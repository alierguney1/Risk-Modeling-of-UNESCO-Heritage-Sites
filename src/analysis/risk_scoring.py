"""
Risk Scoring Engine for UNESCO Heritage Sites.

This module computes 6 sub-scores for each heritage site:
1. Urban Density Score — based on building count and footprint area within 10km
2. Climate Anomaly Score — based on Z-score analysis of extreme weather events
3. Seismic Risk Score — based on Gutenberg-Richter energy from earthquakes within 200km (ST_DWithin)
4. Fire Risk Score — based on FRP × confidence / distance for fires within 100km (ST_DWithin)
5. Flood Risk Score — based on GFMS pixel values and historical flood frequency within 100km (ST_DWithin)
6. Coastal Risk Score — based on elevation for coastal sites (< 50km from coast)

All scores are normalized to [0, 1] using log1p + Min-Max scaling to prevent outlier compression.
Composite score is calculated as weighted average per RISK_WEIGHTS.
Risk levels: low (0-0.25), medium (0.25-0.50), high (0.50-0.75), critical (0.75-1.0)
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
from sqlalchemy import text
from sklearn.preprocessing import MinMaxScaler

from config.settings import RISK_WEIGHTS
from src.db.connection import get_session, engine
from src.db.models import HeritageSite, RiskScore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default risk weights (should sum to 1.0)
DEFAULT_WEIGHTS = RISK_WEIGHTS


def validate_weights(weights: Dict[str, float]) -> bool:
    """
    Validate that risk weights sum to 1.0 (within floating point tolerance).
    
    Args:
        weights: Dictionary of risk component weights
        
    Returns:
        True if valid, raises ValueError otherwise
    """
    total = sum(weights.values())
    if not np.isclose(total, 1.0, atol=1e-6):
        raise ValueError(f"Risk weights must sum to 1.0, got {total}")
    
    logger.info(f"✓ Risk weights validated: sum = {total:.10f}")
    return True


def _log_minmax_scale(df: pd.DataFrame, raw_col: str, score_col: str) -> pd.DataFrame:
    """
    Apply log1p transform then MinMax scaling to a raw column.
    
    This prevents outlier compression: raw values spanning orders of magnitude
    (e.g. 100 to 48,000,000) get compressed to a manageable log range first,
    then MinMax spreads them evenly across [0, 1].
    
    Args:
        df: DataFrame containing the raw column
        raw_col: Name of the raw value column
        score_col: Name of the output score column
        
    Returns:
        DataFrame with score_col added
    """
    if df[raw_col].max() == 0 or df[raw_col].isna().all():
        df[score_col] = 0.0
    else:
        # log1p handles 0 values gracefully (log1p(0) = 0)
        df['_log_raw'] = np.log1p(df[raw_col].astype(float))
        scaler = MinMaxScaler()
        df[score_col] = scaler.fit_transform(df[['_log_raw']])
        df.drop(columns=['_log_raw'], inplace=True)
    return df


def compute_urban_density_score(session) -> pd.DataFrame:
    """
    Compute urban density score for each heritage site.
    
    Score is based on:
    - Number of buildings within 10km buffer
    - Total building footprint area within 10km
    
    Raw density = building_count + (total_area_m2 / 1000000)
    Then log1p + MinMax normalized to [0, 1]
    
    Args:
        session: SQLAlchemy database session
        
    Returns:
        DataFrame with columns: site_id, urban_density_raw, urban_density_score
    """
    logger.info("Computing urban density scores...")
    
    query = text("""
        WITH site_urban_stats AS (
            SELECT 
                hs.id AS site_id,
                COUNT(uf.id) AS building_count,
                COALESCE(SUM(
                    CASE 
                        WHEN uf.feature_type = 'building' 
                        THEN ST_Area(ST_Transform(uf.geom, 3035))
                        ELSE 0
                    END
                ), 0) AS total_area_m2
            FROM unesco_risk.heritage_sites hs
            LEFT JOIN unesco_risk.urban_features uf 
                ON uf.nearest_site_id = hs.id 
                AND uf.distance_to_site_m <= 10000
            GROUP BY hs.id
        )
        SELECT 
            site_id,
            building_count,
            total_area_m2,
            building_count + (total_area_m2 / 1000000.0) AS urban_density_raw
        FROM site_urban_stats
        ORDER BY site_id;
    """)
    
    df = pd.read_sql(query, session.bind)
    logger.info(f"Fetched urban density data for {len(df)} sites")
    
    if len(df) == 0:
        logger.warning("No urban density data found!")
        return pd.DataFrame(columns=['site_id', 'urban_density_raw', 'urban_density_score'])
    
    df = _log_minmax_scale(df, 'urban_density_raw', 'urban_density_score')
    
    logger.info(f"Urban density scores: min={df['urban_density_score'].min():.3f}, "
                f"max={df['urban_density_score'].max():.3f}, "
                f"mean={df['urban_density_score'].mean():.3f}")
    
    return df[['site_id', 'urban_density_raw', 'urban_density_score']]


def compute_climate_anomaly_score(session) -> pd.DataFrame:
    """
    Compute climate anomaly score for each heritage site.
    
    Score is based on:
    - Z-score analysis of daily temperature max and precipitation
    - Count of extreme days: temp > μ+2σ OR precip > μ+3σ
    - Ratio: extreme_days / total_days
    
    Then normalized to [0, 1]
    
    Args:
        session: SQLAlchemy database session
        
    Returns:
        DataFrame with columns: site_id, extreme_days, total_days, anomaly_ratio, climate_anomaly_score
    """
    logger.info("Computing climate anomaly scores...")
    
    query = text("""
        WITH site_climate_stats AS (
            SELECT 
                site_id,
                AVG(temp_max_c) AS temp_mean,
                STDDEV(temp_max_c) AS temp_stddev,
                AVG(precipitation_mm) AS precip_mean,
                STDDEV(precipitation_mm) AS precip_stddev,
                COUNT(*) AS total_days
            FROM unesco_risk.climate_events
            WHERE temp_max_c IS NOT NULL 
                AND precipitation_mm IS NOT NULL
            GROUP BY site_id
        ),
        extreme_events AS (
            SELECT 
                ce.site_id,
                scs.temp_mean,
                scs.temp_stddev,
                scs.precip_mean,
                scs.precip_stddev,
                COUNT(*) AS extreme_days
            FROM unesco_risk.climate_events ce
            JOIN site_climate_stats scs ON ce.site_id = scs.site_id
            WHERE (
                ce.temp_max_c > (scs.temp_mean + 2 * scs.temp_stddev)
                OR ce.precipitation_mm > (scs.precip_mean + 3 * scs.precip_stddev)
            )
            GROUP BY ce.site_id, scs.temp_mean, scs.temp_stddev, 
                     scs.precip_mean, scs.precip_stddev
        )
        SELECT 
            hs.id AS site_id,
            COALESCE(ee.extreme_days, 0) AS extreme_days,
            COALESCE(scs.total_days, 0) AS total_days,
            CASE 
                WHEN scs.total_days > 0 
                THEN CAST(COALESCE(ee.extreme_days, 0) AS FLOAT) / scs.total_days
                ELSE 0.0
            END AS anomaly_ratio
        FROM unesco_risk.heritage_sites hs
        LEFT JOIN site_climate_stats scs ON hs.id = scs.site_id
        LEFT JOIN extreme_events ee ON hs.id = ee.site_id
        ORDER BY hs.id;
    """)
    
    df = pd.read_sql(query, session.bind)
    logger.info(f"Fetched climate anomaly data for {len(df)} sites")
    
    if len(df) == 0:
        logger.warning("No climate anomaly data found!")
        return pd.DataFrame(columns=['site_id', 'extreme_days', 'total_days', 
                                     'anomaly_ratio', 'climate_anomaly_score'])
    
    df = _log_minmax_scale(df, 'anomaly_ratio', 'climate_anomaly_score')
    
    logger.info(f"Climate anomaly scores: min={df['climate_anomaly_score'].min():.3f}, "
                f"max={df['climate_anomaly_score'].max():.3f}, "
                f"mean={df['climate_anomaly_score'].mean():.3f}")
    
    return df[['site_id', 'extreme_days', 'total_days', 'anomaly_ratio', 'climate_anomaly_score']]


def compute_seismic_risk_score(session) -> pd.DataFrame:
    """
    Compute seismic risk score for each heritage site.
    
    Score is based on Gutenberg-Richter energy formula:
    - Uses ST_DWithin to find ALL earthquakes within 200km of each site
    - For each earthquake: energy = 10^(1.5 * magnitude) / distance²
    - Sum all energy contributions
    - Then log1p + MinMax normalized to [0, 1]
    
    Args:
        session: SQLAlchemy database session
        
    Returns:
        DataFrame with columns: site_id, earthquake_count, total_energy, seismic_risk_score
    """
    logger.info("Computing seismic risk scores...")
    
    # Use ST_DWithin for many-to-many: each site considers ALL earthquakes
    # within 200km, not just events mapped as "nearest" to it
    query = text("""
        WITH earthquake_energy AS (
            SELECT 
                hs.id AS site_id,
                COUNT(ee.id) AS earthquake_count,
                COALESCE(SUM(
                    POWER(10, 1.5 * ee.magnitude) / 
                    POWER(GREATEST(
                        ST_Distance(hs.geom::geography, ee.geom::geography) / 1000.0, 
                        0.1
                    ), 2)
                ), 0) AS total_energy
            FROM unesco_risk.heritage_sites hs
            LEFT JOIN unesco_risk.earthquake_events ee 
                ON ST_DWithin(hs.geom::geography, ee.geom::geography, 200000)
            GROUP BY hs.id
        )
        SELECT 
            site_id,
            earthquake_count,
            total_energy
        FROM earthquake_energy
        ORDER BY site_id;
    """)
    
    df = pd.read_sql(query, session.bind)
    logger.info(f"Fetched seismic risk data for {len(df)} sites")
    
    if len(df) == 0:
        logger.warning("No seismic risk data found!")
        return pd.DataFrame(columns=['site_id', 'earthquake_count', 'total_energy', 'seismic_risk_score'])
    
    df = _log_minmax_scale(df, 'total_energy', 'seismic_risk_score')
    
    logger.info(f"Seismic risk scores: min={df['seismic_risk_score'].min():.3f}, "
                f"max={df['seismic_risk_score'].max():.3f}, "
                f"mean={df['seismic_risk_score'].mean():.3f}")
    
    return df[['site_id', 'earthquake_count', 'total_energy', 'seismic_risk_score']]


def compute_fire_risk_score(session) -> pd.DataFrame:
    """
    Compute fire risk score for each heritage site.
    
    Score is based on:
    - Uses ST_DWithin to find ALL fires within 100km of each site
    - For each fire: contribution = FRP × confidence / distance
    - Sum all fire contributions
    - Then log1p + MinMax normalized to [0, 1]
    
    Args:
        session: SQLAlchemy database session
        
    Returns:
        DataFrame with columns: site_id, fire_count, total_fire_risk, fire_risk_score
    """
    logger.info("Computing fire risk scores...")
    
    # Use ST_DWithin for many-to-many: each site considers ALL fires within 100km
    query = text("""
        WITH fire_risk AS (
            SELECT 
                hs.id AS site_id,
                COUNT(fe.id) AS fire_count,
                COALESCE(SUM(
                    fe.frp * (fe.confidence / 100.0) / 
                    GREATEST(
                        ST_Distance(hs.geom::geography, fe.geom::geography) / 1000.0,
                        0.1
                    )
                ), 0) AS total_fire_risk
            FROM unesco_risk.heritage_sites hs
            LEFT JOIN unesco_risk.fire_events fe 
                ON ST_DWithin(hs.geom::geography, fe.geom::geography, 100000)
            GROUP BY hs.id
        )
        SELECT 
            site_id,
            fire_count,
            total_fire_risk
        FROM fire_risk
        ORDER BY site_id;
    """)
    
    df = pd.read_sql(query, session.bind)
    logger.info(f"Fetched fire risk data for {len(df)} sites")
    
    if len(df) == 0:
        logger.warning("No fire risk data found!")
        return pd.DataFrame(columns=['site_id', 'fire_count', 'total_fire_risk', 'fire_risk_score'])
    
    df = _log_minmax_scale(df, 'total_fire_risk', 'fire_risk_score')
    
    logger.info(f"Fire risk scores: min={df['fire_risk_score'].min():.3f}, "
                f"max={df['fire_risk_score'].max():.3f}, "
                f"mean={df['fire_risk_score'].mean():.3f}")
    
    return df[['site_id', 'fire_count', 'total_fire_risk', 'fire_risk_score']]


def compute_flood_risk_score(session) -> pd.DataFrame:
    """
    Compute flood risk score for each heritage site.
    
    Score is based on:
    - GFMS pixel value (if available)
    - Historical flood frequency (count of flood zones within 50km)
    
    Combined score then normalized to [0, 1]
    
    Args:
        session: SQLAlchemy database session
        
    Returns:
        DataFrame with columns: site_id, flood_count, avg_severity, flood_risk_score
    """
    logger.info("Computing flood risk scores...")
    
    # Use ST_DWithin for many-to-many flood zone matching
    query = text("""
        WITH flood_risk AS (
            SELECT 
                hs.id AS site_id,
                COUNT(fz.id) AS flood_count,
                COALESCE(AVG(fz.flood_intensity), 0) AS avg_severity
            FROM unesco_risk.heritage_sites hs
            LEFT JOIN unesco_risk.flood_zones fz 
                ON ST_DWithin(hs.geom::geography, fz.geom::geography, 100000)
            GROUP BY hs.id
        )
        SELECT 
            site_id,
            flood_count,
            avg_severity,
            (flood_count * 0.5 + avg_severity * 0.5) AS flood_risk_raw
        FROM flood_risk
        ORDER BY site_id;
    """)
    
    df = pd.read_sql(query, session.bind)
    logger.info(f"Fetched flood risk data for {len(df)} sites")
    
    if len(df) == 0:
        logger.warning("No flood risk data found!")
        return pd.DataFrame(columns=['site_id', 'flood_count', 'avg_severity', 'flood_risk_score'])
    
    df = _log_minmax_scale(df, 'flood_risk_raw', 'flood_risk_score')
    
    logger.info(f"Flood risk scores: min={df['flood_risk_score'].min():.3f}, "
                f"max={df['flood_risk_score'].max():.3f}, "
                f"mean={df['flood_risk_score'].mean():.3f}")
    
    return df[['site_id', 'flood_count', 'avg_severity', 'flood_risk_score']]


def compute_coastal_risk_score(session) -> pd.DataFrame:
    """
    Compute coastal risk score for each heritage site.
    
    Score is based on elevation for coastal sites:
    - Coastal sites: within 50km of coastline
    - Risk score = max(0, 1 - elevation/10) for coastal sites
    - Non-coastal sites: score = 0
    
    Args:
        session: SQLAlchemy database session
        
    Returns:
        DataFrame with columns: site_id, elevation_m, is_coastal, coastal_risk_score
    """
    logger.info("Computing coastal risk scores...")
    
    # First, check if elevation columns exist
    check_query = text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'unesco_risk' 
          AND table_name = 'heritage_sites' 
          AND column_name IN ('elevation_m', 'coastal_risk_score');
    """)
    
    existing_cols = pd.read_sql(check_query, session.bind)
    has_elevation = 'elevation_m' in existing_cols['column_name'].values
    has_coastal = 'coastal_risk_score' in existing_cols['column_name'].values
    
    if has_elevation and has_coastal:
        # Use existing elevation and coastal risk data
        query = text("""
            SELECT 
                id AS site_id,
                COALESCE(elevation_m, 0) AS elevation_m,
                (elevation_m IS NOT NULL AND elevation_m < 50) AS is_coastal,
                COALESCE(coastal_risk_score, 0) AS coastal_risk_score
            FROM unesco_risk.heritage_sites
            ORDER BY id;
        """)
    else:
        # Fallback: estimate based on proximity to coastline (not implemented)
        logger.warning("Elevation columns not found. Using placeholder coastal risk scores.")
        query = text("""
            SELECT 
                id AS site_id,
                0.0 AS elevation_m,
                FALSE AS is_coastal,
                0.0 AS coastal_risk_score
            FROM unesco_risk.heritage_sites
            ORDER BY id;
        """)
    
    df = pd.read_sql(query, session.bind)
    logger.info(f"Fetched coastal risk data for {len(df)} sites")
    
    # Ensure score is in [0, 1]
    df['coastal_risk_score'] = df['coastal_risk_score'].clip(0, 1)
    
    logger.info(f"Coastal risk scores: min={df['coastal_risk_score'].min():.3f}, "
                f"max={df['coastal_risk_score'].max():.3f}, "
                f"mean={df['coastal_risk_score'].mean():.3f}")
    
    return df[['site_id', 'elevation_m', 'is_coastal', 'coastal_risk_score']]


def compute_composite_score(scores_df: pd.DataFrame, 
                            weights: Dict[str, float] = DEFAULT_WEIGHTS) -> pd.DataFrame:
    """
    Compute composite risk score as weighted average of 6 sub-scores.
    
    Assign risk level based on composite score:
    - low: [0, 0.25)
    - medium: [0.25, 0.50)
    - high: [0.50, 0.75)
    - critical: [0.75, 1.0]
    
    Args:
        scores_df: DataFrame with all 6 sub-scores
        weights: Dictionary of risk component weights (default: DEFAULT_WEIGHTS)
        
    Returns:
        DataFrame with composite_risk_score and risk_level columns added
    """
    logger.info("Computing composite risk scores...")
    
    # Validate weights
    validate_weights(weights)
    
    # Ensure all required score columns exist
    required_cols = [
        'urban_density_score',
        'climate_anomaly_score', 
        'seismic_risk_score',
        'fire_risk_score',
        'flood_risk_score',
        'coastal_risk_score'
    ]
    
    for col in required_cols:
        if col not in scores_df.columns:
            logger.error(f"Missing required column: {col}")
            raise ValueError(f"Missing required column: {col}")
    
    # Fill NaN values with 0
    for col in required_cols:
        scores_df[col] = scores_df[col].fillna(0)
    
    # Calculate weighted average
    scores_df['composite_risk_score'] = (
        scores_df['urban_density_score'] * weights['urban_density'] +
        scores_df['climate_anomaly_score'] * weights['climate_anomaly'] +
        scores_df['seismic_risk_score'] * weights['seismic_risk'] +
        scores_df['fire_risk_score'] * weights['fire_risk'] +
        scores_df['flood_risk_score'] * weights['flood_risk'] +
        scores_df['coastal_risk_score'] * weights['coastal_risk']
    )
    
    # Ensure composite score is in [0, 1]
    scores_df['composite_risk_score'] = scores_df['composite_risk_score'].clip(0, 1)
    
    # Assign risk level using pd.cut
    scores_df['risk_level'] = pd.cut(
        scores_df['composite_risk_score'],
        bins=[0, 0.25, 0.50, 0.75, 1.0],
        labels=['low', 'medium', 'high', 'critical'],
        include_lowest=True
    )
    
    logger.info(f"Composite scores: min={scores_df['composite_risk_score'].min():.3f}, "
                f"max={scores_df['composite_risk_score'].max():.3f}, "
                f"mean={scores_df['composite_risk_score'].mean():.3f}")
    
    # Log risk level distribution
    level_dist = scores_df['risk_level'].value_counts().sort_index()
    logger.info(f"Risk level distribution:\n{level_dist}")
    
    return scores_df


def upsert_risk_scores(scores_df: pd.DataFrame, session) -> int:
    """
    UPSERT risk scores to the risk_scores table.
    
    If a record exists for a site_id, update it.
    If not, insert a new record.
    
    Args:
        scores_df: DataFrame with all risk scores
        session: SQLAlchemy database session
        
    Returns:
        Number of records upserted
    """
    logger.info(f"Upserting {len(scores_df)} risk score records...")
    
    # Prepare data for upsert
    records_upserted = 0
    
    for _, row in scores_df.iterrows():
        try:
            # Convert risk_level to string if it's a category
            risk_level_str = str(row['risk_level']) if pd.notna(row['risk_level']) else 'low'
            
            # Check if record exists
            existing = session.query(RiskScore).filter_by(site_id=int(row['site_id'])).first()
            
            if existing:
                # Update existing record
                existing.urban_density_score = float(row['urban_density_score'])
                existing.climate_anomaly_score = float(row['climate_anomaly_score'])
                existing.seismic_risk_score = float(row['seismic_risk_score'])
                existing.fire_risk_score = float(row['fire_risk_score'])
                existing.flood_risk_score = float(row['flood_risk_score'])
                existing.coastal_risk_score = float(row['coastal_risk_score'])
                existing.composite_risk_score = float(row['composite_risk_score'])
                existing.risk_level = risk_level_str
                # Don't update isolation_forest_score or is_anomaly here (Phase 7)
            else:
                # Insert new record
                new_record = RiskScore(
                    site_id=int(row['site_id']),
                    urban_density_score=float(row['urban_density_score']),
                    climate_anomaly_score=float(row['climate_anomaly_score']),
                    seismic_risk_score=float(row['seismic_risk_score']),
                    fire_risk_score=float(row['fire_risk_score']),
                    flood_risk_score=float(row['flood_risk_score']),
                    coastal_risk_score=float(row['coastal_risk_score']),
                    composite_risk_score=float(row['composite_risk_score']),
                    risk_level=risk_level_str
                )
                session.add(new_record)
            
            records_upserted += 1
            
        except Exception as e:
            logger.error(f"Error upserting record for site_id {row['site_id']}: {e}")
            continue
    
    # Commit all changes
    try:
        session.commit()
        logger.info(f"✓ Successfully upserted {records_upserted} risk score records")
    except Exception as e:
        session.rollback()
        logger.error(f"Error committing risk scores: {e}")
        raise
    
    return records_upserted


def calculate_all_risk_scores() -> pd.DataFrame:
    """
    Main function to calculate all risk scores.
    
    This function:
    1. Computes all 6 sub-scores
    2. Merges them into a single DataFrame
    3. Computes composite score and risk level
    4. Upserts results to database
    
    Returns:
        DataFrame with all risk scores
    """
    logger.info("=" * 80)
    logger.info("Starting risk score calculation for all heritage sites")
    logger.info("=" * 80)
    
    session = get_session()
    
    try:
        # Step 1: Compute all sub-scores
        urban_df = compute_urban_density_score(session)
        climate_df = compute_climate_anomaly_score(session)
        seismic_df = compute_seismic_risk_score(session)
        fire_df = compute_fire_risk_score(session)
        flood_df = compute_flood_risk_score(session)
        coastal_df = compute_coastal_risk_score(session)
        
        # Step 2: Merge all scores on site_id
        logger.info("Merging all sub-scores...")
        
        # Start with urban_df as base
        scores_df = urban_df[['site_id', 'urban_density_score']].copy()
        
        # Merge climate scores
        scores_df = scores_df.merge(
            climate_df[['site_id', 'climate_anomaly_score']], 
            on='site_id', 
            how='outer'
        )
        
        # Merge seismic scores
        scores_df = scores_df.merge(
            seismic_df[['site_id', 'seismic_risk_score']], 
            on='site_id', 
            how='outer'
        )
        
        # Merge fire scores
        scores_df = scores_df.merge(
            fire_df[['site_id', 'fire_risk_score']], 
            on='site_id', 
            how='outer'
        )
        
        # Merge flood scores
        scores_df = scores_df.merge(
            flood_df[['site_id', 'flood_risk_score']], 
            on='site_id', 
            how='outer'
        )
        
        # Merge coastal scores
        scores_df = scores_df.merge(
            coastal_df[['site_id', 'coastal_risk_score']], 
            on='site_id', 
            how='outer'
        )
        
        # Fill any remaining NaN values with 0
        scores_df = scores_df.fillna(0)
        
        logger.info(f"Merged scores for {len(scores_df)} sites")
        
        # Step 3: Compute composite score and risk level
        scores_df = compute_composite_score(scores_df, DEFAULT_WEIGHTS)
        
        # Step 4: Upsert to database
        records_upserted = upsert_risk_scores(scores_df, session)
        
        logger.info("=" * 80)
        logger.info(f"✓ Risk score calculation complete! {records_upserted} records upserted.")
        logger.info("=" * 80)
        
        return scores_df
        
    except Exception as e:
        logger.error(f"Error calculating risk scores: {e}")
        raise
    finally:
        session.close()


def main():
    """Main entry point for CLI execution."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Calculate risk scores for UNESCO Heritage Sites'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Calculate scores without saving to database'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.dry_run:
        logger.info("DRY RUN MODE: Scores will be calculated but not saved")
        session = get_session()
        try:
            # Compute scores but don't upsert
            urban_df = compute_urban_density_score(session)
            climate_df = compute_climate_anomaly_score(session)
            seismic_df = compute_seismic_risk_score(session)
            fire_df = compute_fire_risk_score(session)
            flood_df = compute_flood_risk_score(session)
            coastal_df = compute_coastal_risk_score(session)
            
            # Merge and compute composite
            scores_df = urban_df[['site_id', 'urban_density_score']].copy()
            scores_df = scores_df.merge(climate_df[['site_id', 'climate_anomaly_score']], on='site_id', how='outer')
            scores_df = scores_df.merge(seismic_df[['site_id', 'seismic_risk_score']], on='site_id', how='outer')
            scores_df = scores_df.merge(fire_df[['site_id', 'fire_risk_score']], on='site_id', how='outer')
            scores_df = scores_df.merge(flood_df[['site_id', 'flood_risk_score']], on='site_id', how='outer')
            scores_df = scores_df.merge(coastal_df[['site_id', 'coastal_risk_score']], on='site_id', how='outer')
            scores_df = scores_df.fillna(0)
            scores_df = compute_composite_score(scores_df, DEFAULT_WEIGHTS)
            
            print(f"\n✓ Dry run complete. Calculated scores for {len(scores_df)} sites")
            print(f"\nTop 10 highest risk sites:")
            print(scores_df.nlargest(10, 'composite_risk_score')[
                ['site_id', 'composite_risk_score', 'risk_level']
            ])
        finally:
            session.close()
    else:
        # Normal execution
        scores_df = calculate_all_risk_scores()
        
        print(f"\n✓ Risk scores calculated and saved for {len(scores_df)} sites")
        print(f"\nRisk level distribution:")
        print(scores_df['risk_level'].value_counts().sort_index())


if __name__ == '__main__':
    main()
