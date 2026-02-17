"""
Unit tests for anomaly detection module.

Tests Isolation Forest implementation and anomaly flag updates.
"""

import unittest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock

from src.analysis.anomaly_detection import (
    prepare_feature_matrix,
    detect_risk_anomalies
)
from config.settings import IF_CONTAMINATION, IF_N_ESTIMATORS, IF_RANDOM_STATE


class TestAnomalyDetection(unittest.TestCase):
    """Test suite for anomaly detection functions."""
    
    def test_prepare_feature_matrix_basic(self):
        """Test feature matrix preparation with valid data."""
        test_data = pd.DataFrame({
            'site_id': [1, 2, 3],
            'urban_density_score': [0.5, 0.8, 0.2],
            'climate_anomaly_score': [0.3, 0.6, 0.1],
            'seismic_risk_score': [0.7, 0.4, 0.9],
            'fire_risk_score': [0.2, 0.5, 0.3],
            'flood_risk_score': [0.4, 0.3, 0.6],
            'coastal_risk_score': [0.6, 0.2, 0.1],
        })
        
        X, df = prepare_feature_matrix(test_data)
        
        # Check shape
        self.assertEqual(X.shape, (3, 6))
        
        # Check that all values are numeric
        self.assertTrue(np.isfinite(X).all())
    
    def test_prepare_feature_matrix_with_nan(self):
        """Test that NaN values are replaced with 0."""
        test_data = pd.DataFrame({
            'site_id': [1, 2],
            'urban_density_score': [0.5, np.nan],
            'climate_anomaly_score': [np.nan, 0.6],
            'seismic_risk_score': [0.7, 0.4],
            'fire_risk_score': [0.2, np.nan],
            'flood_risk_score': [np.nan, 0.3],
            'coastal_risk_score': [0.6, 0.2],
        })
        
        X, df = prepare_feature_matrix(test_data)
        
        # Check that no NaN values remain
        self.assertFalse(np.isnan(X).any())
        
        # Check that NaN was replaced with 0
        self.assertEqual(X[0, 1], 0.0)  # climate_anomaly_score for site 1
        self.assertEqual(X[1, 0], 0.0)  # urban_density_score for site 2
    
    def test_prepare_feature_matrix_missing_columns(self):
        """Test feature matrix with missing columns (should add them as 0)."""
        test_data = pd.DataFrame({
            'site_id': [1, 2, 3],
            'urban_density_score': [0.5, 0.8, 0.2],
            'climate_anomaly_score': [0.3, 0.6, 0.1],
            # Missing other score columns
        })
        
        X, df = prepare_feature_matrix(test_data)
        
        # Should still have 6 features
        self.assertEqual(X.shape[1], 6)
        
        # Missing columns should be filled with 0
        self.assertTrue(np.allclose(X[:, 2:], 0.0))
    
    def test_detect_risk_anomalies_basic(self):
        """Test Isolation Forest anomaly detection."""
        # Create test data with one clear outlier
        np.random.seed(42)
        X = np.random.normal(0.5, 0.1, size=(100, 6))
        # Add one outlier
        X[0, :] = [0.95, 0.95, 0.95, 0.95, 0.95, 0.95]
        
        anomaly_scores, anomaly_labels = detect_risk_anomalies(
            X,
            n_estimators=IF_N_ESTIMATORS,
            contamination=IF_CONTAMINATION,
            random_state=IF_RANDOM_STATE
        )
        
        # Check output shapes
        self.assertEqual(len(anomaly_scores), 100)
        self.assertEqual(len(anomaly_labels), 100)
        
        # Check that labels are -1 (anomaly) or 1 (normal)
        self.assertTrue(np.all(np.isin(anomaly_labels, [-1, 1])))
        
        # Check that some anomalies were detected
        n_anomalies = np.sum(anomaly_labels == -1)
        self.assertGreater(n_anomalies, 0)
        
        # Check that contamination rate is approximately correct
        anomaly_rate = n_anomalies / len(anomaly_labels)
        self.assertLessEqual(anomaly_rate, IF_CONTAMINATION + 0.05)
    
    def test_detect_risk_anomalies_all_same(self):
        """Test anomaly detection when all data points are the same."""
        # All data points identical
        X = np.ones((50, 6)) * 0.5
        
        anomaly_scores, anomaly_labels = detect_risk_anomalies(
            X,
            n_estimators=50,
            contamination=0.1,
            random_state=42
        )
        
        # Should still produce valid output
        self.assertEqual(len(anomaly_scores), 50)
        self.assertEqual(len(anomaly_labels), 50)
        
        # All labels should be valid
        self.assertTrue(np.all(np.isin(anomaly_labels, [-1, 1])))
    
    def test_detect_risk_anomalies_reproducibility(self):
        """Test that anomaly detection is reproducible with fixed random_state."""
        np.random.seed(42)
        X = np.random.normal(0.5, 0.2, size=(100, 6))
        
        # Run twice with same random state
        scores1, labels1 = detect_risk_anomalies(X, random_state=42)
        scores2, labels2 = detect_risk_anomalies(X, random_state=42)
        
        # Results should be identical
        np.testing.assert_array_equal(labels1, labels2)
        np.testing.assert_array_almost_equal(scores1, scores2)
    
    def test_detect_risk_anomalies_contamination_parameter(self):
        """Test different contamination rates."""
        np.random.seed(42)
        X = np.random.normal(0.5, 0.1, size=(100, 6))
        
        # Test with low contamination
        _, labels_low = detect_risk_anomalies(X, contamination=0.05, random_state=42)
        n_anomalies_low = np.sum(labels_low == -1)
        
        # Test with high contamination
        _, labels_high = detect_risk_anomalies(X, contamination=0.20, random_state=42)
        n_anomalies_high = np.sum(labels_high == -1)
        
        # Higher contamination should detect more anomalies
        self.assertGreater(n_anomalies_high, n_anomalies_low)
    
    def test_anomaly_score_properties(self):
        """Test properties of anomaly scores."""
        np.random.seed(42)
        X = np.random.normal(0.5, 0.1, size=(100, 6))
        
        anomaly_scores, anomaly_labels = detect_risk_anomalies(X, random_state=42)
        
        # Anomaly scores should be continuous
        self.assertTrue(np.isfinite(anomaly_scores).all())
        
        # Anomalies should have lower (more negative) scores than normal points
        anomaly_mean_score = anomaly_scores[anomaly_labels == -1].mean()
        normal_mean_score = anomaly_scores[anomaly_labels == 1].mean()
        self.assertLess(anomaly_mean_score, normal_mean_score)


class TestAnomalyDetectionIntegration(unittest.TestCase):
    """Integration tests for anomaly detection (require database)."""
    
    @unittest.skip("Requires database connection")
    def test_full_pipeline(self):
        """Test full anomaly detection pipeline."""
        # This test requires a real database connection
        # Skip for now, run manually during integration testing
        pass


if __name__ == '__main__':
    unittest.main()
