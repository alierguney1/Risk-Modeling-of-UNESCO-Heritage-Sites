"""
ETL Module: Fetch Flood Data

Samples flood intensity data from GFMS (Global Flood Monitoring System).
Note: GFMS data access may require manual download or web scraping.

For now, this module provides a framework for flood data integration.

Usage:
    python -m src.etl.fetch_flood [--test] [--verbose]
"""

import logging
import argparse
from typing import Optional, Dict, Tuple
from datetime import datetime, date
import requests
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely import wkt
from tqdm import tqdm
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import (
    GFMS_URL,
)
from src.db.connection import get_session, engine
from src.db.models import HeritageSite

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def sample_flood_at_sites(
    session: Session,
    flood_data_path: Optional[str] = None,
    test_mode: bool = False,
    limit: Optional[int] = None,
    verbose: bool = False
) -> Dict[str, int]:
    """
    Sample flood intensity at heritage site locations.
    
    Note: This function expects pre-downloaded GFMS GeoTIFF data.
    GFMS data access typically requires:
    1. Manual download from GFMS website
    2. Or automated scraping (if permitted)
    
    Args:
        session: SQLAlchemy session
        flood_data_path: Path to GFMS GeoTIFF file
        test_mode: If True, only process first 5 sites
        limit: Optional limit on number of sites
        verbose: Enable verbose logging
    
    Returns:
        Dictionary with statistics
    """
    if verbose:
        logger.setLevel(logging.DEBUG)
    
    # Check if flood data is available
    if flood_data_path is None:
        logger.warning("No flood data path provided")
        logger.info("GFMS flood data requires manual download from: https://flood.umd.edu/")
        logger.info("This module will create placeholder records for demonstration")
        use_placeholder = True
    else:
        use_placeholder = False
        logger.info(f"Using flood data from: {flood_data_path}")
    
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
    
    logger.info(f"Sampling flood data for {total_sites} heritage sites")
    
    # Statistics
    stats = {
        'total_sites': total_sites,
        'sites_processed': 0,
        'sites_with_data': 0,
        'sites_failed': 0,
        'total_records': 0,
    }
    
    # Process each site
    for site in tqdm(sites, desc="Sampling flood data"):
        try:
            # Extract coordinates
            geom_wkt = session.scalar(text(
                f"SELECT ST_AsText(geom) FROM unesco_risk.heritage_sites WHERE id = {site.id}"
            ))
            lat, lon = parse_point_wkt(geom_wkt)
            
            # Sample flood intensity
            if use_placeholder:
                # Create placeholder flood record
                flood_intensity = create_placeholder_flood_record(lat, lon)
            else:
                # Sample from actual GFMS data
                flood_intensity = sample_flood_from_raster(flood_data_path, lat, lon)
            
            if flood_intensity is not None and flood_intensity > 0:
                # Insert flood zone record
                count = insert_flood_zone(
                    site_id=site.id,
                    lat=lat,
                    lon=lon,
                    flood_intensity=flood_intensity,
                    event_date=date.today(),
                    session=session
                )
                
                if count > 0:
                    stats['sites_with_data'] += 1
                    stats['total_records'] += count
            
            stats['sites_processed'] += 1
            
        except Exception as e:
            logger.error(f"Failed to process site {site.id} ({site.name}): {e}")
            stats['sites_failed'] += 1
            continue
    
    logger.info("=" * 60)
    logger.info("FLOOD DATA SAMPLING COMPLETE")
    logger.info(f"Total sites: {stats['total_sites']}")
    logger.info(f"Sites processed: {stats['sites_processed']}")
    logger.info(f"Sites with flood data: {stats['sites_with_data']}")
    logger.info(f"Sites failed: {stats['sites_failed']}")
    logger.info(f"Total flood records: {stats['total_records']}")
    logger.info("=" * 60)
    
    return stats


def sample_flood_from_raster(
    raster_path: str,
    lat: float,
    lon: float
) -> Optional[float]:
    """
    Sample flood intensity from GFMS GeoTIFF raster.
    
    Args:
        raster_path: Path to GeoTIFF file
        lat: Latitude (WGS84)
        lon: Longitude (WGS84)
    
    Returns:
        Flood intensity value or None
    """
    try:
        import rasterio
        
        with rasterio.open(raster_path) as dataset:
            # Get pixel coordinates
            row, col = dataset.index(lon, lat)
            
            # Sample value
            value = dataset.read(1)[row, col]
            
            # Handle nodata
            if dataset.nodata is not None and value == dataset.nodata:
                return None
            
            return float(value)
            
    except Exception as e:
        logger.error(f"Error sampling flood raster at ({lat}, {lon}): {e}")
        return None


def create_placeholder_flood_record(lat: float, lon: float) -> float:
    """
    Create placeholder flood intensity for demonstration.
    
    This is a simple heuristic based on latitude (lower latitudes = more flooding risk).
    In production, use actual GFMS data.
    
    Args:
        lat: Latitude
        lon: Longitude
    
    Returns:
        Placeholder flood intensity (0.0 to 1.0)
    """
    # Simple heuristic: lower latitudes have higher flood risk
    # Mediterranean and southern Europe
    if lat < 45:
        base_risk = 0.3
    else:
        base_risk = 0.1
    
    # Add some randomness for variation
    import random
    random.seed(int(lat * 1000 + lon * 1000))
    variation = random.uniform(-0.1, 0.2)
    
    intensity = max(0.0, min(1.0, base_risk + variation))
    return round(intensity, 4)


def insert_flood_zone(
    site_id: int,
    lat: float,
    lon: float,
    flood_intensity: float,
    event_date: date,
    session: Session
) -> int:
    """
    Insert flood zone record into database.
    
    Args:
        site_id: Heritage site ID
        lat: Latitude
        lon: Longitude
        flood_intensity: Flood intensity value
        event_date: Event date
        session: SQLAlchemy session
    
    Returns:
        Number of records inserted (0 or 1)
    """
    try:
        # Check if record already exists
        query = text("""
            SELECT COUNT(*) FROM unesco_risk.flood_zones
            WHERE nearest_site_id = :site_id
            AND event_date = :event_date
        """)
        
        exists = session.execute(query, {
            'site_id': site_id,
            'event_date': event_date,
        }).scalar()
        
        if exists > 0:
            # Update existing record
            update_query = text("""
                UPDATE unesco_risk.flood_zones
                SET flood_intensity = :flood_intensity,
                    geom = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                WHERE nearest_site_id = :site_id
                AND event_date = :event_date
            """)
            
            session.execute(update_query, {
                'site_id': site_id,
                'flood_intensity': flood_intensity,
                'lon': lon,
                'lat': lat,
                'event_date': event_date,
            })
        else:
            # Insert new record
            insert_query = text("""
                INSERT INTO unesco_risk.flood_zones
                (event_date, flood_intensity, nearest_site_id, distance_to_site_km, geom)
                VALUES
                (:event_date, :flood_intensity, :site_id, 0.0,
                 ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            """)
            
            session.execute(insert_query, {
                'site_id': site_id,
                'flood_intensity': flood_intensity,
                'event_date': event_date,
                'lon': lon,
                'lat': lat,
            })
        
        session.commit()
        return 1
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error inserting flood zone for site {site_id}: {e}")
        return 0


def parse_point_wkt(wkt_str: str) -> Tuple[float, float]:
    """Parse WKT POINT string to extract lat/lon."""
    geom = wkt.loads(wkt_str)
    return geom.y, geom.x  # lat, lon


def check_gfms_data_availability() -> bool:
    """
    Check if GFMS data is accessible.
    
    Returns:
        True if accessible, False otherwise
    """
    try:
        logger.info("Checking GFMS data availability...")
        response = requests.get(GFMS_URL, timeout=10)
        
        if response.status_code == 200:
            logger.info("✓ GFMS website is accessible")
            logger.info("Note: GFMS data typically requires manual download")
            logger.info("Visit: https://flood.umd.edu/ for data access")
            return True
        else:
            logger.warning(f"GFMS website returned status {response.status_code}")
            return False
            
    except Exception as e:
        logger.warning(f"Cannot access GFMS website: {e}")
        return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Sample flood data for UNESCO heritage sites"
    )
    parser.add_argument(
        '--data-path',
        type=str,
        help='Path to GFMS GeoTIFF file'
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
    
    # Check GFMS availability
    check_gfms_data_availability()
    
    # Create database session
    session = get_session()
    
    try:
        # Run flood sampling
        stats = sample_flood_at_sites(
            session=session,
            flood_data_path=args.data_path,
            test_mode=args.test,
            limit=args.limit,
            verbose=args.verbose
        )
        
        # Print summary
        print("\n" + "=" * 60)
        print("FLOOD ETL SUMMARY")
        print("=" * 60)
        print(f"Sites processed: {stats['sites_processed']}/{stats['total_sites']}")
        print(f"Sites with flood data: {stats['sites_with_data']}")
        print(f"Sites failed: {stats['sites_failed']}")
        print(f"Total flood records: {stats['total_records']}")
        print("=" * 60)
        
        if args.data_path is None:
            print("\nNote: Using placeholder flood data (no GFMS raster provided)")
            print("For production use, download GFMS data from: https://flood.umd.edu/")
        
    finally:
        session.close()


if __name__ == '__main__':
    main()
