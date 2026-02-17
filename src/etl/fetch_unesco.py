"""
UNESCO World Heritage Sites ETL module.

Fetches UNESCO World Heritage Sites data from the official API,
filters for European sites, and stores them in PostGIS database.

Supports both XML (primary) and JSON (fallback) endpoints.
"""

import argparse
import logging
import sys
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from datetime import datetime

import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from tqdm import tqdm
from sqlalchemy.dialects.postgresql import insert

from config.settings import (
    UNESCO_XML_URL,
    UNESCO_JSON_URL,
    EUROPE_ISO_CODES,
    EUROPE_BBOX,
    SRC_CRS
)
from src.db.connection import get_session, get_engine
from src.db.models import HeritageSite

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_xml_data(url: str = UNESCO_XML_URL, timeout: int = 30) -> Optional[str]:
    """
    Fetch UNESCO sites data from XML endpoint.
    
    Args:
        url: UNESCO XML endpoint URL
        timeout: Request timeout in seconds
        
    Returns:
        Raw XML string if successful, None otherwise
    """
    try:
        logger.info(f"Fetching data from {url}")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        logger.info(f"✓ Successfully fetched XML data ({len(response.content)} bytes)")
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"✗ Failed to fetch XML data: {e}")
        return None


def fetch_json_data(url: str = UNESCO_JSON_URL, timeout: int = 30) -> Optional[List[Dict]]:
    """
    Fetch UNESCO sites data from JSON endpoint (fallback).
    
    Args:
        url: UNESCO JSON endpoint URL
        timeout: Request timeout in seconds
        
    Returns:
        List of site dictionaries if successful, None otherwise
    """
    try:
        logger.info(f"Fetching data from JSON fallback: {url}")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        logger.info(f"✓ Successfully fetched JSON data ({len(data)} sites)")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"✗ Failed to fetch JSON data: {e}")
        return None


def parse_xml_to_records(xml_string: str) -> List[Dict]:
    """
    Parse UNESCO XML data into list of site dictionaries.
    
    Args:
        xml_string: Raw XML string from UNESCO API
        
    Returns:
        List of dictionaries, each representing a heritage site
    """
    records = []
    
    try:
        root = ET.fromstring(xml_string)
        
        # Find all <row> elements (each represents a site)
        for row in root.findall('.//row'):
            try:
                # Extract fields with fallback defaults
                whc_id = row.findtext('id_number')
                if not whc_id:
                    continue  # Skip if no ID
                    
                # Get coordinates
                latitude = row.findtext('latitude')
                longitude = row.findtext('longitude')
                
                # Skip sites without valid coordinates
                if not latitude or not longitude:
                    logger.warning(f"Skipping site {whc_id}: missing coordinates")
                    continue
                
                try:
                    lat = float(latitude)
                    lon = float(longitude)
                except (ValueError, TypeError):
                    logger.warning(f"Skipping site {whc_id}: invalid coordinates")
                    continue
                
                # Get ISO codes (can be multiple, comma-separated)
                iso_code = row.findtext('iso_code', '').strip()
                
                # Extract category
                category = row.findtext('category', '').strip()
                
                # Parse date inscribed
                date_inscribed_str = row.findtext('date_inscribed', '').strip()
                date_inscribed = None
                if date_inscribed_str:
                    try:
                        date_inscribed = int(date_inscribed_str)
                    except ValueError:
                        pass
                
                # Parse danger status
                danger_str = row.findtext('danger', '0').strip()
                in_danger = danger_str in ('1', 'true', 'True', 'TRUE')
                
                # Parse area
                area_str = row.findtext('area_hectares', '0').strip()
                area_hectares = 0.0
                if area_str:
                    try:
                        area_hectares = float(area_str)
                    except ValueError:
                        area_hectares = 0.0
                
                # Build record
                record = {
                    'whc_id': int(whc_id),
                    'name': row.findtext('site', '').strip() or row.findtext('name', '').strip(),
                    'category': category if category in ('Cultural', 'Natural', 'Mixed') else None,
                    'date_inscribed': date_inscribed,
                    'country': row.findtext('states', '').strip() or row.findtext('state', '').strip(),
                    'iso_code': iso_code,
                    'region': row.findtext('region', '').strip(),
                    'criteria': row.findtext('criteria_txt', '').strip() or row.findtext('criteria', '').strip(),
                    'in_danger': in_danger,
                    'area_hectares': area_hectares,
                    'description': row.findtext('short_description', '').strip() or row.findtext('description', '').strip(),
                    'latitude': lat,
                    'longitude': lon,
                }
                
                records.append(record)
                
            except Exception as e:
                logger.warning(f"Error parsing site record: {e}")
                continue
        
        logger.info(f"✓ Parsed {len(records)} sites from XML")
        
    except ET.ParseError as e:
        logger.error(f"✗ XML parsing error: {e}")
        return []
    
    return records


def parse_json_to_records(json_data: List[Dict]) -> List[Dict]:
    """
    Parse UNESCO JSON data into standardized site dictionaries.
    
    Args:
        json_data: List of site dictionaries from JSON API
        
    Returns:
        List of standardized dictionaries
    """
    records = []
    
    for item in json_data:
        try:
            # Get coordinates
            latitude = item.get('latitude')
            longitude = item.get('longitude')
            
            if not latitude or not longitude:
                continue
            
            try:
                lat = float(latitude)
                lon = float(longitude)
            except (ValueError, TypeError):
                continue
            
            whc_id = item.get('id_number') or item.get('id')
            if not whc_id:
                continue
            
            record = {
                'whc_id': int(whc_id),
                'name': item.get('site') or item.get('name', ''),
                'category': item.get('category'),
                'date_inscribed': int(item.get('date_inscribed')) if item.get('date_inscribed') else None,
                'country': item.get('states') or item.get('state', ''),
                'iso_code': item.get('iso_code', ''),
                'region': item.get('region', ''),
                'criteria': item.get('criteria_txt') or item.get('criteria', ''),
                'in_danger': bool(item.get('danger', 0)),
                'area_hectares': float(item.get('area_hectares', 0)),
                'description': item.get('short_description') or item.get('description', ''),
                'latitude': lat,
                'longitude': lon,
            }
            
            records.append(record)
            
        except Exception as e:
            logger.warning(f"Error parsing JSON record: {e}")
            continue
    
    logger.info(f"✓ Parsed {len(records)} sites from JSON")
    return records


def filter_european_sites(records: List[Dict]) -> List[Dict]:
    """
    Filter records to include only European heritage sites.
    
    Args:
        records: List of all site dictionaries
        
    Returns:
        List of European site dictionaries
    """
    european_sites = []
    
    for record in records:
        # Check ISO codes (can be comma-separated for transboundary sites)
        iso_codes = record.get('iso_code', '').split(',')
        iso_codes = [code.strip().upper() for code in iso_codes if code.strip()]
        
        # Check if any ISO code is in European set
        is_european_iso = any(code in EUROPE_ISO_CODES for code in iso_codes)
        
        # Also check geographic bounds as backup
        lat = record.get('latitude', 0)
        lon = record.get('longitude', 0)
        is_in_bbox = (
            EUROPE_BBOX['min_lat'] <= lat <= EUROPE_BBOX['max_lat'] and
            EUROPE_BBOX['min_lon'] <= lon <= EUROPE_BBOX['max_lon']
        )
        
        if is_european_iso or is_in_bbox:
            european_sites.append(record)
    
    logger.info(f"✓ Filtered to {len(european_sites)} European sites (from {len(records)} total)")
    return european_sites


def validate_records(records: List[Dict]) -> tuple[List[Dict], Dict]:
    """
    Validate site records for data quality.
    
    Args:
        records: List of site dictionaries
        
    Returns:
        Tuple of (valid_records, validation_report)
    """
    validation_report = {
        'total_records': len(records),
        'valid_records': 0,
        'invalid_records': 0,
        'duplicate_whc_ids': [],
        'invalid_geometries': [],
        'invalid_categories': [],
        'out_of_bounds': [],
    }
    
    valid_records = []
    seen_whc_ids = set()
    valid_categories = {'Cultural', 'Natural', 'Mixed'}
    
    for record in records:
        is_valid = True
        
        # Check for duplicate WHC ID
        whc_id = record.get('whc_id')
        if whc_id in seen_whc_ids:
            validation_report['duplicate_whc_ids'].append(whc_id)
            is_valid = False
        else:
            seen_whc_ids.add(whc_id)
        
        # Validate coordinates
        lat = record.get('latitude', 0)
        lon = record.get('longitude', 0)
        
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            validation_report['invalid_geometries'].append(whc_id)
            is_valid = False
        
        # Check bounds for European sites
        if not (EUROPE_BBOX['min_lat'] <= lat <= EUROPE_BBOX['max_lat'] and
                EUROPE_BBOX['min_lon'] <= lon <= EUROPE_BBOX['max_lon']):
            # This is a warning, not necessarily invalid
            validation_report['out_of_bounds'].append(whc_id)
        
        # Validate category
        category = record.get('category')
        if category and category not in valid_categories:
            validation_report['invalid_categories'].append(whc_id)
            # Don't mark as invalid, just warning
        
        if is_valid:
            valid_records.append(record)
            validation_report['valid_records'] += 1
        else:
            validation_report['invalid_records'] += 1
    
    return valid_records, validation_report


def create_geodataframe(records: List[Dict]) -> gpd.GeoDataFrame:
    """
    Convert site records to GeoDataFrame with Point geometries.
    
    Args:
        records: List of site dictionaries
        
    Returns:
        GeoDataFrame with EPSG:4326 CRS
    """
    # Create DataFrame
    df = pd.DataFrame(records)
    
    # Create Point geometries
    geometry = [Point(row['longitude'], row['latitude']) for _, row in df.iterrows()]
    
    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(
        df.drop(['latitude', 'longitude'], axis=1),
        geometry=geometry,
        crs=f"EPSG:{SRC_CRS}"
    )
    
    # Validate all geometries
    invalid_geoms = ~gdf.geometry.is_valid
    if invalid_geoms.any():
        logger.warning(f"Found {invalid_geoms.sum()} invalid geometries, attempting to fix...")
        gdf.loc[invalid_geoms, 'geometry'] = gdf.loc[invalid_geoms, 'geometry'].buffer(0)
    
    logger.info(f"✓ Created GeoDataFrame with {len(gdf)} sites")
    return gdf


def upsert_to_database(gdf: gpd.GeoDataFrame, dry_run: bool = False) -> int:
    """
    Insert or update heritage sites in the database.
    
    Uses PostgreSQL UPSERT (INSERT ... ON CONFLICT) to handle duplicates.
    
    Args:
        gdf: GeoDataFrame with heritage sites
        dry_run: If True, don't write to database
        
    Returns:
        Number of records inserted/updated
    """
    if dry_run:
        logger.info(f"DRY RUN: Would insert/update {len(gdf)} records")
        return len(gdf)
    
    session = get_session()
    count = 0
    
    try:
        logger.info(f"Inserting/updating {len(gdf)} sites to database...")
        
        for idx, row in tqdm(gdf.iterrows(), total=len(gdf), desc="Upserting sites"):
            # Prepare data for insert
            site_data = {
                'whc_id': int(row['whc_id']),
                'name': row['name'][:500] if row['name'] else None,  # Truncate to fit column
                'category': row['category'],
                'date_inscribed': row['date_inscribed'],
                'country': row['country'][:200] if row['country'] else None,
                'iso_code': row['iso_code'][:20] if row['iso_code'] else None,
                'region': row['region'][:100] if row['region'] else None,
                'criteria': row['criteria'][:100] if row['criteria'] else None,
                'in_danger': bool(row['in_danger']),
                'area_hectares': float(row['area_hectares']) if pd.notna(row['area_hectares']) else None,
                'description': row['description'],
                'geom': f'SRID={SRC_CRS};POINT({row.geometry.x} {row.geometry.y})',
            }
            
            # Create UPSERT statement
            stmt = insert(HeritageSite.__table__).values(**site_data)
            
            # On conflict, update all fields except id and whc_id
            stmt = stmt.on_conflict_do_update(
                index_elements=['whc_id'],
                set_={
                    'name': stmt.excluded.name,
                    'category': stmt.excluded.category,
                    'date_inscribed': stmt.excluded.date_inscribed,
                    'country': stmt.excluded.country,
                    'iso_code': stmt.excluded.iso_code,
                    'region': stmt.excluded.region,
                    'criteria': stmt.excluded.criteria,
                    'in_danger': stmt.excluded.in_danger,
                    'area_hectares': stmt.excluded.area_hectares,
                    'description': stmt.excluded.description,
                    'geom': stmt.excluded.geom,
                    'updated_at': datetime.now(),
                }
            )
            
            session.execute(stmt)
            count += 1
        
        session.commit()
        logger.info(f"✓ Successfully inserted/updated {count} sites")
        
    except Exception as e:
        session.rollback()
        logger.error(f"✗ Database error: {e}")
        raise
    finally:
        session.close()
    
    return count


def fetch_unesco_sites(europe_only: bool = True, dry_run: bool = False, 
                       use_json: bool = False) -> Optional[gpd.GeoDataFrame]:
    """
    Main function to fetch, parse, and store UNESCO heritage sites.
    
    Args:
        europe_only: If True, filter to European sites only
        dry_run: If True, don't write to database
        use_json: If True, use JSON endpoint instead of XML
        
    Returns:
        GeoDataFrame of heritage sites if successful, None otherwise
    """
    logger.info("=" * 70)
    logger.info("UNESCO Heritage Sites ETL Process")
    logger.info("=" * 70)
    
    # Step 1: Fetch data
    records = []
    
    if use_json:
        json_data = fetch_json_data()
        if json_data:
            records = parse_json_to_records(json_data)
    else:
        xml_data = fetch_xml_data()
        if xml_data:
            records = parse_xml_to_records(xml_data)
        else:
            # Fallback to JSON
            logger.warning("XML fetch failed, falling back to JSON endpoint...")
            json_data = fetch_json_data()
            if json_data:
                records = parse_json_to_records(json_data)
    
    if not records:
        logger.error("✗ Failed to fetch any data")
        return None
    
    # Step 2: Filter to Europe if requested
    if europe_only:
        records = filter_european_sites(records)
    
    # Step 3: Validate records
    valid_records, validation_report = validate_records(records)
    
    logger.info("\n--- Validation Report ---")
    logger.info(f"Total records: {validation_report['total_records']}")
    logger.info(f"Valid records: {validation_report['valid_records']}")
    logger.info(f"Invalid records: {validation_report['invalid_records']}")
    if validation_report['duplicate_whc_ids']:
        logger.warning(f"Duplicate WHC IDs: {validation_report['duplicate_whc_ids'][:5]}")
    if validation_report['invalid_geometries']:
        logger.warning(f"Invalid geometries: {validation_report['invalid_geometries'][:5]}")
    if validation_report['out_of_bounds']:
        logger.info(f"Out of Europe bounds: {len(validation_report['out_of_bounds'])} sites")
    
    if not valid_records:
        logger.error("✗ No valid records found")
        return None
    
    # Step 4: Create GeoDataFrame
    gdf = create_geodataframe(valid_records)
    
    # Step 5: Print sample
    logger.info("\n--- Sample Records (first 5) ---")
    sample_cols = ['whc_id', 'name', 'country', 'category', 'date_inscribed']
    logger.info("\n" + gdf[sample_cols].head(5).to_string())
    
    # Step 6: Category distribution
    logger.info("\n--- Category Distribution ---")
    logger.info("\n" + gdf['category'].value_counts().to_string())
    
    # Step 7: Country distribution (top 10)
    logger.info("\n--- Top 10 Countries ---")
    logger.info("\n" + gdf['country'].value_counts().head(10).to_string())
    
    # Step 8: Upsert to database
    if not dry_run:
        count = upsert_to_database(gdf, dry_run=False)
        logger.info(f"\n✓ ETL process complete! {count} sites stored in database.")
    else:
        logger.info(f"\n✓ DRY RUN complete! {len(gdf)} sites would be stored.")
    
    logger.info("=" * 70)
    
    return gdf


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Fetch and store UNESCO World Heritage Sites data'
    )
    parser.add_argument(
        '--all', 
        action='store_true',
        help='Fetch all sites worldwide (default: Europe only)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Fetch and parse data without writing to database'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Use JSON endpoint instead of XML'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        gdf = fetch_unesco_sites(
            europe_only=not args.all,
            dry_run=args.dry_run,
            use_json=args.json
        )
        
        if gdf is not None:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
