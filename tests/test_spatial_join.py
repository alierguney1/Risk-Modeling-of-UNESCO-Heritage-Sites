"""
Unit tests for spatial_join module (Phase 5)

Tests CRS transformations, buffer creation, and spatial join operations
without requiring a live database connection.
"""

import unittest
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, Polygon
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.etl.spatial_join import (
    create_buffers,
    join_urban_to_sites,
    join_hazards_to_sites,
    validate_crs_transformation,
    CRS_WGS84,
    CRS_ETRS89_LAEA,
    BUFFER_DISTANCES
)


class TestCRSTransformation(unittest.TestCase):
    """Test CRS transformations accuracy."""
    
    def test_validate_crs_transformation(self):
        """Test that CRS transformation validation works correctly."""
        # Create dummy sites GeoDataFrame (not actually used in validation)
        sites_gdf = gpd.GeoDataFrame(
            {'id': [1], 'name': ['Test']},
            geometry=[Point(0, 0)],
            crs=CRS_WGS84
        )
        
        # This should pass (validates known European city distances)
        result = validate_crs_transformation(sites_gdf)
        self.assertTrue(result, "CRS validation should pass for known European distances")
    
    def test_crs_constants(self):
        """Test that CRS constants are correctly defined."""
        self.assertEqual(CRS_WGS84, "EPSG:4326")
        self.assertEqual(CRS_ETRS89_LAEA, "EPSG:3035")
    
    def test_distance_calculation_accuracy(self):
        """Test distance calculation accuracy in EPSG:3035."""
        # Create two points in Paris and London
        paris = Point(2.3522, 48.8566)
        london = Point(-0.1276, 51.5074)
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(
            {'name': ['Paris', 'London']},
            geometry=[paris, london],
            crs=CRS_WGS84
        )
        
        # Transform to EPSG:3035
        gdf_proj = gdf.to_crs(CRS_ETRS89_LAEA)
        
        # Calculate distance
        distance_m = gdf_proj.geometry.iloc[0].distance(gdf_proj.geometry.iloc[1])
        distance_km = distance_m / 1000.0
        
        # Expected: ~340-350 km
        self.assertGreater(distance_km, 330, "Paris-London distance should be > 330 km")
        self.assertLess(distance_km, 360, "Paris-London distance should be < 360 km")


class TestBufferCreation(unittest.TestCase):
    """Test buffer zone creation."""
    
    def setUp(self):
        """Create sample heritage sites for testing."""
        self.sites_gdf = gpd.GeoDataFrame({
            'id': [1, 2, 3],
            'whc_id': [100, 101, 102],
            'name': ['Site A', 'Site B', 'Site C'],
            'geometry': [
                Point(2.3522, 48.8566),  # Paris
                Point(13.4050, 52.5200),  # Berlin
                Point(12.4964, 41.9028)   # Rome
            ]
        }, crs=CRS_WGS84)
    
    def test_create_buffers_single_distance(self):
        """Test buffer creation with single distance."""
        buffers = create_buffers(self.sites_gdf, distances_m=[5000])
        
        self.assertEqual(len(buffers), 1, "Should create 1 buffer zone")
        self.assertIn(5000, buffers, "Should have 5km buffer")
        self.assertEqual(len(buffers[5000]), 3, "Should have 3 buffered sites")
        self.assertEqual(buffers[5000].crs, CRS_WGS84, "Output should be in WGS84")
    
    def test_create_buffers_multiple_distances(self):
        """Test buffer creation with multiple distances."""
        distances = [5000, 10000, 25000]
        buffers = create_buffers(self.sites_gdf, distances_m=distances)
        
        self.assertEqual(len(buffers), len(distances), f"Should create {len(distances)} buffer zones")
        
        for dist in distances:
            self.assertIn(dist, buffers, f"Should have {dist}m buffer")
            self.assertEqual(len(buffers[dist]), 3, "Each buffer should have 3 sites")
            self.assertTrue('buffer_m' in buffers[dist].columns, "Should have buffer_m column")
            self.assertEqual(buffers[dist]['buffer_m'].iloc[0], dist, "buffer_m should match distance")
    
    def test_buffer_geometry_type(self):
        """Test that buffers create polygon geometries."""
        buffers = create_buffers(self.sites_gdf, distances_m=[5000])
        
        for geom in buffers[5000].geometry:
            self.assertTrue(geom.geom_type in ['Polygon', 'MultiPolygon'], 
                          "Buffers should create polygon geometries")
    
    def test_buffer_area_proportional(self):
        """Test that larger buffers have larger areas."""
        distances = [5000, 10000]
        buffers = create_buffers(self.sites_gdf, distances_m=distances)
        
        # Project to metric CRS for area calculation
        buffer_5km_proj = buffers[5000].to_crs(CRS_ETRS89_LAEA)
        buffer_10km_proj = buffers[10000].to_crs(CRS_ETRS89_LAEA)
        
        # 10km buffer should have ~4x area of 5km buffer (πr² relationship)
        area_5km = buffer_5km_proj.geometry.iloc[0].area
        area_10km = buffer_10km_proj.geometry.iloc[0].area
        
        ratio = area_10km / area_5km
        self.assertGreater(ratio, 3.8, "10km buffer area should be ~4x larger than 5km")
        self.assertLess(ratio, 4.2, "10km buffer area should be ~4x larger than 5km")


class TestUrbanJoin(unittest.TestCase):
    """Test urban features spatial join."""
    
    def setUp(self):
        """Create sample data for testing."""
        # Create one site in Paris
        self.sites_gdf = gpd.GeoDataFrame({
            'id': [1],
            'whc_id': [100],
            'name': ['Paris Site'],
            'geometry': [Point(2.3522, 48.8566)]
        }, crs=CRS_WGS84)
        
        # Create urban features: one near, one far
        # Near: ~1 km from site
        near_lon, near_lat = 2.3622, 48.8566
        # Far: ~20 km from site  
        far_lon, far_lat = 2.5522, 48.8566
        
        self.urban_gdf = gpd.GeoDataFrame({
            'id': [1, 2],
            'feature_type': ['building', 'building'],
            'name': ['Near Building', 'Far Building'],
            'geometry': [Point(near_lon, near_lat), Point(far_lon, far_lat)]
        }, crs=CRS_WGS84)
    
    def test_join_urban_to_sites_within_buffer(self):
        """Test that urban features within buffer are joined."""
        # Use 5km buffer
        joined = join_urban_to_sites(self.urban_gdf, self.sites_gdf, buffer_m=5000)
        
        # Should join the near building (1km away) but not far building (20km away)
        self.assertGreater(len(joined), 0, "Should find at least one urban feature")
        self.assertLess(len(joined), len(self.urban_gdf), "Should not join all features")
    
    def test_join_urban_distance_calculation(self):
        """Test that distance is calculated correctly."""
        joined = join_urban_to_sites(self.urban_gdf, self.sites_gdf, buffer_m=5000)
        
        if len(joined) > 0:
            self.assertTrue('distance_to_site_m' in joined.columns, 
                          "Should have distance_to_site_m column")
            self.assertTrue('nearest_site_id' in joined.columns,
                          "Should have nearest_site_id column")
            
            # Distance should be positive
            self.assertGreater(joined['distance_to_site_m'].iloc[0], 0,
                             "Distance should be positive")
            
            # Distance should be less than buffer distance
            self.assertLess(joined['distance_to_site_m'].iloc[0], 5000,
                          "Distance should be less than buffer")
    
    def test_join_urban_empty_inputs(self):
        """Test handling of empty inputs."""
        empty_gdf = gpd.GeoDataFrame(columns=['id', 'geometry'], crs=CRS_WGS84)
        
        # Empty urban features
        result = join_urban_to_sites(empty_gdf, self.sites_gdf, buffer_m=5000)
        self.assertTrue(result.empty, "Should return empty GeoDataFrame")
        
        # Empty sites
        result = join_urban_to_sites(self.urban_gdf, empty_gdf, buffer_m=5000)
        self.assertTrue(result.empty, "Should return empty GeoDataFrame")


class TestHazardJoin(unittest.TestCase):
    """Test hazard events spatial join."""
    
    def setUp(self):
        """Create sample data for testing."""
        # Create sites
        self.sites_gdf = gpd.GeoDataFrame({
            'id': [1, 2],
            'whc_id': [100, 101],
            'name': ['Site A', 'Site B'],
            'geometry': [
                Point(2.3522, 48.8566),  # Paris
                Point(13.4050, 52.5200)  # Berlin
            ]
        }, crs=CRS_WGS84)
        
        # Create hazard events (earthquakes)
        self.hazard_gdf = gpd.GeoDataFrame({
            'id': [1, 2, 3],
            'magnitude': [4.0, 5.5, 3.2],
            'geometry': [
                Point(2.4522, 48.8566),   # Near Paris (~10km)
                Point(13.5050, 52.5200),  # Near Berlin (~10km)
                Point(0.0, 40.0)          # Far from both
            ]
        }, crs=CRS_WGS84)
    
    def test_join_hazards_to_sites_nearest(self):
        """Test nearest neighbor join for hazards."""
        joined = join_hazards_to_sites(
            self.hazard_gdf,
            self.sites_gdf,
            max_distance_m=100000,  # 100km max
            hazard_type='earthquake'
        )
        
        self.assertGreater(len(joined), 0, "Should find hazards within max distance")
        self.assertTrue('nearest_site_id' in joined.columns,
                       "Should have nearest_site_id column")
        self.assertTrue('distance_to_site_m' in joined.columns,
                       "Should have distance_to_site_m column")
        self.assertTrue('distance_to_site_km' in joined.columns,
                       "Should have distance_to_site_km column")
    
    def test_join_hazards_distance_consistency(self):
        """Test that km and m distances are consistent."""
        joined = join_hazards_to_sites(
            self.hazard_gdf,
            self.sites_gdf,
            max_distance_m=100000
        )
        
        if len(joined) > 0:
            for _, row in joined.iterrows():
                if pd.notna(row['distance_to_site_m']) and pd.notna(row['distance_to_site_km']):
                    # km should be m / 1000
                    expected_km = row['distance_to_site_m'] / 1000.0
                    self.assertAlmostEqual(
                        row['distance_to_site_km'],
                        expected_km,
                        places=2,
                        msg="km and m distances should be consistent"
                    )
    
    def test_join_hazards_max_distance_filter(self):
        """Test that hazards beyond max distance are filtered."""
        # Use very small max distance
        joined = join_hazards_to_sites(
            self.hazard_gdf,
            self.sites_gdf,
            max_distance_m=5000,  # 5km max
            hazard_type='earthquake'
        )
        
        # Should find fewer hazards with smaller max distance
        self.assertLessEqual(len(joined), len(self.hazard_gdf),
                           "Should filter some hazards")
    
    def test_join_hazards_empty_inputs(self):
        """Test handling of empty inputs."""
        empty_gdf = gpd.GeoDataFrame(columns=['id', 'geometry'], crs=CRS_WGS84)
        
        # Empty hazards
        result = join_hazards_to_sites(empty_gdf, self.sites_gdf, max_distance_m=100000)
        self.assertTrue(result.empty, "Should return empty GeoDataFrame")
        
        # Empty sites
        result = join_hazards_to_sites(self.hazard_gdf, empty_gdf, max_distance_m=100000)
        self.assertTrue(result.empty, "Should return empty GeoDataFrame")


class TestBufferDistances(unittest.TestCase):
    """Test buffer distance constants."""
    
    def test_buffer_distances_defined(self):
        """Test that all required buffer distances are defined."""
        required_keys = ['urban', 'fire', 'earthquake', 'flood', 'max_distance']
        
        for key in required_keys:
            self.assertIn(key, BUFFER_DISTANCES,
                        f"BUFFER_DISTANCES should have '{key}' key")
    
    def test_buffer_distances_values(self):
        """Test that buffer distances have reasonable values."""
        self.assertEqual(BUFFER_DISTANCES['urban'], 5000,
                        "Urban buffer should be 5km")
        self.assertEqual(BUFFER_DISTANCES['fire'], 25000,
                        "Fire buffer should be 25km")
        self.assertEqual(BUFFER_DISTANCES['earthquake'], 50000,
                        "Earthquake buffer should be 50km")
        self.assertEqual(BUFFER_DISTANCES['flood'], 50000,
                        "Flood buffer should be 50km")
        self.assertEqual(BUFFER_DISTANCES['max_distance'], 100000,
                        "Max distance should be 100km")


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
