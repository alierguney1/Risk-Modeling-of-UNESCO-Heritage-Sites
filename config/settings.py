"""
Central configuration for the UNESCO Heritage Sites Risk Modeling project.

All constants: CRS codes, bounding box, buffer distances, risk weights,
API URLs, European ISO country codes, and model parameters.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# CRS Constants
# ---------------------------------------------------------------------------
SRC_CRS = 4326          # WGS84 — storage & API communication
PROJ_CRS = 3035         # ETRS89/LAEA Europe — metric computations

# ---------------------------------------------------------------------------
# Europe Bounding Box
# ---------------------------------------------------------------------------
EUROPE_BBOX = {
    "min_lat": 34,
    "max_lat": 72,
    "min_lon": -25,
    "max_lon": 45,
}

# ---------------------------------------------------------------------------
# Buffer Distances (meters)
# ---------------------------------------------------------------------------
BUFFER_DISTANCES = [5000, 10000, 25000, 50000]
OSM_BUFFER_M = 5000     # Default OSM extraction radius

# ---------------------------------------------------------------------------
# Risk Weights
# ---------------------------------------------------------------------------
RISK_WEIGHTS = {
    "urban_density": 0.25,
    "climate_anomaly": 0.20,
    "seismic_risk": 0.20,
    "fire_risk": 0.15,
    "flood_risk": 0.10,
    "coastal_risk": 0.10,
}

# ---------------------------------------------------------------------------
# Isolation Forest Parameters
# ---------------------------------------------------------------------------
IF_CONTAMINATION = 0.10
IF_N_ESTIMATORS = 200
IF_RANDOM_STATE = 42

# ---------------------------------------------------------------------------
# API URLs
# ---------------------------------------------------------------------------
UNESCO_XML_URL = "https://whc.unesco.org/en/list/xml/"
UNESCO_JSON_URL = "https://whc.unesco.org/en/list/?action=list&format=json"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_CLIMATE_URL = "https://climate-api.open-meteo.com/v1/climate"
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
USGS_EARTHQUAKE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
FIRMS_API_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
OPENTOPO_API_URL = "https://portal.opentopography.org/API/globaldem"
GFMS_URL = "https://flood.umd.edu/"

# ---------------------------------------------------------------------------
# Climate Data Range
# ---------------------------------------------------------------------------
CLIMATE_START_DATE = "2020-01-01"
CLIMATE_END_DATE = "2025-12-31"

# ---------------------------------------------------------------------------
# Open-Meteo Daily Variables
# ---------------------------------------------------------------------------
OPEN_METEO_DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "windspeed_10m_max",
    "windgusts_10m_max",
    "precipitation_hours",
    "et0_fao_evapotranspiration",
]

# ---------------------------------------------------------------------------
# NASA POWER Variables
# ---------------------------------------------------------------------------
NASA_POWER_PARAMS = "T2M,PRECTOTCORR,WS10M,ALLSKY_SFC_SW_DWN,RH2M"

# ---------------------------------------------------------------------------
# Earthquake Defaults
# ---------------------------------------------------------------------------
EARTHQUAKE_MIN_MAGNITUDE = 3.0
EARTHQUAKE_START_DATE = "2015-01-01"
EARTHQUAKE_END_DATE = "2025-12-31"

# ---------------------------------------------------------------------------
# FIRMS Fire Defaults
# ---------------------------------------------------------------------------
FIRMS_DEFAULT_SOURCE = "VIIRS_SNPP_NRT"
FIRMS_DEFAULT_DAYS = 10

# ---------------------------------------------------------------------------
# Elevation / Coastal Risk
# ---------------------------------------------------------------------------
DEM_TYPE = "COP30"
DEM_BUFFER_DEG = 0.01
COASTAL_ELEVATION_THRESHOLD_M = 10
COASTAL_DISTANCE_THRESHOLD_KM = 50

# ---------------------------------------------------------------------------
# OSMnx Configuration
# ---------------------------------------------------------------------------
OSMNX_TIMEOUT = 300
OSMNX_CACHE_FOLDER = ".cache/osmnx"
OSMNX_SLEEP_SECONDS = 5

# OSM Tags for Urban Sprawl Analysis
OSM_TAGS = {
    "building": True,
    "landuse": ["residential", "commercial", "industrial", "construction"],
}

# ---------------------------------------------------------------------------
# Risk Level Classification Bins
# ---------------------------------------------------------------------------
RISK_BINS = [0, 0.4, 0.6, 0.8, 1.0]
RISK_LABELS = ["low", "medium", "high", "critical"]

# Risk level colors for visualization
RISK_COLORS = {
    "critical": "#d32f2f",  # Red
    "high": "#f57c00",      # Orange
    "medium": "#fbc02d",    # Yellow
    "low": "#388e3c",       # Green
}

# ---------------------------------------------------------------------------
# Database Configuration (from .env)
# ---------------------------------------------------------------------------
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "unesco_risk")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "changeme")

DATABASE_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# ---------------------------------------------------------------------------
# API Keys (from .env)
# ---------------------------------------------------------------------------
FIRMS_API_KEY = os.getenv("FIRMS_API_KEY", "")
OPENTOPO_API_KEY = os.getenv("OPENTOPO_API_KEY", "")

# ---------------------------------------------------------------------------
# European ISO Country Codes
# ---------------------------------------------------------------------------
EUROPE_ISO_CODES = {
    "TR", "IT", "ES", "FR", "DE", "GR", "GB", "PT", "PL", "CZ",
    "HR", "AT", "CH", "BE", "NL", "SE", "NO", "DK", "FI", "RO",
    "BG", "HU", "SK", "SI", "RS", "BA", "ME", "MK", "AL", "CY",
    "MT", "IS", "IE", "LU", "LT", "LV", "EE", "MD", "UA", "BY",
    "GE", "AM", "AZ", "RU", "AD", "MC", "SM", "VA", "LI", "XK",
}

# ---------------------------------------------------------------------------
# Output Paths
# ---------------------------------------------------------------------------
OUTPUT_MAP_DIR = "output/maps"
DEFAULT_MAP_FILE = "output/maps/europe_risk_map.html"
