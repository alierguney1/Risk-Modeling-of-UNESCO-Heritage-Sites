"""
Pytest configuration and shared fixtures for UNESCO Risk Modeling tests.

This module provides reusable fixtures for:
- Database sessions
- Sample geographic data
- Mock API responses
- Test data cleanup
"""

import pytest
import geopandas as gpd
from shapely.geometry import Point
import pandas as pd
import numpy as np
from unittest.mock import MagicMock
from datetime import datetime, timedelta


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture(scope='session')
def db_engine():
    """
    Create a database engine for the test session.
    
    Returns:
        SQLAlchemy engine connected to test database.
    """
    from src.db.connection import engine
    return engine


@pytest.fixture(scope='function')
def db_session(db_engine):
    """
    Create a new database session for each test function.
    
    Provides transaction rollback after each test to ensure isolation.
    
    Yields:
        SQLAlchemy Session object
    """
    from src.db.connection import get_session
    
    session = get_session()
    
    yield session
    
    # Rollback transaction and close session after test
    session.rollback()
    session.close()


# ============================================================================
# SAMPLE GEOGRAPHIC DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_heritage_sites():
    """
    Create sample UNESCO heritage sites as GeoDataFrame.
    
    Returns 5 European sites with realistic coordinates and attributes.
    
    Returns:
        GeoDataFrame with sample heritage sites
    """
    data = {
        'whc_id': [91, 94, 252, 445, 709],
        'name': [
            'Venice and its Lagoon',
            'Historic Centre of Rome',
            'Acropolis, Athens',
            'Historic Areas of Istanbul',
            'Tower of London'
        ],
        'category': ['Cultural', 'Cultural', 'Cultural', 'Cultural', 'Cultural'],
        'date_inscribed': [1987, 1980, 1987, 1985, 1988],
        'country': ['Italy', 'Italy', 'Greece', 'Turkey', 'United Kingdom'],
        'iso_code': ['IT', 'IT', 'GR', 'TR', 'GB'],
        'region': ['Europe'] * 5,
        'criteria': [
            '(i)(ii)(iii)(iv)(v)(vi)',
            '(i)(ii)(iii)(iv)(vi)',
            '(i)(ii)(iii)(iv)(vi)',
            '(i)(ii)(iii)(iv)',
            '(ii)(iv)'
        ],
        'in_danger': [False, False, False, False, False],
        'area_hectares': [7092.0, 1430.0, 3.0, 678.0, 7.3],
        'description': [
            'Venice is a unique artistic achievement.',
            'Historic centre of Rome.',
            'The Acropolis of Athens.',
            'Historic Areas of Istanbul.',
            'The Tower of London.'
        ],
        'latitude': [45.4371908, 41.8954656, 37.9715323, 41.0082376, 51.5081124],
        'longitude': [12.3345898, 12.4823243, 23.7257492, 28.9783589, -0.0759493]
    }
    
    # Create geometry column
    geometry = [Point(lon, lat) for lat, lon in zip(data['latitude'], data['longitude'])]
    
    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(data, geometry=geometry, crs='EPSG:4326')
    
    return gdf


@pytest.fixture
def sample_urban_features():
    """
    Create sample OSM urban features near heritage sites.
    
    Returns:
        GeoDataFrame with sample urban features (buildings, landuse)
    """
    # Features near Venice (site_id would be 1 in actual DB)
    data = {
        'osm_id': ['123456', '234567', '345678'],
        'osm_type': ['way', 'way', 'way'],
        'feature_type': ['building', 'building', 'landuse'],
        'feature_value': ['residential', 'commercial', 'retail'],
        'area_m2': [250.5, 1200.8, 5000.0],
        'latitude': [45.4380, 45.4365, 45.4355],
        'longitude': [12.3350, 12.3340, 12.3330]
    }
    
    geometry = [Point(lon, lat) for lat, lon in zip(data['latitude'], data['longitude'])]
    gdf = gpd.GeoDataFrame(data, geometry=geometry, crs='EPSG:4326')
    
    return gdf


@pytest.fixture
def sample_earthquake_events():
    """
    Create sample earthquake events.
    
    Returns:
        GeoDataFrame with sample earthquakes
    """
    data = {
        'usgs_id': ['us1000abc', 'us1000def', 'us1000ghi'],
        'magnitude': [6.2, 5.5, 4.8],
        'depth_km': [10.0, 15.2, 8.5],
        'event_time': [
            datetime(2023, 2, 6, 1, 17, 35),
            datetime(2023, 5, 15, 14, 22, 10),
            datetime(2023, 8, 20, 8, 45, 0)
        ],
        'place': ['Turkey', 'Greece', 'Italy'],
        'latitude': [37.2, 38.5, 42.1],
        'longitude': [37.0, 22.3, 13.2]
    }
    
    geometry = [Point(lon, lat) for lat, lon in zip(data['latitude'], data['longitude'])]
    gdf = gpd.GeoDataFrame(data, geometry=geometry, crs='EPSG:4326')
    
    return gdf


@pytest.fixture
def sample_climate_events():
    """
    Create sample climate events time series.
    
    Returns:
        DataFrame with climate data
    """
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    
    data = {
        'site_id': [1] * len(dates),
        'event_date': dates,
        'temp_max_c': np.random.uniform(15, 35, len(dates)),
        'temp_min_c': np.random.uniform(5, 20, len(dates)),
        'precipitation_mm': np.random.exponential(5, len(dates)),
        'wind_speed_kmh': np.random.uniform(0, 30, len(dates)),
        'solar_radiation_wm2': np.random.uniform(100, 300, len(dates))
    }
    
    return pd.DataFrame(data)


# ============================================================================
# MOCK API RESPONSE FIXTURES
# ============================================================================

@pytest.fixture
def mock_unesco_xml():
    """
    Mock UNESCO XML API response.
    
    Returns:
        str: Sample XML response with 2 sites
    """
    return """<?xml version="1.0" encoding="UTF-8"?>
<query>
    <row>
        <id_number>91</id_number>
        <site>Venice and its Lagoon</site>
        <category>Cultural</category>
        <date_inscribed>1987</date_inscribed>
        <states>Italy</states>
        <iso_code>IT</iso_code>
        <region>Europe and North America</region>
        <criteria_txt>(i)(ii)(iii)(iv)(v)(vi)</criteria_txt>
        <danger>0</danger>
        <area_hectares>7092.0</area_hectares>
        <latitude>45.4371908</latitude>
        <longitude>12.3345898</longitude>
        <short_description>Venice is extraordinary.</short_description>
    </row>
    <row>
        <id_number>94</id_number>
        <site>Historic Centre of Rome</site>
        <category>Cultural</category>
        <date_inscribed>1980</date_inscribed>
        <states>Italy</states>
        <iso_code>IT</iso_code>
        <region>Europe and North America</region>
        <criteria_txt>(i)(ii)(iii)(iv)(vi)</criteria_txt>
        <danger>0</danger>
        <area_hectares>1430.0</area_hectares>
        <latitude>41.8954656</latitude>
        <longitude>12.4823243</longitude>
        <short_description>Historic Centre of Rome.</short_description>
    </row>
</query>"""


@pytest.fixture
def mock_usgs_earthquake_response():
    """
    Mock USGS Earthquake Catalog API response.
    
    Returns:
        dict: Sample GeoJSON response
    """
    return {
        "type": "FeatureCollection",
        "metadata": {
            "generated": 1676505600000,
            "count": 2
        },
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "mag": 6.2,
                    "place": "Turkey",
                    "time": 1675647455000,
                    "updated": 1675650000000,
                    "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us1000abc",
                    "detail": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/detail/us1000abc.geojson",
                    "felt": 500,
                    "cdi": 7.5,
                    "mmi": 8.0,
                    "alert": "red",
                    "status": "reviewed",
                    "tsunami": 0,
                    "sig": 900,
                    "net": "us",
                    "code": "1000abc",
                    "ids": ",us1000abc,",
                    "sources": ",us,",
                    "types": ",origin,phase-data,",
                    "nst": 150,
                    "dmin": 0.5,
                    "rms": 0.8,
                    "gap": 45,
                    "magType": "mww",
                    "type": "earthquake"
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [37.0, 37.2, 10.0]
                },
                "id": "us1000abc"
            },
            {
                "type": "Feature",
                "properties": {
                    "mag": 5.5,
                    "place": "Greece",
                    "time": 1684156930000,
                    "type": "earthquake"
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [22.3, 38.5, 15.2]
                },
                "id": "us1000def"
            }
        ]
    }


# ============================================================================
# RISK SCORING FIXTURES
# ============================================================================

@pytest.fixture
def sample_risk_weights():
    """
    Standard risk weights for testing.
    
    Returns:
        dict: Risk category weights that sum to 1.0
    """
    return {
        'urban_density_score': 0.25,
        'climate_anomaly_score': 0.20,
        'seismic_risk_score': 0.20,
        'fire_risk_score': 0.15,
        'flood_risk_score': 0.10,
        'coastal_risk_score': 0.10
    }


@pytest.fixture
def sample_risk_scores():
    """
    Sample risk scores DataFrame for testing composite calculations.
    
    Returns:
        DataFrame with normalized risk scores
    """
    data = {
        'site_id': [1, 2, 3, 4, 5],
        'urban_density_score': [0.8, 0.3, 0.6, 0.1, 0.9],
        'climate_anomaly_score': [0.4, 0.7, 0.2, 0.5, 0.3],
        'seismic_risk_score': [0.6, 0.2, 0.8, 0.1, 0.4],
        'fire_risk_score': [0.2, 0.5, 0.3, 0.6, 0.7],
        'flood_risk_score': [0.7, 0.1, 0.4, 0.2, 0.5],
        'coastal_risk_score': [0.9, 0.0, 0.3, 0.0, 0.6]
    }
    
    return pd.DataFrame(data)


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
def reset_test_data(db_session):
    """
    Automatically clean up test data after each test.
    
    This fixture runs after every test to ensure test isolation.
    """
    yield
    
    # Cleanup happens here after the test completes
    # The db_session fixture already handles rollback
    pass


# ============================================================================
# CONFIGURATION FIXTURES
# ============================================================================

@pytest.fixture
def europe_bbox():
    """
    Europe bounding box coordinates.
    
    Returns:
        tuple: (min_lat, max_lat, min_lon, max_lon)
    """
    return (34.0, 72.0, -25.0, 45.0)


@pytest.fixture
def europe_iso_codes():
    """
    List of European ISO country codes.
    
    Returns:
        set: ISO 3166-1 alpha-2 codes for European countries
    """
    return {
        'AL', 'AD', 'AT', 'BY', 'BE', 'BA', 'BG', 'HR', 'CY', 'CZ',
        'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IS', 'IE', 'IT',
        'XK', 'LV', 'LI', 'LT', 'LU', 'MT', 'MD', 'MC', 'ME', 'NL',
        'MK', 'NO', 'PL', 'PT', 'RO', 'RU', 'SM', 'RS', 'SK', 'SI',
        'ES', 'SE', 'CH', 'TR', 'UA', 'GB', 'VA'
    }


# ============================================================================
# UTILITY FIXTURES
# ============================================================================

@pytest.fixture
def temp_output_dir(tmp_path):
    """
    Create a temporary directory for test outputs.
    
    Args:
        tmp_path: pytest built-in fixture
    
    Returns:
        Path object to temporary directory
    """
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def mock_logger():
    """
    Mock logger for testing logging behavior.
    
    Returns:
        MagicMock: Mock logger object
    """
    return MagicMock()
