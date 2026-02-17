"""
ETL Module: Fetch Elevation Data

Retrieves elevation data from OpenTopography API using Copernicus DEM (COP30).
Computes coastal risk scores for sites near coastlines.

API: https://portal.opentopography.org/API/globaldem

Usage:
    python -m src.etl.fetch_elevation [--test] [--verbose]
"""

import logging
import argparse
from typing import Optional, Dict, Tuple
from io import BytesIO
import time
import requests
import numpy as np
import rasterio
from rasterio.io import MemoryFile
import pandas as pd
from tqdm import tqdm
from shapely import wkt
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import (
    OPENTOPO_API_URL,
    OPENTOPO_API_KEY,
    DEM_TYPE,
    DEM_BUFFER_DEG,
    COASTAL_ELEVATION_THRESHOLD_M,
    COASTAL_DISTANCE_THRESHOLD_KM,
)
from src.db.connection import get_session
from src.db.models import HeritageSite

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_elevation(
    lat: float,
    lon: float,
    api_key: str,
    dem_type: str = DEM_TYPE,
    buffer_deg: float = DEM_BUFFER_DEG
) -> Optional[float]:
    """
    Fetch elevation at a specific point from OpenTopography API.
    
    Args:
        lat: Latitude (WGS84)
        lon: Longitude (WGS84)
        api_key: OpenTopography API key
        dem_type: DEM dataset (COP30, SRTMGL3, etc.)
        buffer_deg: Buffer around point in degrees
    
    Returns:
        Elevation in meters or None if error
    """
    try:
        # Build bounding box around point
        south = lat - buffer_deg
        north = lat + buffer_deg
        west = lon - buffer_deg
        east = lon + buffer_deg
        
        # OpenTopography API parameters
        params = {
            'demtype': dem_type,
            'south': south,
            'north': north,
            'west': west,
            'east': east,
            'outputFormat': 'GTiff',
            'API_Key': api_key,
        }
        
        logger.debug(f"Fetching elevation at ({lat}, {lon}) with buffer {buffer_deg}°")
        
        response = requests.get(OPENTOPO_API_URL, params=params, timeout=30)
        response.raise_for_status()
        
        # Read GeoTIFF from response
        with MemoryFile(BytesIO(response.content)) as memfile:
            with memfile.open() as dataset:
                # Sample elevation at exact coordinate
                row, col = dataset.index(lon, lat)
                elevation = dataset.read(1)[row, col]
                
                # Handle nodata values
                if dataset.nodata is not None and elevation == dataset.nodata:
                    logger.warning(f"No elevation data at ({lat}, {lon})")
                    return None
                
                logger.debug(f"Elevation at ({lat}, {lon}): {elevation:.2f} m")
                return float(elevation)
        
    except requests.RequestException as e:
        logger.error(f"HTTP error fetching elevation: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching elevation at ({lat}, {lon}): {e}")
        return None


def compute_coastal_risk_score(elevation: Optional[float]) -> float:
    """
    Compute coastal risk score based on elevation.
    
    Score formula: max(0, 1 - elevation/10)
    - Sites at sea level (0m): score = 1.0 (highest risk)
    - Sites at 10m+: score = 0.0 (no coastal risk)
    
    Args:
        elevation: Elevation in meters
    
    Returns:
        Coastal risk score (0.0 to 1.0)
    """
    if elevation is None:
        return 0.0
    
    if elevation < 0:
        # Below sea level - maximum risk
        return 1.0
    
    score = max(0.0, 1.0 - (elevation / COASTAL_ELEVATION_THRESHOLD_M))
    return round(score, 4)


def update_site_elevation(
    site_id: int,
    elevation: float,
    coastal_risk: float,
    session: Session
):
    """
    Update heritage_sites table with elevation data.
    
    Note: This requires adding elevation columns to the table first.
    
    Args:
        site_id: Heritage site ID
        elevation: Elevation in meters
        coastal_risk: Coastal risk score
        session: SQLAlchemy session
    """
    try:
        # Check if elevation column exists
        query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'unesco_risk' 
            AND table_name = 'heritage_sites' 
            AND column_name = 'elevation_m'
        """)
        
        result = session.execute(query).fetchone()
        
        if result is None:
            # Add elevation columns
            logger.info("Adding elevation columns to heritage_sites table...")
            alter_query = text("""
                ALTER TABLE unesco_risk.heritage_sites
                ADD COLUMN IF NOT EXISTS elevation_m FLOAT,
                ADD COLUMN IF NOT EXISTS coastal_risk_score FLOAT
            """)
            session.execute(alter_query)
            session.commit()
        
        # Update site
        update_query = text("""
            UPDATE unesco_risk.heritage_sites
            SET elevation_m = :elevation,
                coastal_risk_score = :coastal_risk,
                updated_at = NOW()
            WHERE id = :site_id
        """)
        
        session.execute(update_query, {
            'site_id': site_id,
            'elevation': elevation,
            'coastal_risk': coastal_risk,
        })
        session.commit()
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating site {site_id} elevation: {e}")


def fetch_all_elevations(
    session: Session,
    api_key: str,
    test_mode: bool = False,
    limit: Optional[int] = None,
    verbose: bool = False
) -> Dict[str, int]:
    """
    Fetch elevation data for all heritage sites.
    
    Args:
        session: SQLAlchemy session
        api_key: OpenTopography API key
        test_mode: If True, only process first 5 sites
        limit: Optional limit on number of sites
        verbose: Enable verbose logging
    
    Returns:
        Dictionary with statistics
    """
    if verbose:
        logger.setLevel(logging.DEBUG)
    
    # Verify API key
    if not api_key or api_key == 'your_opentopo_api_key_here':
        logger.error("OpenTopography API key not configured")
        logger.info("Get your free API key at: https://portal.opentopography.org/")
        return {'error': 'No API key'}
    
    # Get all heritage sites
    query = session.query(HeritageSite.id, HeritageSite.name, HeritageSite.geom)
    
    if test_mode:
        logger.info("TEST MODE: Processing only 5 sites")
        query = query.limit(5)
    elif limit:
        logger.info(f"Processing {limit} sites (limit applied)")
        query = query.limit(limit)
    
    sites = query.all()
    total_sites = len(sites)
    
    logger.info(f"Fetching elevation data for {total_sites} heritage sites")
    
    # Statistics
    stats = {
        'total_sites': total_sites,
        'sites_processed': 0,
        'sites_with_data': 0,
        'sites_failed': 0,
        'coastal_sites': 0,
    }
    
    # Process each site
    for site in tqdm(sites, desc="Fetching elevation data"):
        try:
            # Extract coordinates
            geom_wkt = session.scalar(text(
                f"SELECT ST_AsText(geom) FROM unesco_risk.heritage_sites WHERE id = {site.id}"
            ))
            lat, lon = parse_point_wkt(geom_wkt)
            
            # Fetch elevation
            elevation = fetch_elevation(lat, lon, api_key)
            
            if elevation is not None:
                # Compute coastal risk
                coastal_risk = compute_coastal_risk_score(elevation)
                
                # Update database
                update_site_elevation(site.id, elevation, coastal_risk, session)
                
                stats['sites_with_data'] += 1
                
                if coastal_risk > 0:
                    stats['coastal_sites'] += 1
            
            stats['sites_processed'] += 1
            
            # Rate limiting (OpenTopography has rate limits)
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Failed to process site {site.id} ({site.name}): {e}")
            stats['sites_failed'] += 1
            continue
    
    logger.info("=" * 60)
    logger.info("ELEVATION FETCH COMPLETE")
    logger.info(f"Total sites: {stats['total_sites']}")
    logger.info(f"Sites processed: {stats['sites_processed']}")
    logger.info(f"Sites with elevation data: {stats['sites_with_data']}")
    logger.info(f"Sites with coastal risk: {stats['coastal_sites']}")
    logger.info(f"Sites failed: {stats['sites_failed']}")
    logger.info("=" * 60)
    
    return stats


def parse_point_wkt(wkt_str: str) -> Tuple[float, float]:
    """Parse WKT POINT string to extract lat/lon."""
    geom = wkt.loads(wkt_str)
    return geom.y, geom.x  # lat, lon


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch elevation data for UNESCO heritage sites"
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: process only 5 sites'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of sites to process'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Get API key from environment
    api_key = OPENTOPO_API_KEY
    
    # Create database session
    session = get_session()
    
    try:
        # Run elevation fetch
        stats = fetch_all_elevations(
            session=session,
            api_key=api_key,
            test_mode=args.test,
            limit=args.limit,
            verbose=args.verbose
        )
        
        if 'error' in stats:
            return
        
        # Print summary
        print("\n" + "=" * 60)
        print("ELEVATION ETL SUMMARY")
        print("=" * 60)
        print(f"Sites processed: {stats['sites_processed']}/{stats['total_sites']}")
        print(f"Sites with data: {stats['sites_with_data']}")
        print(f"Sites with coastal risk: {stats['coastal_sites']}")
        print(f"Sites failed: {stats['sites_failed']}")
        print("=" * 60)
        
    finally:
        session.close()


if __name__ == '__main__':
    main()
