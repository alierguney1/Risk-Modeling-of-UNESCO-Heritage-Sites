"""
ETL Module: Fetch Climate Data

Retrieves climate time-series data from two sources:
1. Open-Meteo Archive API (https://archive-api.open-meteo.com)
2. NASA POWER API (https://power.larc.nasa.gov)

Stores daily climate variables (2020-2025) for all UNESCO heritage sites.

Usage:
    python -m src.etl.fetch_climate [--source {open_meteo|nasa_power|both}] [--test] [--limit N]
"""

import logging
import time
import argparse
from typing import Optional, Dict, List
from datetime import datetime, date
import requests
import pandas as pd
import geopandas as gpd
from tqdm import tqdm
from shapely import wkt
from shapely.geometry import Point
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import (
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_DAILY_VARS,
    NASA_POWER_URL,
    NASA_POWER_PARAMS,
    CLIMATE_START_DATE,
    CLIMATE_END_DATE,
)
from src.db.connection import get_session, engine
from src.db.models import HeritageSite, ClimateEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_open_meteo(
    site_id: int,
    lat: float,
    lon: float,
    start_date: str = CLIMATE_START_DATE,
    end_date: str = CLIMATE_END_DATE
) -> Optional[pd.DataFrame]:
    """
    Fetch climate data from Open-Meteo Archive API for a single site.
    
    Args:
        site_id: Heritage site database ID
        lat: Site latitude (WGS84)
        lon: Site longitude (WGS84)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    
    Returns:
        DataFrame with daily climate data or None if error
    """
    try:
        # Build API request
        params = {
            'latitude': lat,
            'longitude': lon,
            'start_date': start_date,
            'end_date': end_date,
            'daily': ','.join(OPEN_METEO_DAILY_VARS),
            'timezone': 'UTC',
        }
        
        logger.debug(f"Fetching Open-Meteo data for site {site_id} at ({lat}, {lon})")
        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Check for errors in response
        if 'error' in data:
            logger.error(f"Open-Meteo API error for site {site_id}: {data['reason']}")
            return None
        
        # Parse daily data
        if 'daily' not in data:
            logger.warning(f"No daily data in Open-Meteo response for site {site_id}")
            return None
        
        daily = data['daily']
        
        # Create DataFrame
        df = pd.DataFrame({
            'site_id': site_id,
            'event_date': pd.to_datetime(daily['time']),
            'source': 'open_meteo',
            'temp_max_c': daily.get('temperature_2m_max'),
            'temp_min_c': daily.get('temperature_2m_min'),
            'temp_mean_c': daily.get('temperature_2m_mean'),
            'precipitation_mm': daily.get('precipitation_sum'),
            'wind_max_ms': daily.get('windspeed_10m_max'),
            'wind_gust_ms': daily.get('windgusts_10m_max'),
            'solar_radiation_kwh': None,  # Not available in this endpoint
            'humidity_pct': None,  # Not available in this endpoint
        })
        
        # Add geometry
        df['geom'] = Point(lon, lat)
        
        logger.info(f"Fetched {len(df)} Open-Meteo records for site {site_id}")
        return df
        
    except requests.RequestException as e:
        logger.error(f"HTTP error fetching Open-Meteo data for site {site_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching Open-Meteo data for site {site_id}: {e}")
        return None


def fetch_nasa_power(
    site_id: int,
    lat: float,
    lon: float,
    start_date: str = CLIMATE_START_DATE,
    end_date: str = CLIMATE_END_DATE
) -> Optional[pd.DataFrame]:
    """
    Fetch climate data from NASA POWER API for a single site.
    
    Args:
        site_id: Heritage site database ID
        lat: Site latitude (WGS84)
        lon: Site longitude (WGS84)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    
    Returns:
        DataFrame with daily climate data or None if error
    """
    try:
        # Convert date format for NASA POWER (YYYYMMDD)
        start = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y%m%d')
        end = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y%m%d')
        
        # Build API request
        params = {
            'parameters': NASA_POWER_PARAMS,
            'community': 'RE',
            'longitude': lon,
            'latitude': lat,
            'start': start,
            'end': end,
            'format': 'JSON',
        }
        
        logger.debug(f"Fetching NASA POWER data for site {site_id} at ({lat}, {lon})")
        response = requests.get(NASA_POWER_URL, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Check for errors
        if 'messages' in data:
            logger.warning(f"NASA POWER messages for site {site_id}: {data['messages']}")
        
        # Parse parameters data
        if 'properties' not in data or 'parameter' not in data['properties']:
            logger.error(f"Invalid NASA POWER response for site {site_id}")
            return None
        
        params_data = data['properties']['parameter']
        
        # Build DataFrame
        records = []
        
        # Get all dates from T2M parameter (temperature is always available)
        if 'T2M' not in params_data:
            logger.error(f"No temperature data in NASA POWER response for site {site_id}")
            return None
        
        dates = list(params_data['T2M'].keys())
        
        for date_str in dates:
            # NASA POWER uses -999 for missing values
            record = {
                'site_id': site_id,
                'event_date': datetime.strptime(date_str, '%Y%m%d').date(),
                'source': 'nasa_power',
                'temp_mean_c': params_data.get('T2M', {}).get(date_str),
                'temp_max_c': None,  # Not directly available, use mean
                'temp_min_c': None,  # Not directly available, use mean
                'precipitation_mm': params_data.get('PRECTOTCORR', {}).get(date_str),
                'wind_max_ms': params_data.get('WS10M', {}).get(date_str),
                'wind_gust_ms': None,  # Not available
                'solar_radiation_kwh': params_data.get('ALLSKY_SFC_SW_DWN', {}).get(date_str),
                'humidity_pct': params_data.get('RH2M', {}).get(date_str),
            }
            
            # Replace -999 (missing value indicator) with None
            for key, value in record.items():
                if value == -999 or value == '-999':
                    record[key] = None
            
            # Add geometry
            record['geom'] = Point(lon, lat)
            
            records.append(record)
        
        df = pd.DataFrame(records)
        logger.info(f"Fetched {len(df)} NASA POWER records for site {site_id}")
        return df
        
    except requests.RequestException as e:
        logger.error(f"HTTP error fetching NASA POWER data for site {site_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching NASA POWER data for site {site_id}: {e}")
        return None


def upsert_climate_data(df: pd.DataFrame, session: Session) -> int:
    """
    Insert or update climate data in the climate_events table.
    
    Uses ON CONFLICT to handle duplicates based on (site_id, event_date, source).
    
    Args:
        df: DataFrame with climate data
        session: SQLAlchemy session
    
    Returns:
        Number of rows inserted/updated
    """
    if df.empty:
        return 0
    
    try:
        # Convert to GeoDataFrame
        gdf = gpd.GeoDataFrame(df, geometry='geom', crs='EPSG:4326')
        
        # Use to_postgis for bulk insert
        # Note: This will fail on duplicates, so we handle via SQL instead
        count = len(gdf)
        
        # Insert records one by one with UPSERT
        inserted = 0
        for _, row in gdf.iterrows():
            try:
                # Build INSERT ... ON CONFLICT query
                query = text("""
                    INSERT INTO unesco_risk.climate_events
                    (site_id, event_date, source, temp_max_c, temp_min_c, temp_mean_c,
                     precipitation_mm, wind_max_ms, wind_gust_ms, solar_radiation_kwh,
                     humidity_pct, geom)
                    VALUES
                    (:site_id, :event_date, :source, :temp_max_c, :temp_min_c, :temp_mean_c,
                     :precipitation_mm, :wind_max_ms, :wind_gust_ms, :solar_radiation_kwh,
                     :humidity_pct, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                    ON CONFLICT (site_id, event_date, source)
                    DO UPDATE SET
                        temp_max_c = EXCLUDED.temp_max_c,
                        temp_min_c = EXCLUDED.temp_min_c,
                        temp_mean_c = EXCLUDED.temp_mean_c,
                        precipitation_mm = EXCLUDED.precipitation_mm,
                        wind_max_ms = EXCLUDED.wind_max_ms,
                        wind_gust_ms = EXCLUDED.wind_gust_ms,
                        solar_radiation_kwh = EXCLUDED.solar_radiation_kwh,
                        humidity_pct = EXCLUDED.humidity_pct
                """)
                
                session.execute(query, {
                    'site_id': int(row['site_id']),
                    'event_date': row['event_date'],
                    'source': row['source'],
                    'temp_max_c': float(row['temp_max_c']) if pd.notna(row['temp_max_c']) else None,
                    'temp_min_c': float(row['temp_min_c']) if pd.notna(row['temp_min_c']) else None,
                    'temp_mean_c': float(row['temp_mean_c']) if pd.notna(row['temp_mean_c']) else None,
                    'precipitation_mm': float(row['precipitation_mm']) if pd.notna(row['precipitation_mm']) else None,
                    'wind_max_ms': float(row['wind_max_ms']) if pd.notna(row['wind_max_ms']) else None,
                    'wind_gust_ms': float(row['wind_gust_ms']) if pd.notna(row['wind_gust_ms']) else None,
                    'solar_radiation_kwh': float(row['solar_radiation_kwh']) if pd.notna(row['solar_radiation_kwh']) else None,
                    'humidity_pct': float(row['humidity_pct']) if pd.notna(row['humidity_pct']) else None,
                    'lon': row.geometry.x,
                    'lat': row.geometry.y,
                })
                inserted += 1
            except Exception as e:
                logger.warning(f"Error inserting climate record: {e}")
                continue
        
        session.commit()
        logger.info(f"Inserted/updated {inserted} climate records")
        return inserted
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error inserting climate data: {e}")
        return 0


def validate_date_ranges(df: pd.DataFrame) -> Dict[str, any]:
    """
    Validate date ranges in climate data.
    
    Args:
        df: Climate DataFrame
    
    Returns:
        Dictionary with validation statistics
    """
    if df.empty:
        return {'valid': False, 'reason': 'Empty dataset'}
    
    df_sorted = df.sort_values('event_date')
    dates = pd.to_datetime(df_sorted['event_date'])
    
    # Check for large gaps (> 7 days)
    gaps = dates.diff()
    large_gaps = gaps[gaps > pd.Timedelta(days=7)]
    
    validation = {
        'valid': True,
        'total_records': len(df),
        'start_date': dates.min(),
        'end_date': dates.max(),
        'num_large_gaps': len(large_gaps),
        'largest_gap_days': gaps.max().days if not gaps.empty else 0,
    }
    
    if len(large_gaps) > 0:
        logger.warning(f"Found {len(large_gaps)} gaps > 7 days in climate data")
        logger.warning(f"Largest gap: {gaps.max().days} days")
    
    return validation


def fetch_all_climate(
    session: Session,
    source: str = 'both',
    test_mode: bool = False,
    limit: Optional[int] = None,
    verbose: bool = False
) -> Dict[str, int]:
    """
    Fetch climate data for all heritage sites.
    
    Args:
        session: SQLAlchemy session
        source: Data source ('open_meteo', 'nasa_power', or 'both')
        test_mode: If True, only process first 5 sites
        limit: Optional limit on number of sites
        verbose: Enable verbose logging
    
    Returns:
        Dictionary with statistics
    """
    if verbose:
        logger.setLevel(logging.DEBUG)
    
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
    
    logger.info(f"Fetching climate data for {total_sites} sites (source: {source})")
    
    # Statistics
    stats = {
        'total_sites': total_sites,
        'sites_processed': 0,
        'sites_failed': 0,
        'open_meteo_records': 0,
        'nasa_power_records': 0,
        'total_records': 0,
    }
    
    # Process each site
    for site in tqdm(sites, desc="Fetching climate data"):
        try:
            # Extract coordinates
            geom_wkt = session.scalar(text(
                f"SELECT ST_AsText(geom) FROM unesco_risk.heritage_sites WHERE id = {site.id}"
            ))
            lat, lon = parse_point_wkt(geom_wkt)
            
            # Fetch from Open-Meteo
            if source in ['open_meteo', 'both']:
                om_df = fetch_open_meteo(site.id, lat, lon)
                if om_df is not None and not om_df.empty:
                    count = upsert_climate_data(om_df, session)
                    stats['open_meteo_records'] += count
                    stats['total_records'] += count
                
                # Rate limiting for Open-Meteo
                time.sleep(0.5)
            
            # Fetch from NASA POWER
            if source in ['nasa_power', 'both']:
                nasa_df = fetch_nasa_power(site.id, lat, lon)
                if nasa_df is not None and not nasa_df.empty:
                    count = upsert_climate_data(nasa_df, session)
                    stats['nasa_power_records'] += count
                    stats['total_records'] += count
                
                # Rate limiting for NASA POWER (~30 req/min = 2s between requests)
                time.sleep(2)
            
            stats['sites_processed'] += 1
            
        except Exception as e:
            logger.error(f"Failed to process site {site.id} ({site.name}): {e}")
            stats['sites_failed'] += 1
            continue
    
    logger.info("=" * 60)
    logger.info("CLIMATE DATA FETCH COMPLETE")
    logger.info(f"Total sites: {stats['total_sites']}")
    logger.info(f"Sites processed: {stats['sites_processed']}")
    logger.info(f"Sites failed: {stats['sites_failed']}")
    logger.info(f"Open-Meteo records: {stats['open_meteo_records']}")
    logger.info(f"NASA POWER records: {stats['nasa_power_records']}")
    logger.info(f"Total climate records: {stats['total_records']}")
    logger.info("=" * 60)
    
    return stats


def parse_point_wkt(wkt_str: str) -> tuple:
    """Parse WKT POINT string to extract lat/lon."""
    geom = wkt.loads(wkt_str)
    return geom.y, geom.x  # lat, lon


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch climate data for UNESCO heritage sites"
    )
    parser.add_argument(
        '--source',
        choices=['open_meteo', 'nasa_power', 'both'],
        default='both',
        help='Data source to fetch from'
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
        # Run climate fetch
        stats = fetch_all_climate(
            session=session,
            source=args.source,
            test_mode=args.test,
            limit=args.limit,
            verbose=args.verbose
        )
        
        # Print summary
        print("\n" + "=" * 60)
        print("CLIMATE ETL SUMMARY")
        print("=" * 60)
        print(f"Sites processed: {stats['sites_processed']}/{stats['total_sites']}")
        print(f"Sites failed: {stats['sites_failed']}")
        print(f"Open-Meteo records: {stats['open_meteo_records']}")
        print(f"NASA POWER records: {stats['nasa_power_records']}")
        print(f"Total records: {stats['total_records']}")
        print("=" * 60)
        
    finally:
        session.close()


if __name__ == '__main__':
    main()
