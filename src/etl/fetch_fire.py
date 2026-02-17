"""
ETL Module: Fetch Fire Data

Retrieves active fire detections from NASA FIRMS (Fire Information for Resource Management System).
Uses VIIRS and MODIS satellite data.

API: https://firms.modaps.eosdis.nasa.gov/

Usage:
    python -m src.etl.fetch_fire [--days 10] [--source VIIRS_SNPP_NRT] [--verbose]
"""

import logging
import argparse
from typing import Optional, Dict, List
from datetime import datetime, date, timedelta
import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from sqlalchemy import text
from sqlalchemy.orm import Session
import os

from config.settings import (
    FIRMS_API_URL,
    FIRMS_API_KEY,
    FIRMS_DEFAULT_SOURCE,
    FIRMS_DEFAULT_DAYS,
    EUROPE_BBOX,
)
from src.db.connection import get_session, engine
from src.db.models import FireEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def verify_firms_api_key(api_key: str) -> bool:
    """
    Verify that FIRMS API key is valid.
    
    Args:
        api_key: FIRMS API key
    
    Returns:
        True if key is valid, False otherwise
    """
    if not api_key or api_key == 'your_firms_api_key_here':
        logger.error("FIRMS API key not configured. Please set FIRMS_API_KEY in .env")
        return False
    
    # Test with a small query (1 day, small area)
    test_url = f"{FIRMS_API_URL}/{api_key}/{FIRMS_DEFAULT_SOURCE}/0,0,1/1"
    
    try:
        response = requests.get(test_url, timeout=10)
        if response.status_code == 200:
            logger.info("✓ FIRMS API key is valid")
            return True
        elif response.status_code == 403:
            logger.error("✗ FIRMS API key is invalid (403 Forbidden)")
            return False
        else:
            logger.warning(f"FIRMS API returned status {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error verifying FIRMS API key: {e}")
        return False


def fetch_firms_fire(
    api_key: str,
    source: str = FIRMS_DEFAULT_SOURCE,
    days: int = FIRMS_DEFAULT_DAYS,
    bbox: Optional[Dict] = None
) -> Optional[gpd.GeoDataFrame]:
    """
    Fetch fire detection data from FIRMS API (NRT - Near Real Time).
    
    Note: FIRMS NRT API only provides last 10 days of data.
    For historical data, use archive downloads from FIRMS website.
    
    Args:
        api_key: FIRMS API key
        source: Satellite source (VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT, MODIS_NRT)
        days: Number of days to fetch (1-10 for NRT)
        bbox: Bounding box dict with min_lat, max_lat, min_lon, max_lon
    
    Returns:
        GeoDataFrame with fire events or None if error
    """
    if bbox is None:
        bbox = EUROPE_BBOX
    
    if days > 10:
        logger.warning("FIRMS NRT API only provides last 10 days. Setting days=10")
        days = 10
    
    try:
        # Build API URL: /MAP_KEY/SOURCE/BBOX/DAYS
        # BBOX format: min_lon,min_lat,max_lon,max_lat
        bbox_str = f"{bbox['min_lon']},{bbox['min_lat']},{bbox['max_lon']},{bbox['max_lat']}"
        url = f"{FIRMS_API_URL}/{api_key}/{source}/{bbox_str}/{days}"
        
        logger.info(f"Fetching FIRMS fire data: source={source}, days={days}")
        logger.info(f"URL: {url}")
        
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        # FIRMS API returns CSV format
        if response.status_code == 200:
            # Check if response is empty
            if len(response.text.strip()) == 0:
                logger.warning("No fire detections in response")
                return None
            
            # Parse CSV
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))
            
            if df.empty:
                logger.warning("No fire detections found")
                return None
            
            logger.info(f"Received {len(df)} fire detections from FIRMS")
            
            # Parse and validate data
            gdf = parse_firms_csv(df, source)
            return gdf
        else:
            logger.error(f"FIRMS API returned status {response.status_code}")
            return None
        
    except requests.RequestException as e:
        logger.error(f"HTTP error fetching FIRMS data: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching FIRMS data: {e}")
        return None


def parse_firms_csv(df: pd.DataFrame, source: str) -> gpd.GeoDataFrame:
    """
    Parse FIRMS CSV data into standardized format.
    
    FIRMS columns vary slightly between VIIRS and MODIS:
    - VIIRS: latitude, longitude, bright_ti4, confidence, frp, acq_date, acq_time, daynight
    - MODIS: latitude, longitude, brightness, confidence, frp, acq_date, acq_time, daynight
    
    Args:
        df: Raw FIRMS DataFrame
        source: Satellite source identifier
    
    Returns:
        GeoDataFrame with standardized columns
    """
    try:
        # Map column names
        records = []
        
        for _, row in df.iterrows():
            try:
                # Handle VIIRS vs MODIS brightness column
                brightness = row.get('bright_ti4', row.get('brightness'))
                
                # Normalize confidence
                # VIIRS: low/nominal/high OR 0-100
                # MODIS: 0-100
                confidence = normalize_confidence(row.get('confidence'))
                
                # Parse date and time
                acq_date = pd.to_datetime(row['acq_date'])
                acq_time_str = str(int(row['acq_time'])).zfill(4)  # Ensure 4 digits
                acq_time = datetime.strptime(acq_time_str, '%H%M').time()
                
                record = {
                    'satellite': source,
                    'brightness': float(brightness) if pd.notna(brightness) else None,
                    'confidence': int(confidence),
                    'frp': float(row['frp']) if pd.notna(row['frp']) else None,
                    'acq_date': acq_date.date(),
                    'acq_time': acq_time,
                    'day_night': row.get('daynight', 'D')[0],  # D or N
                    'geom': Point(float(row['longitude']), float(row['latitude'])),
                }
                records.append(record)
            except Exception as e:
                logger.warning(f"Error parsing fire record: {e}")
                continue
        
        if not records:
            logger.warning("No valid fire records parsed")
            return gpd.GeoDataFrame()
        
        gdf = gpd.GeoDataFrame(records, geometry='geom', crs='EPSG:4326')
        logger.info(f"Parsed {len(gdf)} fire detections")
        
        return gdf
        
    except Exception as e:
        logger.error(f"Error parsing FIRMS CSV: {e}")
        return gpd.GeoDataFrame()


def normalize_confidence(confidence_val) -> int:
    """
    Normalize confidence values to 0-100 integer scale.
    
    VIIRS can be: 'low', 'nominal', 'high' OR 0-100
    MODIS is: 0-100
    
    Args:
        confidence_val: Confidence value (str or numeric)
    
    Returns:
        Integer confidence 0-100
    """
    if pd.isna(confidence_val):
        return 0
    
    # Check if it's a string (VIIRS categorical)
    if isinstance(confidence_val, str):
        confidence_str = confidence_val.lower()
        if 'low' in confidence_str:
            return 30
        elif 'nominal' in confidence_str:
            return 50
        elif 'high' in confidence_str:
            return 80
        else:
            # Try to parse as number
            try:
                return int(float(confidence_val))
            except:
                return 50  # Default
    
    # Numeric value
    return int(float(confidence_val))


def upsert_fire_data(gdf: gpd.GeoDataFrame, session: Session) -> int:
    """
    Insert or update fire data in the fire_events table.
    
    Uses simple INSERT (no ON CONFLICT) since fire events are unique by
    (lat, lon, acq_date, acq_time, satellite).
    
    Args:
        gdf: GeoDataFrame with fire data
        session: SQLAlchemy session
    
    Returns:
        Number of rows inserted
    """
    if gdf is None or gdf.empty:
        return 0
    
    try:
        inserted = 0
        
        for _, row in gdf.iterrows():
            try:
                # Check if record already exists
                query = text("""
                    SELECT COUNT(*) FROM unesco_risk.fire_events
                    WHERE satellite = :satellite
                    AND acq_date = :acq_date
                    AND acq_time = :acq_time
                    AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 100)
                """)
                
                exists = session.execute(query, {
                    'satellite': row['satellite'],
                    'acq_date': row['acq_date'],
                    'acq_time': row['acq_time'],
                    'lon': row.geometry.x,
                    'lat': row.geometry.y,
                }).scalar()
                
                if exists > 0:
                    continue  # Skip duplicate
                
                # Insert new record
                insert_query = text("""
                    INSERT INTO unesco_risk.fire_events
                    (satellite, brightness, confidence, frp, acq_date, acq_time, day_night, geom)
                    VALUES
                    (:satellite, :brightness, :confidence, :frp, :acq_date, :acq_time,
                     :day_night, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                """)
                
                session.execute(insert_query, {
                    'satellite': row['satellite'],
                    'brightness': float(row['brightness']) if pd.notna(row['brightness']) else None,
                    'confidence': int(row['confidence']),
                    'frp': float(row['frp']) if pd.notna(row['frp']) else None,
                    'acq_date': row['acq_date'],
                    'acq_time': row['acq_time'],
                    'day_night': row['day_night'],
                    'lon': row.geometry.x,
                    'lat': row.geometry.y,
                })
                inserted += 1
            except Exception as e:
                logger.warning(f"Error inserting fire record: {e}")
                continue
        
        session.commit()
        logger.info(f"Inserted {inserted} fire records")
        return inserted
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error inserting fire data: {e}")
        return 0


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch fire detection data from NASA FIRMS"
    )
    parser.add_argument(
        '--days',
        type=int,
        default=FIRMS_DEFAULT_DAYS,
        help=f'Number of days to fetch (1-10, default: {FIRMS_DEFAULT_DAYS})'
    )
    parser.add_argument(
        '--source',
        type=str,
        default=FIRMS_DEFAULT_SOURCE,
        choices=['VIIRS_SNPP_NRT', 'VIIRS_NOAA20_NRT', 'MODIS_NRT'],
        help=f'Satellite source (default: {FIRMS_DEFAULT_SOURCE})'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Get API key from environment
    api_key = FIRMS_API_KEY
    
    # Verify API key
    if not verify_firms_api_key(api_key):
        logger.error("Cannot proceed without valid FIRMS API key")
        logger.info("Get your free API key at: https://firms.modaps.eosdis.nasa.gov/api/area/")
        return
    
    # Create database session
    session = get_session()
    
    try:
        # Fetch fire data
        logger.info("Starting fire data fetch...")
        gdf = fetch_firms_fire(
            api_key=api_key,
            source=args.source,
            days=args.days,
            bbox=EUROPE_BBOX
        )
        
        if gdf is None or gdf.empty:
            logger.warning("No fire data fetched")
            return
        
        # Insert into database
        count = upsert_fire_data(gdf, session)
        
        # Print summary
        print("\n" + "=" * 60)
        print("FIRE ETL SUMMARY")
        print("=" * 60)
        print(f"Total fire detections fetched: {len(gdf)}")
        print(f"Records inserted: {count}")
        print(f"Source: {args.source}")
        print(f"Days: {args.days}")
        print(f"Date range: {gdf['acq_date'].min()} to {gdf['acq_date'].max()}")
        print(f"Confidence range: {gdf['confidence'].min()} - {gdf['confidence'].max()}")
        print("=" * 60)
        
        # Fire distribution by day/night
        day_night_counts = gdf['day_night'].value_counts()
        print("\nDetections by time:")
        for dn, count in day_night_counts.items():
            dn_label = "Day" if dn == 'D' else "Night"
            print(f"  {dn_label}: {count}")
        
    finally:
        session.close()


if __name__ == '__main__':
    main()
