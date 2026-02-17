"""
Kernel Density Estimation (KDE) for Urban Density Analysis.

This module computes urban density scores using sklearn's KernelDensity with:
- Gaussian kernel
- Bandwidth: 1000 meters (in EPSG:3035 projection)
- Density computed at each urban feature centroid

The density scores indicate clustering of urban features and can be used
for visualizing urban density hotspots around heritage sites.
"""

import logging
import numpy as np
import pandas as pd
from typing import Tuple
from sqlalchemy import text
from sklearn.neighbors import KernelDensity

from config.settings import PROJ_CRS
from src.db.connection import get_session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# KDE Parameters
KDE_BANDWIDTH = 1000.0  # meters in EPSG:3035
KDE_KERNEL = 'gaussian'


def load_urban_features(session) -> pd.DataFrame:
    """
    Load urban feature centroids from database.
    
    Converts geometries to EPSG:3035 for metric distance calculations.
    
    Args:
        session: SQLAlchemy database session
        
    Returns:
        DataFrame with id, x, y coordinates in EPSG:3035
    """
    logger.info("Loading urban feature centroids...")
    
    query = text("""
        SELECT 
            id,
            ST_X(ST_Transform(ST_Centroid(geom), :proj_crs)) AS x,
            ST_Y(ST_Transform(ST_Centroid(geom), :proj_crs)) AS y,
            feature_type,
            nearest_site_id
        FROM unesco_risk.urban_features
        WHERE geom IS NOT NULL;
    """)
    
    df = pd.read_sql(query, session.bind, params={'proj_crs': PROJ_CRS})
    logger.info(f"Loaded {len(df)} urban feature centroids")
    
    return df


def compute_urban_kde(
    urban_df: pd.DataFrame,
    bandwidth: float = KDE_BANDWIDTH,
    kernel: str = KDE_KERNEL
) -> Tuple[KernelDensity, np.ndarray]:
    """
    Compute Kernel Density Estimation on urban features.
    
    Args:
        urban_df: DataFrame with x, y coordinates
        bandwidth: Bandwidth for KDE in meters (default: 1000)
        kernel: Kernel type (default: 'gaussian')
        
    Returns:
        Tuple of (fitted KDE model, density scores)
    """
    logger.info(f"Computing KDE with bandwidth={bandwidth}m, kernel='{kernel}'...")
    
    if len(urban_df) == 0:
        logger.warning("No urban features found!")
        return None, np.array([])
    
    # Extract coordinates
    X = urban_df[['x', 'y']].values
    
    # Initialize and fit KDE
    kde = KernelDensity(
        bandwidth=bandwidth,
        kernel=kernel,
        metric='euclidean',
        algorithm='auto'
    )
    
    kde.fit(X)
    logger.info("✓ KDE model fitted")
    
    # Compute density scores at each point
    log_density = kde.score_samples(X)
    density_scores = np.exp(log_density)
    
    logger.info(f"Density scores: min={density_scores.min():.6e}, "
                f"max={density_scores.max():.6e}, "
                f"mean={density_scores.mean():.6e}")
    
    return kde, density_scores


def update_urban_density_scores(urban_df: pd.DataFrame, density_scores: np.ndarray, session) -> int:
    """
    Update urban_features table with density scores.
    
    Note: This requires adding a 'density_score' column to urban_features table.
    
    Args:
        urban_df: DataFrame with urban feature IDs
        density_scores: Array of density scores
        session: SQLAlchemy database session
        
    Returns:
        Number of records updated
    """
    logger.info("Updating urban_features table with density scores...")
    
    # First, check if density_score column exists
    check_query = text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'unesco_risk' 
          AND table_name = 'urban_features' 
          AND column_name = 'density_score';
    """)
    
    result = session.execute(check_query).fetchall()
    
    if not result:
        # Add density_score column
        logger.info("Adding density_score column to urban_features table...")
        alter_query = text("""
            ALTER TABLE unesco_risk.urban_features 
            ADD COLUMN IF NOT EXISTS density_score FLOAT;
        """)
        session.execute(alter_query)
        session.commit()
        logger.info("✓ density_score column added")
    
    # Update density scores
    records_updated = 0
    
    for i, (idx, row) in enumerate(urban_df.iterrows()):
        try:
            update_query = text("""
                UPDATE unesco_risk.urban_features
                SET density_score = :density_score
                WHERE id = :feature_id;
            """)
            
            session.execute(update_query, {
                'density_score': float(density_scores[i]),
                'feature_id': int(row['id'])
            })
            
            records_updated += 1
            
        except Exception as e:
            logger.error(f"Error updating density score for feature {row['id']}: {e}")
            continue
    
    # Commit all updates
    try:
        session.commit()
        logger.info(f"✓ Successfully updated {records_updated} urban features with density scores")
    except Exception as e:
        session.rollback()
        logger.error(f"Error committing density score updates: {e}")
        raise
    
    return records_updated


def compute_site_density_summary(session) -> pd.DataFrame:
    """
    Compute summary statistics of urban density for each heritage site.
    
    Aggregates density scores for all urban features within 5km of each site.
    
    Args:
        session: SQLAlchemy database session
        
    Returns:
        DataFrame with site_id, avg_density, max_density, density_feature_count
    """
    logger.info("Computing site-level density summaries...")
    
    query = text("""
        SELECT 
            hs.id AS site_id,
            hs.name AS site_name,
            COUNT(uf.id) AS density_feature_count,
            COALESCE(AVG(uf.density_score), 0) AS avg_density,
            COALESCE(MAX(uf.density_score), 0) AS max_density,
            COALESCE(STDDEV(uf.density_score), 0) AS stddev_density
        FROM unesco_risk.heritage_sites hs
        LEFT JOIN unesco_risk.urban_features uf 
            ON uf.nearest_site_id = hs.id 
            AND uf.distance_to_site_m <= 5000
            AND uf.density_score IS NOT NULL
        GROUP BY hs.id, hs.name
        ORDER BY avg_density DESC;
    """)
    
    df = pd.read_sql(query, session.bind)
    logger.info(f"Computed density summaries for {len(df)} sites")
    
    return df


def run_density_analysis() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Main function to run urban density analysis.
    
    This function:
    1. Loads urban feature centroids
    2. Computes KDE
    3. Updates database with density scores
    4. Computes site-level summaries
    
    Returns:
        Tuple of (urban_df with density scores, site_summary_df)
    """
    logger.info("=" * 80)
    logger.info("Starting urban density analysis (KDE)")
    logger.info("=" * 80)
    
    session = get_session()
    
    try:
        # Step 1: Load urban features
        urban_df = load_urban_features(session)
        
        if len(urban_df) == 0:
            logger.warning("No urban features found! Please run fetch_osm.py first.")
            return pd.DataFrame(), pd.DataFrame()
        
        # Step 2: Compute KDE
        kde_model, density_scores = compute_urban_kde(urban_df, KDE_BANDWIDTH, KDE_KERNEL)
        
        if kde_model is None:
            return pd.DataFrame(), pd.DataFrame()
        
        # Add density scores to DataFrame
        urban_df['density_score'] = density_scores
        
        # Step 3: Update database
        records_updated = update_urban_density_scores(urban_df, density_scores, session)
        
        # Step 4: Compute site-level summaries
        site_summary_df = compute_site_density_summary(session)
        
        logger.info("=" * 80)
        logger.info(f"✓ Urban density analysis complete!")
        logger.info(f"Urban features analyzed: {len(urban_df)}")
        logger.info(f"Records updated: {records_updated}")
        logger.info(f"Sites with density data: {(site_summary_df['density_feature_count'] > 0).sum()}")
        logger.info("=" * 80)
        
        # Show top high-density sites
        if len(site_summary_df) > 0:
            top_density_sites = site_summary_df.nlargest(10, 'avg_density')
            logger.info(f"\nTop 10 sites by average urban density:")
            for _, row in top_density_sites.iterrows():
                logger.info(f"  {row['site_name']}: avg_density={row['avg_density']:.6e}, "
                           f"features={row['density_feature_count']}")
        
        return urban_df, site_summary_df
        
    except Exception as e:
        logger.error(f"Error during density analysis: {e}")
        raise
    finally:
        session.close()


def main():
    """Main entry point for CLI execution."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Compute urban density using Kernel Density Estimation'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Compute density without updating database'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--bandwidth',
        type=float,
        default=KDE_BANDWIDTH,
        help=f'KDE bandwidth in meters (default: {KDE_BANDWIDTH})'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.dry_run:
        logger.info("DRY RUN MODE: Density will be computed but not saved")
        session = get_session()
        try:
            urban_df = load_urban_features(session)
            if len(urban_df) > 0:
                kde_model, density_scores = compute_urban_kde(
                    urban_df, 
                    bandwidth=args.bandwidth
                )
                
                if kde_model is not None:
                    print(f"\n✓ Dry run complete. Computed density for {len(density_scores)} features")
                    print(f"Density stats: min={density_scores.min():.6e}, "
                          f"max={density_scores.max():.6e}, "
                          f"mean={density_scores.mean():.6e}")
        finally:
            session.close()
    else:
        # Normal execution
        urban_df, site_summary_df = run_density_analysis()
        
        if len(site_summary_df) > 0:
            print(f"\n✓ Density analysis complete!")
            print(f"Analyzed {len(urban_df)} urban features")
            print(f"Sites with density data: {(site_summary_df['density_feature_count'] > 0).sum()}")
            
            print(f"\nTop 5 highest density sites:")
            print(site_summary_df.nlargest(5, 'avg_density')[
                ['site_name', 'avg_density', 'density_feature_count']
            ])


if __name__ == '__main__':
    main()
