"""
Anomaly Detection for UNESCO Heritage Sites Risk Analysis.

This module implements Isolation Forest to detect multi-dimensional risk outliers.
Sites flagged as anomalies have their is_anomaly flag set to TRUE.
of their composite risk score.

Isolation Forest parameters:
- n_estimators: 200 (number of trees)
- contamination: 0.1 (expected proportion of anomalies, ~10%)
- random_state: 42 (for reproducibility)
- n_jobs: -1 (use all CPU cores)
"""

import logging
import numpy as np
import pandas as pd
from typing import Tuple
from sklearn.ensemble import IsolationForest

from config.settings import IF_CONTAMINATION, IF_N_ESTIMATORS, IF_RANDOM_STATE
from src.db.connection import get_session
from src.db.models import RiskScore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_risk_scores(session) -> pd.DataFrame:
    """
    Load all risk scores from database.
    
    Args:
        session: SQLAlchemy database session
        
    Returns:
        DataFrame with site_id and all 6 sub-scores
    """
    logger.info("Loading risk scores from database...")
    
    risk_scores = session.query(RiskScore).all()
    
    if not risk_scores:
        logger.warning("No risk scores found in database!")
        return pd.DataFrame()
    
    data = []
    for rs in risk_scores:
        data.append({
            'site_id': rs.site_id,
            'urban_density_score': rs.urban_density_score or 0.0,
            'climate_anomaly_score': rs.climate_anomaly_score or 0.0,
            'seismic_risk_score': rs.seismic_risk_score or 0.0,
            'fire_risk_score': rs.fire_risk_score or 0.0,
            'flood_risk_score': rs.flood_risk_score or 0.0,
            'coastal_risk_score': rs.coastal_risk_score or 0.0,
            'composite_risk_score': rs.composite_risk_score or 0.0,
            'risk_level': rs.risk_level or 'low'
        })
    
    df = pd.DataFrame(data)
    logger.info(f"Loaded {len(df)} risk score records")
    
    return df


def prepare_feature_matrix(scores_df: pd.DataFrame) -> Tuple[np.ndarray, pd.DataFrame]:
    """
    Prepare feature matrix for Isolation Forest.
    
    Uses 6 sub-score columns as features. NaN values are replaced with 0.
    
    Args:
        scores_df: DataFrame with risk scores
        
    Returns:
        Tuple of (feature_matrix, scores_df)
    """
    logger.info("Preparing feature matrix for Isolation Forest...")
    
    feature_cols = [
        'urban_density_score',
        'climate_anomaly_score',
        'seismic_risk_score',
        'fire_risk_score',
        'flood_risk_score',
        'coastal_risk_score'
    ]
    
    # Ensure all feature columns exist
    for col in feature_cols:
        if col not in scores_df.columns:
            logger.warning(f"Missing feature column {col}, setting to 0")
            scores_df[col] = 0.0
    
    # Replace NaN with 0
    scores_df[feature_cols] = scores_df[feature_cols].fillna(0)
    
    # Extract feature matrix
    X = scores_df[feature_cols].values
    
    logger.info(f"Feature matrix shape: {X.shape}")
    logger.info(f"Feature columns: {feature_cols}")
    
    return X, scores_df


def detect_risk_anomalies(
    X: np.ndarray,
    n_estimators: int = IF_N_ESTIMATORS,
    contamination: float = IF_CONTAMINATION,
    random_state: int = IF_RANDOM_STATE
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Detect anomalies using Isolation Forest.
    
    Args:
        X: Feature matrix (n_samples, n_features)
        n_estimators: Number of trees in the forest
        contamination: Expected proportion of outliers
        random_state: Random seed for reproducibility
        
    Returns:
        Tuple of (anomaly_scores, anomaly_labels)
        - anomaly_scores: Continuous anomaly score from decision_function()
        - anomaly_labels: Binary labels (-1 = anomaly, 1 = normal)
    """
    logger.info("Training Isolation Forest for anomaly detection...")
    logger.info(f"Parameters: n_estimators={n_estimators}, contamination={contamination}, "
                f"random_state={random_state}")
    
    # Initialize Isolation Forest
    iso_forest = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
        verbose=0
    )
    
    # Fit and predict
    anomaly_labels = iso_forest.fit_predict(X)
    anomaly_scores = iso_forest.decision_function(X)
    
    # Count anomalies
    n_anomalies = np.sum(anomaly_labels == -1)
    anomaly_rate = n_anomalies / len(anomaly_labels)
    
    logger.info(f"✓ Isolation Forest trained")
    logger.info(f"Detected {n_anomalies} anomalies out of {len(anomaly_labels)} sites "
                f"({anomaly_rate*100:.1f}%)")
    
    return anomaly_scores, anomaly_labels


def update_anomaly_flags(scores_df: pd.DataFrame, session) -> int:
    """
    Update risk_scores table with anomaly scores and flags.
    
    For anomalous sites:
    - Set is_anomaly = TRUE
    - Set isolation_forest_score
    - Override risk_level = 'critical'
    
    Args:
        scores_df: DataFrame with anomaly information
        session: SQLAlchemy database session
        
    Returns:
        Number of records updated
    """
    logger.info(f"Updating {len(scores_df)} risk score records with anomaly information...")
    
    records_updated = 0
    
    for _, row in scores_df.iterrows():
        try:
            # Find existing record
            risk_score = session.query(RiskScore).filter_by(site_id=int(row['site_id'])).first()
            
            if risk_score:
                # Update isolation forest score
                risk_score.isolation_forest_score = float(row['anomaly_score'])
                
                # Update is_anomaly flag
                risk_score.is_anomaly = bool(row['is_anomaly'])
                
                # Do NOT override risk_level — anomaly is a flag, not a risk level
                # risk_level is determined by composite_risk_score in risk_scoring.py
                if row['is_anomaly']:
                    logger.debug(f"Site {row['site_id']}: Anomaly detected (is_anomaly=True)")
                
                records_updated += 1
            else:
                logger.warning(f"No risk score record found for site_id {row['site_id']}")
        
        except Exception as e:
            logger.error(f"Error updating anomaly flag for site_id {row['site_id']}: {e}")
            continue
    
    # Commit changes
    try:
        session.commit()
        logger.info(f"✓ Successfully updated {records_updated} records with anomaly information")
    except Exception as e:
        session.rollback()
        logger.error(f"Error committing anomaly updates: {e}")
        raise
    
    return records_updated


def run_anomaly_detection() -> pd.DataFrame:
    """
    Main function to run anomaly detection pipeline.
    
    This function:
    1. Loads risk scores from database
    2. Prepares feature matrix
    3. Runs Isolation Forest
    4. Updates database with anomaly flags and scores
    
    Returns:
        DataFrame with anomaly information
    """
    logger.info("=" * 80)
    logger.info("Starting anomaly detection for heritage sites")
    logger.info("=" * 80)
    
    session = get_session()
    
    try:
        # Step 1: Load risk scores
        scores_df = load_risk_scores(session)
        
        if len(scores_df) == 0:
            logger.error("No risk scores found! Please run risk_scoring.py first.")
            return pd.DataFrame()
        
        # Step 2: Prepare feature matrix
        X, scores_df = prepare_feature_matrix(scores_df)
        
        # Step 3: Run Isolation Forest
        anomaly_scores, anomaly_labels = detect_risk_anomalies(X)
        
        # Add anomaly information to DataFrame
        scores_df['anomaly_score'] = anomaly_scores
        scores_df['is_anomaly'] = anomaly_labels == -1
        
        # Step 4: Update database
        records_updated = update_anomaly_flags(scores_df, session)
        
        # Log summary statistics
        n_anomalies = scores_df['is_anomaly'].sum()
        logger.info("=" * 80)
        logger.info(f"✓ Anomaly detection complete!")
        logger.info(f"Total sites analyzed: {len(scores_df)}")
        logger.info(f"Anomalies detected: {n_anomalies} ({n_anomalies/len(scores_df)*100:.1f}%)")
        logger.info(f"Records updated: {records_updated}")
        logger.info("=" * 80)
        
        # Show top anomalies
        if n_anomalies > 0:
            top_anomalies = scores_df[scores_df['is_anomaly']].nsmallest(10, 'anomaly_score')
            logger.info(f"\nTop 10 anomalous sites (lowest anomaly scores):")
            for _, row in top_anomalies.iterrows():
                logger.info(f"  Site {row['site_id']}: anomaly_score={row['anomaly_score']:.3f}, "
                           f"composite={row['composite_risk_score']:.3f}")
        
        return scores_df
        
    except Exception as e:
        logger.error(f"Error during anomaly detection: {e}")
        raise
    finally:
        session.close()


def main():
    """Main entry point for CLI execution."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Detect anomalies in heritage site risk scores using Isolation Forest'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Detect anomalies without updating database'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--contamination',
        type=float,
        default=IF_CONTAMINATION,
        help=f'Expected proportion of anomalies (default: {IF_CONTAMINATION})'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.dry_run:
        logger.info("DRY RUN MODE: Anomalies will be detected but not saved")
        session = get_session()
        try:
            scores_df = load_risk_scores(session)
            if len(scores_df) > 0:
                X, scores_df = prepare_feature_matrix(scores_df)
                anomaly_scores, anomaly_labels = detect_risk_anomalies(
                    X, contamination=args.contamination
                )
                scores_df['anomaly_score'] = anomaly_scores
                scores_df['is_anomaly'] = anomaly_labels == -1
                
                n_anomalies = scores_df['is_anomaly'].sum()
                print(f"\n✓ Dry run complete. Detected {n_anomalies} anomalies "
                      f"out of {len(scores_df)} sites ({n_anomalies/len(scores_df)*100:.1f}%)")
                
                if n_anomalies > 0:
                    print(f"\nTop 10 anomalous sites:")
                    print(scores_df[scores_df['is_anomaly']].nsmallest(10, 'anomaly_score')[
                        ['site_id', 'anomaly_score', 'composite_risk_score']
                    ])
        finally:
            session.close()
    else:
        # Normal execution
        scores_df = run_anomaly_detection()
        
        if len(scores_df) > 0:
            n_anomalies = scores_df['is_anomaly'].sum()
            print(f"\n✓ Anomaly detection complete!")
            print(f"Detected {n_anomalies} anomalies out of {len(scores_df)} sites")


if __name__ == '__main__':
    main()
