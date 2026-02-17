"""
ETL Module: Fetch Earthquake Data

Retrieves earthquake events from USGS Earthquake Catalog API.
Fetches European earthquakes (magnitude >= 3.0) from 2015-2025.

API: https://earthquake.usgs.gov/fdsnws/event/1/

Usage:
    python -m src.etl.fetch_earthquake [--min-mag 3.0] [--verbose]
"""

import logging
import argparse
from typing import Optional, Dict, List
from datetime import datetime
import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import (
    USGS_EARTHQUAKE_URL,
    EARTHQUAKE_MIN_MAGNITUDE,
    EARTHQUAKE_START_DATE,
    EARTHQUAKE_END_DATE,
    EUROPE_BBOX,
)
from src.db.connection import get_session, engine
from src.db.models import EarthquakeEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_earthquakes_europe(
    min_magnitude: float = EARTHQUAKE_MIN_MAGNITUDE,
    start_date: str = EARTHQUAKE_START_DATE,
    end_date: str = EARTHQUAKE_END_DATE,
    bbox: Optional[Dict] = None
) -> Optional[gpd.GeoDataFrame]:
    """
    Fetch earthquake events from USGS for Europe.
    
    Args:
        min_magnitude: Minimum magnitude threshold
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        bbox: Bounding box dict with min_lat, max_lat, min_lon, max_lon
    
    Returns:
        GeoDataFrame with earthquake events or None if error
    """
    if bbox is None:
        bbox = EUROPE_BBOX
    
    try:
        # USGS API expects: minlatitude, maxlatitude, minlongitude, maxlongitude
        params = {
            'format': 'geojson',
            'starttime': start_date,
            'endtime': end_date,
            'minmagnitude': min_magnitude,
            'minlatitude': bbox['min_lat'],
            'maxlatitude': bbox['max_lat'],
            'minlongitude': bbox['min_lon'],
            'maxlongitude': bbox['max_lon'],
            'orderby': 'time-asc',
        }
        
        logger.info(f"Fetching earthquakes: mag >= {min_magnitude}, {start_date} to {end_date}")
        logger.info(f"Bounding box: {bbox}")
        
        response = requests.get(USGS_EARTHQUAKE_URL, params=params, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        # Check for features
        if 'features' not in data or len(data['features']) == 0:
            logger.warning("No earthquake events found in response")
            return None
        
        features = data['features']
        logger.info(f"Received {len(features)} earthquake events from USGS")
        
        # Parse GeoJSON features
        records = []
        for feature in features:
            try:
                props = feature['properties']
                coords = feature['geometry']['coordinates']  # [lon, lat, depth]
                
                record = {
                    'usgs_id': feature['id'],
                    'magnitude': props.get('mag'),
                    'mag_type': props.get('magType'),
                    'depth_km': coords[2] if len(coords) > 2 else None,
                    'place_desc': props.get('place', '')[:300],
                    'event_time': datetime.fromtimestamp(props['time'] / 1000.0),  # Convert from epoch ms
                    'significance': props.get('sig'),
                    'mmi': props.get('mmi'),
                    'alert_level': props.get('alert'),
                    'tsunami': props.get('tsunami') == 1,
                    'geom': Point(coords[0], coords[1]),  # lon, lat
                }
                records.append(record)
            except Exception as e:
                logger.warning(f"Error parsing earthquake feature: {e}")
                continue
        
        if not records:
            logger.warning("No valid earthquake records parsed")
            return None
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(records, geometry='geom', crs='EPSG:4326')
        logger.info(f"Parsed {len(gdf)} earthquake events")
        
        # Validate data
        validate_earthquake_data(gdf)
        
        return gdf
        
    except requests.RequestException as e:
        logger.error(f"HTTP error fetching earthquake data: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching earthquake data: {e}")
        return None


def validate_earthquake_data(gdf: gpd.GeoDataFrame):
    """
    Validate earthquake data quality.
    
    Args:
        gdf: Earthquake GeoDataFrame
    """
    logger.info("Validating earthquake data...")
    
    # Check magnitude range
    mag_min = gdf['magnitude'].min()
    mag_max = gdf['magnitude'].max()
    logger.info(f"Magnitude range: {mag_min:.2f} to {mag_max:.2f}")
    
    # Check depth values
    if 'depth_km' in gdf.columns:
        depth_invalid = gdf[gdf['depth_km'] < 0]
        if len(depth_invalid) > 0:
            logger.warning(f"Found {len(depth_invalid)} events with negative depth")
    
    # Check for null geometries
    null_geoms = gdf[gdf.geometry.is_empty]
    if len(null_geoms) > 0:
        logger.warning(f"Found {len(null_geoms)} events with null geometry")
    
    # Time range
    time_min = gdf['event_time'].min()
    time_max = gdf['event_time'].max()
    logger.info(f"Time range: {time_min} to {time_max}")
    
    # Magnitude distribution
    mag_bins = [0, 3, 4, 5, 6, 7, 10]
    mag_counts = pd.cut(gdf['magnitude'], bins=mag_bins).value_counts().sort_index()
    logger.info("Magnitude distribution:")
    for interval, count in mag_counts.items():
        logger.info(f"  {interval}: {count}")


def handle_pagination(
    min_magnitude: float,
    start_date: str,
    end_date: str,
    bbox: Dict
) -> gpd.GeoDataFrame:
    """
    Handle USGS API pagination for large datasets.
    
    USGS API has a limit of 20,000 events per request.
    If we hit this limit, split the query by year.
    
    Args:
        min_magnitude: Minimum magnitude
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        bbox: Bounding box
    
    Returns:
        Combined GeoDataFrame
    """
    # First try a single request
    gdf = fetch_earthquakes_europe(min_magnitude, start_date, end_date, bbox)
    
    if gdf is None or len(gdf) < 20000:
        # No pagination needed
        return gdf
    
    logger.warning("Dataset may be truncated (20k limit). Splitting by year...")
    
    # Split by year
    start_year = int(start_date.split('-')[0])
    end_year = int(end_date.split('-')[0])
    
    all_gdfs = []
    
    for year in range(start_year, end_year + 1):
        year_start = f"{year}-01-01"
        year_end = f"{year}-12-31" if year < end_year else end_date
        
        logger.info(f"Fetching earthquakes for year {year}...")
        year_gdf = fetch_earthquakes_europe(min_magnitude, year_start, year_end, bbox)
        
        if year_gdf is not None:
            all_gdfs.append(year_gdf)
    
    if not all_gdfs:
        return None
    
    # Combine all years
    combined_gdf = pd.concat(all_gdfs, ignore_index=True)
    logger.info(f"Combined {len(combined_gdf)} earthquake events from {len(all_gdfs)} years")
    
    return combined_gdf


def upsert_earthquake_data(gdf: gpd.GeoDataFrame, session: Session) -> int:
    """
    Insert or update earthquake data in the earthquake_events table.
    
    Uses ON CONFLICT to handle duplicates based on usgs_id.
    
    Args:
        gdf: GeoDataFrame with earthquake data
        session: SQLAlchemy session
    
    Returns:
        Number of rows inserted/updated
    """
    if gdf is None or gdf.empty:
        return 0
    
    try:
        inserted = 0
        
        for _, row in gdf.iterrows():
            try:
                # Build INSERT ... ON CONFLICT query
                query = text("""
                    INSERT INTO unesco_risk.earthquake_events
                    (usgs_id, magnitude, mag_type, depth_km, place_desc, event_time,
                     significance, mmi, alert_level, tsunami, geom)
                    VALUES
                    (:usgs_id, :magnitude, :mag_type, :depth_km, :place_desc, :event_time,
                     :significance, :mmi, :alert_level, :tsunami,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                    ON CONFLICT (usgs_id)
                    DO UPDATE SET
                        magnitude = EXCLUDED.magnitude,
                        mag_type = EXCLUDED.mag_type,
                        depth_km = EXCLUDED.depth_km,
                        place_desc = EXCLUDED.place_desc,
                        event_time = EXCLUDED.event_time,
                        significance = EXCLUDED.significance,
                        mmi = EXCLUDED.mmi,
                        alert_level = EXCLUDED.alert_level,
                        tsunami = EXCLUDED.tsunami
                """)
                
                session.execute(query, {
                    'usgs_id': str(row['usgs_id']),
                    'magnitude': float(row['magnitude']) if pd.notna(row['magnitude']) else None,
                    'mag_type': str(row['mag_type']) if pd.notna(row['mag_type']) else None,
                    'depth_km': float(row['depth_km']) if pd.notna(row['depth_km']) else None,
                    'place_desc': str(row['place_desc'])[:300] if pd.notna(row['place_desc']) else None,
                    'event_time': row['event_time'],
                    'significance': int(row['significance']) if pd.notna(row['significance']) else None,
                    'mmi': float(row['mmi']) if pd.notna(row['mmi']) else None,
                    'alert_level': str(row['alert_level']) if pd.notna(row['alert_level']) else None,
                    'tsunami': bool(row['tsunami']) if pd.notna(row['tsunami']) else False,
                    'lon': row.geometry.x,
                    'lat': row.geometry.y,
                })
                inserted += 1
            except Exception as e:
                logger.warning(f"Error inserting earthquake record {row.get('usgs_id')}: {e}")
                continue
        
        session.commit()
        logger.info(f"Inserted/updated {inserted} earthquake records")
        return inserted
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error inserting earthquake data: {e}")
        return 0


def test_known_earthquakes(gdf: gpd.GeoDataFrame):
    """
    Spot check for known major earthquakes.
    
    Args:
        gdf: Earthquake GeoDataFrame
    """
    logger.info("Checking for known major earthquakes...")
    
    # Turkey 2023 M7.8 earthquake
    turkey_2023 = gdf[
        (gdf['event_time'].dt.year == 2023) &
        (gdf['magnitude'] >= 7.5) &
        (gdf['place_desc'].str.contains('Turkey', case=False, na=False))
    ]
    
    if len(turkey_2023) > 0:
        logger.info(f"✓ Found Turkey 2023 M7.8 earthquake: {turkey_2023.iloc[0]['usgs_id']}")
    else:
        logger.warning("✗ Turkey 2023 M7.8 earthquake not found in dataset")
    
    # Italy earthquakes (frequent seismic activity)
    italy_quakes = gdf[gdf['place_desc'].str.contains('Italy', case=False, na=False)]
    logger.info(f"Found {len(italy_quakes)} earthquakes in Italy")
    
    # Greece earthquakes
    greece_quakes = gdf[gdf['place_desc'].str.contains('Greece', case=False, na=False)]
    logger.info(f"Found {len(greece_quakes)} earthquakes in Greece")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch earthquake data from USGS for European heritage sites"
    )
    parser.add_argument(
        '--min-mag',
        type=float,
        default=EARTHQUAKE_MIN_MAGNITUDE,
        help=f'Minimum magnitude (default: {EARTHQUAKE_MIN_MAGNITUDE})'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default=EARTHQUAKE_START_DATE,
        help=f'Start date YYYY-MM-DD (default: {EARTHQUAKE_START_DATE})'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default=EARTHQUAKE_END_DATE,
        help=f'End date YYYY-MM-DD (default: {EARTHQUAKE_END_DATE})'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Create database session
    session = get_session()
    
    try:
        # Fetch earthquake data with pagination handling
        logger.info("Starting earthquake data fetch...")
        gdf = handle_pagination(
            min_magnitude=args.min_mag,
            start_date=args.start_date,
            end_date=args.end_date,
            bbox=EUROPE_BBOX
        )
        
        if gdf is None or gdf.empty:
            logger.error("No earthquake data fetched")
            return
        
        # Test known earthquakes
        test_known_earthquakes(gdf)
        
        # Insert into database
        count = upsert_earthquake_data(gdf, session)
        
        # Print summary
        print("\n" + "=" * 60)
        print("EARTHQUAKE ETL SUMMARY")
        print("=" * 60)
        print(f"Total earthquakes fetched: {len(gdf)}")
        print(f"Records inserted/updated: {count}")
        print(f"Magnitude range: {gdf['magnitude'].min():.2f} - {gdf['magnitude'].max():.2f}")
        print(f"Time range: {gdf['event_time'].min()} to {gdf['event_time'].max()}")
        print("=" * 60)
        
    finally:
        session.close()


if __name__ == '__main__':
    main()
