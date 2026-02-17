"""
ETL Module: Fetch OSM Urban Features

Extracts building and landuse data from OpenStreetMap around each UNESCO heritage site
using OSMnx library. Features are fetched within a configurable radius (default 5 km)
and stored in the urban_features table.

Usage:
    python -m src.etl.fetch_osm [--test] [--verbose] [--limit N]
"""

import logging
import time
import argparse
from typing import Optional, Dict, Any, List
from datetime import datetime

import osmnx as ox
import geopandas as gpd
import pandas as pd
from tqdm import tqdm
from shapely import wkt
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import (
    OSM_BUFFER_M,
    OSM_TAGS,
    OSMNX_TIMEOUT,
    OSMNX_CACHE_FOLDER,
    OSMNX_SLEEP_SECONDS,
    PROJ_CRS,
)
from src.db.connection import get_session, engine
from src.db.models import HeritageSite, UrbanFeature

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def configure_osmnx():
    """Configure OSMnx settings for stable and cached requests."""
    ox.settings.timeout = OSMNX_TIMEOUT
    ox.settings.use_cache = True
    ox.settings.cache_folder = OSMNX_CACHE_FOLDER
    logger.info(f"OSMnx configured: timeout={OSMNX_TIMEOUT}s, cache={OSMNX_CACHE_FOLDER}")


def fetch_osm_for_site(
    site_id: int,
    lat: float,
    lon: float,
    radius_m: int = OSM_BUFFER_M,
    tags: Optional[Dict[str, Any]] = None
) -> Optional[gpd.GeoDataFrame]:
    """
    Fetch OSM features around a single heritage site.
    
    Args:
        site_id: Heritage site database ID
        lat: Site latitude (WGS84)
        lon: Site longitude (WGS84)
        radius_m: Search radius in meters (default from config)
        tags: OSM tags to extract (default from config)
    
    Returns:
        GeoDataFrame with OSM features or None if error/no data
    """
    if tags is None:
        tags = OSM_TAGS
    
    try:
        # Fetch features from OSM
        logger.debug(f"Fetching OSM features for site {site_id} at ({lat}, {lon}), radius={radius_m}m")
        gdf = ox.features_from_point((lat, lon), tags=tags, dist=radius_m)
        
        if gdf.empty:
            logger.warning(f"No OSM features found for site {site_id}")
            return None
        
        # Reset index to get OSM ID and type as columns
        gdf = gdf.reset_index()
        
        # Add site reference
        gdf['site_id'] = site_id
        
        # Compute area for polygon features in EPSG:3035 (metric CRS)
        gdf = compute_feature_areas(gdf)
        
        logger.info(f"Fetched {len(gdf)} OSM features for site {site_id}")
        return gdf
        
    except ox._errors.InsufficientResponseError as e:
        logger.warning(f"Insufficient OSM data for site {site_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching OSM for site {site_id}: {e}")
        return None


def compute_feature_areas(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Compute area in square meters for polygon features using EPSG:3035.
    
    Args:
        gdf: Input GeoDataFrame in WGS84 (EPSG:4326)
    
    Returns:
        GeoDataFrame with area_m2 column
    """
    try:
        # Save original CRS
        original_crs = gdf.crs
        
        # Reproject to metric CRS for accurate area calculation
        gdf_proj = gdf.to_crs(epsg=PROJ_CRS)
        
        # Calculate area for polygon geometries
        gdf['area_m2'] = gdf_proj.geometry.apply(
            lambda geom: geom.area if geom.geom_type in ['Polygon', 'MultiPolygon'] else 0.0
        )
        
        logger.debug(f"Computed areas for {len(gdf)} features")
        return gdf
        
    except Exception as e:
        logger.error(f"Error computing areas: {e}")
        gdf['area_m2'] = 0.0
        return gdf


def map_osm_to_db_schema(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Map OSM GeoDataFrame columns to database schema.
    
    Args:
        gdf: Raw OSM GeoDataFrame
    
    Returns:
        GeoDataFrame with columns matching urban_features table
    """
    mapped_data = []
    
    for _, row in gdf.iterrows():
        try:
            # Determine feature type and value
            feature_type, feature_value = extract_feature_info(row)
            
            # Build mapped record
            record = {
                'osm_id': int(row.get('osmid', 0)) if pd.notna(row.get('osmid')) else None,
                'osm_type': str(row.get('element_type', 'unknown')),
                'feature_type': feature_type,
                'feature_value': feature_value,
                'name': str(row.get('name', ''))[:500] if pd.notna(row.get('name')) else None,
                'nearest_site_id': int(row['site_id']),
                'distance_to_site_m': None,  # Will be computed in Phase 5
                'geom': row.geometry,
                'area_m2': row.get('area_m2', 0.0),
            }
            mapped_data.append(record)
            
        except Exception as e:
            logger.warning(f"Error mapping OSM record: {e}")
            continue
    
    if not mapped_data:
        return gpd.GeoDataFrame()
    
    # Create new GeoDataFrame
    mapped_gdf = gpd.GeoDataFrame(mapped_data, crs=gdf.crs)
    logger.debug(f"Mapped {len(mapped_gdf)} OSM features to DB schema")
    
    return mapped_gdf


def extract_feature_info(row: pd.Series) -> tuple:
    """
    Extract feature_type and feature_value from OSM tags.
    
    Args:
        row: OSM feature row
    
    Returns:
        Tuple of (feature_type, feature_value)
    """
    # Check building tag first
    if pd.notna(row.get('building')):
        building_val = row.get('building')
        if building_val is True or building_val == 'yes':
            return ('building', 'yes')
        else:
            return ('building', str(building_val))
    
    # Check landuse tag
    if pd.notna(row.get('landuse')):
        return ('landuse', str(row.get('landuse')))
    
    # Default
    return ('unknown', 'unknown')


def upsert_osm_features(gdf: gpd.GeoDataFrame, session: Session) -> int:
    """
    Insert or update OSM features in the urban_features table.
    
    Args:
        gdf: GeoDataFrame with OSM features
        session: SQLAlchemy session
    
    Returns:
        Number of rows inserted/updated
    """
    if gdf.empty:
        return 0
    
    try:
        # Drop the area_m2 column as it's not in the database schema
        gdf_to_insert = gdf.drop(columns=['area_m2'], errors='ignore')
        
        # Use GeoPandas to_postgis for efficient bulk insert
        # This will handle geometry conversion automatically
        count = len(gdf_to_insert)
        gdf_to_insert.to_postgis(
            name='urban_features',
            con=engine,
            schema='unesco_risk',
            if_exists='append',
            index=False
        )
        
        session.commit()
        logger.info(f"Inserted {count} OSM features into database")
        return count
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error inserting OSM features: {e}")
        return 0


def fetch_all_osm(
    session: Session,
    test_mode: bool = False,
    limit: Optional[int] = None,
    verbose: bool = False
) -> Dict[str, int]:
    """
    Fetch OSM features for all heritage sites.
    
    Args:
        session: SQLAlchemy session
        test_mode: If True, only process first 5 sites
        limit: Optional limit on number of sites to process
        verbose: Enable verbose logging
    
    Returns:
        Dictionary with statistics
    """
    if verbose:
        logger.setLevel(logging.DEBUG)
    
    # Configure OSMnx
    configure_osmnx()
    
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
    
    logger.info(f"Fetching OSM data for {total_sites} heritage sites")
    
    # Statistics
    stats = {
        'total_sites': total_sites,
        'sites_processed': 0,
        'sites_with_data': 0,
        'sites_failed': 0,
        'total_features': 0,
    }
    
    # Process each site
    for site in tqdm(sites, desc="Fetching OSM data"):
        try:
            # Extract coordinates from WKT geometry
            geom_wkt = session.scalar(text(
                f"SELECT ST_AsText(geom) FROM unesco_risk.heritage_sites WHERE id = {site.id}"
            ))
            lat, lon = parse_point_wkt(geom_wkt)
            
            # Fetch OSM features
            osm_gdf = fetch_osm_for_site(site.id, lat, lon)
            
            if osm_gdf is not None and not osm_gdf.empty:
                # Map to DB schema
                mapped_gdf = map_osm_to_db_schema(osm_gdf)
                
                if not mapped_gdf.empty:
                    # Insert into database
                    count = upsert_osm_features(mapped_gdf, session)
                    stats['total_features'] += count
                    stats['sites_with_data'] += 1
            
            stats['sites_processed'] += 1
            
            # Rate limiting: sleep between requests
            time.sleep(OSMNX_SLEEP_SECONDS)
            
        except Exception as e:
            logger.error(f"Failed to process site {site.id} ({site.name}): {e}")
            stats['sites_failed'] += 1
            continue
    
    logger.info("=" * 60)
    logger.info("OSM FETCH COMPLETE")
    logger.info(f"Total sites: {stats['total_sites']}")
    logger.info(f"Sites processed: {stats['sites_processed']}")
    logger.info(f"Sites with OSM data: {stats['sites_with_data']}")
    logger.info(f"Sites failed: {stats['sites_failed']}")
    logger.info(f"Total OSM features: {stats['total_features']}")
    logger.info("=" * 60)
    
    return stats


def parse_point_wkt(wkt_str: str) -> tuple:
    """
    Parse WKT POINT string to extract lat/lon.
    
    Args:
        wkt_str: WKT string like 'POINT(lon lat)'
    
    Returns:
        Tuple of (lat, lon)
    """
    geom = wkt.loads(wkt_str)
    return geom.y, geom.x  # lat, lon


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch OSM urban features for UNESCO heritage sites"
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
    
    # Create database session
    session = get_session()
    
    try:
        # Run OSM fetch
        stats = fetch_all_osm(
            session=session,
            test_mode=args.test,
            limit=args.limit,
            verbose=args.verbose
        )
        
        # Print summary
        print("\n" + "=" * 60)
        print("OSM ETL SUMMARY")
        print("=" * 60)
        print(f"Sites processed: {stats['sites_processed']}/{stats['total_sites']}")
        print(f"Sites with data: {stats['sites_with_data']}")
        print(f"Sites failed: {stats['sites_failed']}")
        print(f"Total features collected: {stats['total_features']}")
        print("=" * 60)
        
    finally:
        session.close()


if __name__ == '__main__':
    main()
