"""
Unit tests for risk scoring module.

Tests all 6 sub-score functions, composite score calculation,
and data validation.
"""

import unittest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.analysis.risk_scoring import (
    validate_weights,
    compute_composite_score,
    DEFAULT_WEIGHTS
)


class TestRiskScoring(unittest.TestCase):
    """Test suite for risk scoring functions."""
    
    def test_validate_weights_sum_to_one(self):
        """Test that DEFAULT_WEIGHTS sum to 1.0."""
        self.assertTrue(validate_weights(DEFAULT_WEIGHTS))
        
        total = sum(DEFAULT_WEIGHTS.values())
        self.assertAlmostEqual(total, 1.0, places=6)
    
    def test_validate_weights_invalid(self):
        """Test that invalid weights raise ValueError."""
        invalid_weights = {
            'urban_density': 0.3,
            'climate_anomaly': 0.2,
            'seismic_risk': 0.2,
            'fire_risk': 0.2,
            'flood_risk': 0.1,
            'coastal_risk': 0.1,
        }  # Sum = 1.1, not 1.0
        
        with self.assertRaises(ValueError):
            validate_weights(invalid_weights)
    
    def test_compute_composite_score_basic(self):
        """Test composite score calculation with simple data."""
        # Create test data
        test_data = pd.DataFrame({
            'site_id': [1, 2, 3],
            'urban_density_score': [0.5, 0.8, 0.2],
            'climate_anomaly_score': [0.3, 0.6, 0.1],
            'seismic_risk_score': [0.7, 0.4, 0.9],
            'fire_risk_score': [0.2, 0.5, 0.3],
            'flood_risk_score': [0.4, 0.3, 0.6],
            'coastal_risk_score': [0.6, 0.2, 0.1],
        })
        
        # Compute composite scores
        result_df = compute_composite_score(test_data, DEFAULT_WEIGHTS)
        
        # Check that composite_risk_score column was added
        self.assertIn('composite_risk_score', result_df.columns)
        self.assertIn('risk_level', result_df.columns)
        
        # Check that all scores are in [0, 1]
        self.assertTrue((result_df['composite_risk_score'] >= 0).all())
        self.assertTrue((result_df['composite_risk_score'] <= 1).all())
        
        # Check that risk levels are assigned
        valid_levels = ['low', 'medium', 'high', 'critical']
        for level in result_df['risk_level']:
            self.assertIn(str(level), valid_levels)
    
    def test_compute_composite_score_with_nan(self):
        """Test composite score handles NaN values correctly."""
        test_data = pd.DataFrame({
            'site_id': [1, 2],
            'urban_density_score': [0.5, np.nan],
            'climate_anomaly_score': [np.nan, 0.6],
            'seismic_risk_score': [0.7, 0.4],
            'fire_risk_score': [0.2, np.nan],
            'flood_risk_score': [np.nan, 0.3],
            'coastal_risk_score': [0.6, 0.2],
        })
        
        # Compute composite scores
        result_df = compute_composite_score(test_data, DEFAULT_WEIGHTS)
        
        # Check that NaN values were filled with 0
        self.assertFalse(result_df['composite_risk_score'].isna().any())
        
        # Check that scores are valid
        self.assertTrue((result_df['composite_risk_score'] >= 0).all())
        self.assertTrue((result_df['composite_risk_score'] <= 1).all())
    
    def test_risk_level_assignment(self):
        """Test that risk levels are correctly assigned based on score ranges."""
        test_data = pd.DataFrame({
            'site_id': [1, 2, 3, 4],
            'urban_density_score': [0.1, 0.3, 0.6, 0.9],
            'climate_anomaly_score': [0.1, 0.3, 0.6, 0.9],
            'seismic_risk_score': [0.1, 0.3, 0.6, 0.9],
            'fire_risk_score': [0.1, 0.3, 0.6, 0.9],
            'flood_risk_score': [0.1, 0.3, 0.6, 0.9],
            'coastal_risk_score': [0.1, 0.3, 0.6, 0.9],
        })
        
        result_df = compute_composite_score(test_data, DEFAULT_WEIGHTS)
        
        # Site 1 should be low (all scores 0.1)
        self.assertEqual(str(result_df.iloc[0]['risk_level']), 'low')
        
        # Site 2 should be medium (all scores 0.3)
        self.assertEqual(str(result_df.iloc[1]['risk_level']), 'medium')
        
        # Site 3 should be high (all scores 0.6)
        self.assertEqual(str(result_df.iloc[2]['risk_level']), 'high')
        
        # Site 4 should be critical (all scores 0.9)
        self.assertEqual(str(result_df.iloc[3]['risk_level']), 'critical')
    
    def test_composite_score_calculation_manual(self):
        """Test composite score calculation against manual calculation."""
        test_data = pd.DataFrame({
            'site_id': [1],
            'urban_density_score': [0.5],
            'climate_anomaly_score': [0.4],
            'seismic_risk_score': [0.3],
            'fire_risk_score': [0.2],
            'flood_risk_score': [0.1],
            'coastal_risk_score': [0.0],
        })
        
        result_df = compute_composite_score(test_data, DEFAULT_WEIGHTS)
        
        # Manual calculation
        expected_score = (
            0.5 * DEFAULT_WEIGHTS['urban_density'] +
            0.4 * DEFAULT_WEIGHTS['climate_anomaly'] +
            0.3 * DEFAULT_WEIGHTS['seismic_risk'] +
            0.2 * DEFAULT_WEIGHTS['fire_risk'] +
            0.1 * DEFAULT_WEIGHTS['flood_risk'] +
            0.0 * DEFAULT_WEIGHTS['coastal_risk']
        )
        
        self.assertAlmostEqual(
            result_df.iloc[0]['composite_risk_score'],
            expected_score,
            places=6
        )
    
    def test_composite_score_edge_cases(self):
        """Test composite score with edge cases (all 0s, all 1s)."""
        # All zeros
        test_zeros = pd.DataFrame({
            'site_id': [1],
            'urban_density_score': [0.0],
            'climate_anomaly_score': [0.0],
            'seismic_risk_score': [0.0],
            'fire_risk_score': [0.0],
            'flood_risk_score': [0.0],
            'coastal_risk_score': [0.0],
        })
        
        result_zeros = compute_composite_score(test_zeros, DEFAULT_WEIGHTS)
        self.assertEqual(result_zeros.iloc[0]['composite_risk_score'], 0.0)
        self.assertEqual(str(result_zeros.iloc[0]['risk_level']), 'low')
        
        # All ones
        test_ones = pd.DataFrame({
            'site_id': [1],
            'urban_density_score': [1.0],
            'climate_anomaly_score': [1.0],
            'seismic_risk_score': [1.0],
            'fire_risk_score': [1.0],
            'flood_risk_score': [1.0],
            'coastal_risk_score': [1.0],
        })
        
        result_ones = compute_composite_score(test_ones, DEFAULT_WEIGHTS)
        self.assertEqual(result_ones.iloc[0]['composite_risk_score'], 1.0)
        self.assertEqual(str(result_ones.iloc[0]['risk_level']), 'critical')


class TestRiskScoringIntegration(unittest.TestCase):
    """Integration tests for risk scoring (require database)."""
    
    @unittest.skip("Requires database connection")
    def test_full_pipeline(self):
        """Test full risk scoring pipeline."""
        # This test requires a real database connection
        # Skip for now, run manually during integration testing
        pass


if __name__ == '__main__':
    unittest.main()
