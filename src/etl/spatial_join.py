"""
CRS Transformation & Spatial Join Module

This module handles spatial transformations and joins between heritage sites
and hazard/urban features. All distance calculations use EPSG:3035 (ETRS89/LAEA Europe)
for accurate metric computations.

Author: UNESCO Risk Modeling Project
Phase: 5 - CRS Transformation & Spatial Join
"""

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point
from sqlalchemy import text
from tqdm import tqdm
import logging
from typing import Dict, List, Tuple, Optional

from src.db.connection import get_session
from src.db.models import (
    HeritageSite, UrbanFeature, EarthquakeEvent, 
    FireEvent, FloodZone, ClimateEvent
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# CRS Constants
CRS_WGS84 = "EPSG:4326"  # Storage CRS
CRS_ETRS89_LAEA = "EPSG:3035"  # Computation CRS for Europe

# Buffer distances in meters
BUFFER_DISTANCES = {
    'urban': 5000,      # 5 km for urban features
    'fire': 25000,      # 25 km for fire events  
    'earthquake': 50000,  # 50 km for earthquakes
    'flood': 50000,     # 50 km for flood zones
    'max_distance': 100000  # 100 km maximum for nearest neighbor search
}


def create_buffers(
    sites_gdf: gpd.GeoDataFrame,
    distances_m: List[int] = [5000, 10000, 25000, 50000]
) -> Dict[int, gpd.GeoDataFrame]:
    """
    Create concentric buffers around each heritage site.
    
    Buffers are created in EPSG:3035 for accurate metric distances,
    then transformed back to EPSG:4326 for storage.
    
    Args:
        sites_gdf: GeoDataFrame of heritage sites in EPSG:4326
        distances_m: List of buffer distances in meters
        
    Returns:
        Dictionary mapping distance -> buffered GeoDataFrame
        
    Example:
        >>> sites = gpd.read_postgis("SELECT * FROM heritage_sites", engine)
        >>> buffers = create_buffers(sites, [5000, 10000])
        >>> buffer_5km = buffers[5000]
    """
    logger.info(f"Creating {len(distances_m)} buffer zones for {len(sites_gdf)} sites")
    
    # Project to EPSG:3035 for metric buffer
    sites_proj = sites_gdf.to_crs(CRS_ETRS89_LAEA)
    
    buffers = {}
    for dist in distances_m:
        logger.debug(f"Creating {dist}m buffer...")
        buffer_gdf = sites_proj.copy()
        buffer_gdf["geometry"] = sites_proj.buffer(dist)
        buffer_gdf["buffer_m"] = dist
        
        # Transform back to WGS84 for storage
        buffers[dist] = buffer_gdf.to_crs(CRS_WGS84)
        
    logger.info(f"Created {len(buffers)} buffer zones successfully")
    return buffers


def join_urban_to_sites(
    urban_gdf: gpd.GeoDataFrame,
    sites_gdf: gpd.GeoDataFrame,
    buffer_m: int = 5000
) -> gpd.GeoDataFrame:
    """
    Spatial join: which urban features fall within site buffer zones.
    
    Performs an inner join to find urban features within the specified buffer
    distance of each heritage site. Calculates accurate metric distances in EPSG:3035.
    
    Args:
        urban_gdf: GeoDataFrame of OSM urban features in EPSG:4326
        sites_gdf: GeoDataFrame of heritage sites in EPSG:4326
        buffer_m: Buffer distance in meters (default: 5000)
        
    Returns:
        GeoDataFrame with joined urban features including:
        - nearest_site_id: ID of the nearest heritage site
        - distance_to_site_m: Distance in meters to the site
        
    Example:
        >>> urban = gpd.read_postgis("SELECT * FROM urban_features", engine)
        >>> sites = gpd.read_postgis("SELECT * FROM heritage_sites", engine)
        >>> joined = join_urban_to_sites(urban, sites, buffer_m=5000)
    """
    logger.info(f"Joining {len(urban_gdf)} urban features to {len(sites_gdf)} sites (buffer={buffer_m}m)")
    
    if urban_gdf.empty or sites_gdf.empty:
        logger.warning("Empty input GeoDataFrame, returning empty result")
        return gpd.GeoDataFrame()
    
    # Project both to EPSG:3035 for accurate metric calculations
    urban_proj = urban_gdf.to_crs(CRS_ETRS89_LAEA)
    sites_proj = sites_gdf.to_crs(CRS_ETRS89_LAEA)
    
    # Create buffer zones around sites
    sites_buffer = sites_proj.copy()
    sites_buffer["geometry"] = sites_proj.buffer(buffer_m)
    
    # Spatial join: find urban features within buffers
    logger.debug("Performing spatial join...")
    joined = gpd.sjoin(
        urban_proj, 
        sites_buffer, 
        how="inner", 
        predicate="within"
    )
    
    if joined.empty:
        logger.warning("No urban features found within buffer zones")
        return joined.to_crs(CRS_WGS84)
    
    # Calculate distance from each feature to its nearest site centroid
    logger.debug("Calculating distances to site centroids...")
    
    # Get site geometries for the joined features
    site_geoms = sites_proj.loc[joined.index_right, "geometry"].values
    
    # Calculate distances
    joined["distance_to_site_m"] = joined.geometry.distance(
        gpd.GeoSeries(site_geoms, crs=CRS_ETRS89_LAEA)
    )
    
    # Add site ID reference
    joined["nearest_site_id"] = sites_proj.loc[joined.index_right, "id"].values
    
    logger.info(f"Successfully joined {len(joined)} urban features")
    
    # Transform back to WGS84
    return joined.to_crs(CRS_WGS84)


def join_hazards_to_sites(
    hazard_gdf: gpd.GeoDataFrame,
    sites_gdf: gpd.GeoDataFrame,
    max_distance_m: int = 100000,
    hazard_type: str = "hazard"
) -> gpd.GeoDataFrame:
    """
    Nearest-site spatial join for point hazards (earthquakes, fires, floods).
    
    Uses sjoin_nearest to link each hazard event to its closest heritage site,
    with a maximum search distance constraint.
    
    Args:
        hazard_gdf: GeoDataFrame of hazard events in EPSG:4326
        sites_gdf: GeoDataFrame of heritage sites in EPSG:4326
        max_distance_m: Maximum distance for nearest neighbor search (meters)
        hazard_type: Type of hazard for logging (e.g., 'earthquake', 'fire')
        
    Returns:
        GeoDataFrame with joined hazard events including:
        - nearest_site_id: ID of the nearest heritage site
        - distance_to_site_m: Distance in meters
        - distance_to_site_km: Distance in kilometers
        
    Example:
        >>> earthquakes = gpd.read_postgis("SELECT * FROM earthquake_events", engine)
        >>> sites = gpd.read_postgis("SELECT * FROM heritage_sites", engine)
        >>> joined = join_hazards_to_sites(earthquakes, sites, max_distance_m=50000)
    """
    logger.info(f"Joining {len(hazard_gdf)} {hazard_type} events to {len(sites_gdf)} sites "
                f"(max_distance={max_distance_m}m)")
    
    if hazard_gdf.empty or sites_gdf.empty:
        logger.warning("Empty input GeoDataFrame, returning empty result")
        return gpd.GeoDataFrame()
    
    # Project both to EPSG:3035 for metric distance calculations
    hazard_proj = hazard_gdf.to_crs(CRS_ETRS89_LAEA)
    sites_proj = sites_gdf.to_crs(CRS_ETRS89_LAEA)
    
    # Perform nearest neighbor spatial join
    logger.debug("Performing nearest neighbor spatial join...")
    joined = gpd.sjoin_nearest(
        hazard_proj,
        sites_proj,
        how="left",
        max_distance=max_distance_m,
        distance_col="distance_to_site_m"
    )
    
    # Filter out events beyond max distance (sjoin_nearest may include them with NaN)
    initial_count = len(joined)
    joined = joined[joined["distance_to_site_m"].notna()]
    filtered_count = initial_count - len(joined)
    
    if filtered_count > 0:
        logger.info(f"Filtered {filtered_count} {hazard_type} events beyond {max_distance_m}m")
    
    if joined.empty:
        logger.warning(f"No {hazard_type} events found within {max_distance_m}m of any site")
        return joined.to_crs(CRS_WGS84)
    
    # Add distance in kilometers
    joined["distance_to_site_km"] = joined["distance_to_site_m"] / 1000.0
    
    # Add site ID reference (from the join)
    joined["nearest_site_id"] = sites_proj.loc[joined.index_right, "id"].values
    
    logger.info(f"Successfully joined {len(joined)} {hazard_type} events")
    
    # Transform back to WGS84
    return joined.to_crs(CRS_WGS84)


def update_urban_features_distances(session, verbose: bool = True) -> int:
    """
    Update distance_to_site_m for all urban features using PostGIS.
    nearest_site_id is already populated by the OSM ETL.
    
    Uses ST_Transform + ST_Distance for accurate metric distance in EPSG:3035.
    
    Args:
        session: Database session
        verbose: Print progress information
        
    Returns:
        Number of urban features updated
    """
    logger.info("Updating urban features distances using PostGIS...")
    
    update_sql = text("""
        UPDATE unesco_risk.urban_features uf
        SET distance_to_site_m = ST_Distance(
                ST_Transform(uf.geom, 3035),
                ST_Transform(hs.geom, 3035)
            )
        FROM unesco_risk.heritage_sites hs
        WHERE uf.nearest_site_id = hs.id
          AND uf.nearest_site_id IS NOT NULL;
    """)
    
    result = session.execute(update_sql)
    updated_count = result.rowcount
    session.commit()
    
    logger.info(f"Updated distances for {updated_count} urban features")
    return updated_count


def update_earthquake_distances(session, verbose: bool = True) -> int:
    """
    Update nearest_site_id and distance_to_site_km for all earthquake events
    using PostGIS lateral cross-join (nearest neighbor).
    
    Args:
        session: Database session
        verbose: Print progress information
        
    Returns:
        Number of earthquake events updated
    """
    logger.info("Updating earthquake events with PostGIS nearest-neighbor join...")
    
    update_sql = text("""
        WITH nearest AS (
            SELECT DISTINCT ON (ee.id)
                ee.id AS event_id,
                hs.id AS site_id,
                ST_Distance(
                    ST_Transform(ee.geom, 3035),
                    ST_Transform(hs.geom, 3035)
                ) / 1000.0 AS dist_km
            FROM unesco_risk.earthquake_events ee
            CROSS JOIN LATERAL (
                SELECT id, geom
                FROM unesco_risk.heritage_sites
                ORDER BY ee.geom <-> geom
                LIMIT 1
            ) hs
        )
        UPDATE unesco_risk.earthquake_events ee
        SET nearest_site_id = n.site_id,
            distance_to_site_km = n.dist_km
        FROM nearest n
        WHERE ee.id = n.event_id
          AND n.dist_km <= :max_dist_km;
    """)
    
    max_dist_km = BUFFER_DISTANCES['earthquake'] / 1000.0
    result = session.execute(update_sql, {'max_dist_km': max_dist_km})
    updated_count = result.rowcount
    session.commit()
    
    logger.info(f"Updated {updated_count} earthquake events (within {max_dist_km} km)")
    return updated_count


def update_fire_distances(session, verbose: bool = True) -> int:
    """
    Update nearest_site_id and distance_to_site_km for all fire events
    using PostGIS lateral cross-join (nearest neighbor).
    
    Args:
        session: Database session
        verbose: Print progress information
        
    Returns:
        Number of fire events updated
    """
    logger.info("Updating fire events with PostGIS nearest-neighbor join...")
    
    update_sql = text("""
        WITH nearest AS (
            SELECT DISTINCT ON (fe.id)
                fe.id AS event_id,
                hs.id AS site_id,
                ST_Distance(
                    ST_Transform(fe.geom, 3035),
                    ST_Transform(hs.geom, 3035)
                ) / 1000.0 AS dist_km
            FROM unesco_risk.fire_events fe
            CROSS JOIN LATERAL (
                SELECT id, geom
                FROM unesco_risk.heritage_sites
                ORDER BY fe.geom <-> geom
                LIMIT 1
            ) hs
        )
        UPDATE unesco_risk.fire_events fe
        SET nearest_site_id = n.site_id,
            distance_to_site_km = n.dist_km
        FROM nearest n
        WHERE fe.id = n.event_id
          AND n.dist_km <= :max_dist_km;
    """)
    
    max_dist_km = BUFFER_DISTANCES['fire'] / 1000.0
    result = session.execute(update_sql, {'max_dist_km': max_dist_km})
    updated_count = result.rowcount
    session.commit()
    
    logger.info(f"Updated {updated_count} fire events (within {max_dist_km} km)")
    return updated_count


def update_flood_distances(session, verbose: bool = True) -> int:
    """
    Update nearest_site_id and distance_to_site_km for all flood zones
    using PostGIS lateral cross-join (nearest neighbor).
    
    Args:
        session: Database session
        verbose: Print progress information
        
    Returns:
        Number of flood zones updated
    """
    logger.info("Updating flood zones with PostGIS nearest-neighbor join...")
    
    update_sql = text("""
        WITH nearest AS (
            SELECT DISTINCT ON (fz.id)
                fz.id AS zone_id,
                hs.id AS site_id,
                ST_Distance(
                    ST_Transform(fz.geom, 3035),
                    ST_Transform(hs.geom, 3035)
                ) / 1000.0 AS dist_km
            FROM unesco_risk.flood_zones fz
            CROSS JOIN LATERAL (
                SELECT id, geom
                FROM unesco_risk.heritage_sites
                ORDER BY fz.geom <-> geom
                LIMIT 1
            ) hs
        )
        UPDATE unesco_risk.flood_zones fz
        SET nearest_site_id = n.site_id,
            distance_to_site_km = n.dist_km
        FROM nearest n
        WHERE fz.id = n.zone_id
          AND n.dist_km <= :max_dist_km;
    """)
    
    max_dist_km = BUFFER_DISTANCES['flood'] / 1000.0
    result = session.execute(update_sql, {'max_dist_km': max_dist_km})
    updated_count = result.rowcount
    session.commit()
    
    logger.info(f"Updated {updated_count} flood zones (within {max_dist_km} km)")
    return updated_count


def validate_crs_transformation(sites_gdf: gpd.GeoDataFrame) -> bool:
    """
    Validate CRS transformations by checking known distances.
    
    Tests the accuracy of EPSG:4326 -> EPSG:3035 transformation
    by computing distances between well-known European cities.
    
    Args:
        sites_gdf: GeoDataFrame of heritage sites
        
    Returns:
        True if validation passes, False otherwise
        
    Example:
        Expected: Paris to London ~340 km, Rome to Athens ~1100 km
    """
    logger.info("Validating CRS transformations...")
    
    # Known test points (approximate city centers)
    test_points = {
        'Paris': Point(2.3522, 48.8566),
        'London': Point(-0.1276, 51.5074),
        'Rome': Point(12.4964, 41.9028),
        'Athens': Point(23.7275, 37.9838)
    }
    
    # Expected distances (km) with tolerance
    expected_distances = {
        ('Paris', 'London'): (340, 350),  # ~344 km
        ('Rome', 'Athens'): (1050, 1150)  # ~1100 km
    }
    
    # Create test GeoDataFrame
    test_gdf = gpd.GeoDataFrame(
        {'name': list(test_points.keys())},
        geometry=list(test_points.values()),
        crs=CRS_WGS84
    )
    
    # Transform to EPSG:3035
    test_proj = test_gdf.to_crs(CRS_ETRS89_LAEA)
    
    # Compute distances
    validation_passed = True
    for (city1, city2), (min_km, max_km) in expected_distances.items():
        point1 = test_proj[test_proj['name'] == city1].geometry.iloc[0]
        point2 = test_proj[test_proj['name'] == city2].geometry.iloc[0]
        
        distance_m = point1.distance(point2)
        distance_km = distance_m / 1000.0
        
        if min_km <= distance_km <= max_km:
            logger.info(f"✓ {city1} to {city2}: {distance_km:.1f} km "
                       f"(expected: {min_km}-{max_km} km)")
        else:
            logger.error(f"✗ {city1} to {city2}: {distance_km:.1f} km "
                        f"(expected: {min_km}-{max_km} km) - OUT OF RANGE")
            validation_passed = False
    
    if validation_passed:
        logger.info("CRS transformation validation PASSED")
    else:
        logger.error("CRS transformation validation FAILED")
    
    return validation_passed


def run_full_spatial_join(verbose: bool = True, dry_run: bool = False):
    """
    Run the complete spatial join pipeline for all data types.
    
    This is the main entry point for Phase 5 execution.
    
    Args:
        verbose: Print detailed progress information
        dry_run: If True, perform joins but don't update database
        
    Example:
        >>> run_full_spatial_join(verbose=True, dry_run=False)
    """
    logger.info("=" * 80)
    logger.info("PHASE 5: CRS TRANSFORMATION & SPATIAL JOIN")
    logger.info("=" * 80)
    
    if dry_run:
        logger.warning("DRY RUN MODE: Database will not be updated")
    
    session = get_session()
    
    try:
        # Step 1: Validate CRS transformations
        logger.info("\n[Step 1/5] Validating CRS transformations...")
        sites_query = "SELECT id, whc_id, name, ST_AsText(geom) as geom_wkt FROM unesco_risk.heritage_sites LIMIT 10"
        sites_df = pd.read_sql(sites_query, session.bind)
        sites_df['geometry'] = sites_df['geom_wkt'].apply(lambda x: Point([float(c) for c in x.replace('POINT(', '').replace(')', '').split()]))
        sites_gdf = gpd.GeoDataFrame(sites_df, geometry='geometry', crs=CRS_WGS84)
        
        if not validate_crs_transformation(sites_gdf):
            logger.error("CRS validation failed. Aborting.")
            return
        
        if dry_run:
            logger.info("Dry run mode - skipping database updates")
            return
        
        # Step 2: Update urban features
        logger.info("\n[Step 2/5] Updating urban features...")
        urban_count = update_urban_features_distances(session, verbose=verbose)
        
        # Step 3: Update earthquake events
        logger.info("\n[Step 3/5] Updating earthquake events...")
        eq_count = update_earthquake_distances(session, verbose=verbose)
        
        # Step 4: Update fire events
        logger.info("\n[Step 4/5] Updating fire events...")
        fire_count = update_fire_distances(session, verbose=verbose)
        
        # Step 5: Update flood zones
        logger.info("\n[Step 5/5] Updating flood zones...")
        flood_count = update_flood_distances(session, verbose=verbose)
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("SPATIAL JOIN COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Urban features updated: {urban_count}")
        logger.info(f"Earthquake events updated: {eq_count}")
        logger.info(f"Fire events updated: {fire_count}")
        logger.info(f"Flood zones updated: {flood_count}")
        logger.info(f"Total records updated: {urban_count + eq_count + fire_count + flood_count}")
        
        # Verification queries
        logger.info("\n" + "-" * 80)
        logger.info("VERIFICATION QUERIES")
        logger.info("-" * 80)
        
        # Count non-null nearest_site_id
        for table in ['urban_features', 'earthquake_events', 'fire_events', 'flood_zones']:
            result = session.execute(text(f"""
                SELECT COUNT(*) FROM unesco_risk.{table} 
                WHERE nearest_site_id IS NOT NULL
            """))
            count = result.scalar()
            logger.info(f"{table}: {count} records with nearest_site_id")
        
        # Average distances
        for table in ['earthquake_events', 'fire_events', 'flood_zones']:
            result = session.execute(text(f"""
                SELECT AVG(distance_to_site_km) FROM unesco_risk.{table}
                WHERE distance_to_site_km IS NOT NULL
            """))
            avg_dist = result.scalar()
            if avg_dist:
                logger.info(f"{table}: avg distance = {avg_dist:.2f} km")
        
    except Exception as e:
        logger.error(f"Error during spatial join: {e}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


# CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Phase 5: CRS Transformation & Spatial Join",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (validation only, no database updates)
  python -m src.etl.spatial_join --dry-run
  
  # Run full spatial join pipeline
  python -m src.etl.spatial_join
  
  # Run with minimal output
  python -m src.etl.spatial_join --quiet
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate CRS transformations without updating database'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimal output (disable progress bars)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output with debug information'
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.WARNING)
    
    # Run the spatial join pipeline
    run_full_spatial_join(
        verbose=not args.quiet,
        dry_run=args.dry_run
    )
