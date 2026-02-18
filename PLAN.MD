# Risk Modeling of UNESCO Heritage Sites — Technical Architecture & Implementation Plan

> **Scope**: Europe (~500+ UNESCO sites)  
> **Infrastructure**: Local PostgreSQL/PostGIS + Airflow  
> **Climate Sources**: Open-Meteo (primary) + NASA POWER (supplementary)  
> **Hazard Sources**: USGS Earthquake, NASA FIRMS Fire, GFMS Flood, OpenTopography DEM  

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Data Sources & Structures](#2-data-sources--structures)
3. [PostGIS Database Schema](#3-postgis-database-schema)
4. [ETL Pipeline — Data Fetching Modules](#4-etl-pipeline--data-fetching-modules)
5. [CRS Transformation & Spatial Join](#5-crs-transformation--spatial-join)
6. [Analytical Layer — Multi-Variate Risk Model](#6-analytical-layer--multi-variate-risk-model)
7. [Airflow DAG Design](#7-airflow-dag-design)
8. [Folium Visualization](#8-folium-visualization)
9. [Configuration & Environment Variables](#9-configuration--environment-variables)
10. [Verification & Testing](#10-verification--testing)
11. [Key Decisions](#11-key-decisions)
12. [Development Roadmap](#12-development-roadmap--step-by-step-implementation-guide)

---

## 1. Project Structure

```
Risk-Modeling-of-UNESCO-Heritage-Sites/
├── README.md
├── PLAN.MD
├── requirements.txt
├── setup.py
├── .env.example
├── run_dashboard.py            # Launch interactive dashboard
├── generate_static_visualizations.py  # Export HTML files
├── generate_screenshots.py     # Create PNG screenshots
├── config/
│   └── settings.py             # API URLs, CRS constants, buffer distances
├── sql/
│   ├── 01_create_schema.sql
│   ├── 02_create_tables.sql
│   └── 03_create_indices.sql
├── dags/
│   └── unesco_risk_dag.py      # Airflow DAG definition
├── src/
│   ├── __init__.py
│   ├── etl/
│   │   ├── __init__.py
│   │   ├── fetch_unesco.py     # UNESCO data fetching
│   │   ├── fetch_osm.py        # OSMnx urban features
│   │   ├── fetch_climate.py    # Open-Meteo + NASA POWER
│   │   ├── fetch_earthquake.py # USGS earthquake data
│   │   ├── fetch_fire.py       # NASA FIRMS fire data
│   │   ├── fetch_flood.py      # GFMS flood data
│   │   ├── fetch_elevation.py  # OpenTopography DEM
│   │   └── spatial_join.py     # CRS transform + spatial join
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── risk_scoring.py     # Proximity Risk Score algorithm
│   │   ├── anomaly_detection.py # Isolation Forest model
│   │   └── density_analysis.py # Spatial density analysis
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py       # SQLAlchemy + GeoAlchemy2 connection
│   │   └── models.py           # ORM models
│   └── visualization/
│       ├── __init__.py
│       ├── dash_app.py         # Modern interactive dashboard (PRIMARY)
│       └── folium_map_legacy.py # Legacy static HTML map
│   │   ├── fetch_earthquake.py # USGS earthquake data
│   │   ├── fetch_fire.py       # NASA FIRMS fire data
│   │   ├── fetch_flood.py      # GFMS flood data
│   │   ├── fetch_elevation.py  # OpenTopography DEM
│   │   └── spatial_join.py     # CRS transform + spatial join
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── risk_scoring.py     # Proximity Risk Score algorithm
│   │   ├── anomaly_detection.py # Isolation Forest model
│   │   └── density_analysis.py # Spatial density analysis
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py       # SQLAlchemy + GeoAlchemy2 connection
│   │   └── models.py           # ORM models
│   └── visualization/
│       ├── __init__.py
│       ├── dash_app.py         # Modern interactive dashboard
│       └── folium_map_legacy.py # Legacy static HTML map
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_risk_analysis.ipynb
│   └── 03_visualization.ipynb
├── tests/
│   ├── test_etl.py
│   ├── test_analysis.py
│   └── test_db.py
├── docs/
│   ├── DASHBOARD_GUIDE.md      # Interactive dashboard usage guide
│   ├── DASHBOARD_SHOWCASE.md   # Visual showcase and features
│   └── LEGACY_VS_MODERN.md     # Comparison guide
└── output/
    ├── maps/                   # HTML map outputs (legacy)
    ├── visualizations/         # Interactive HTML files
    └── screenshots/            # PNG screenshots
```

### Dependencies (`requirements.txt`)

```
# Geospatial libraries
geopandas>=0.14
osmnx>=1.9
pyproj>=3.6
shapely>=2.0
rasterio>=1.3

# Data processing
pandas>=2.1
numpy>=1.25
scipy>=1.11

# Database
sqlalchemy>=2.0
geoalchemy2>=0.14
psycopg2-binary>=2.9

# Visualization (Modern)
plotly>=5.18.0
dash>=2.14.0
dash-bootstrap-components>=1.5.0
kaleido>=0.2.1

# Visualization (Legacy)
folium>=0.15

# Machine Learning
scikit-learn>=1.3

# Utilities
requests>=2.31
python-dotenv>=1.0
tqdm>=4.66
cloudscraper>=1.2.71

# Workflow (optional)
apache-airflow>=2.8
rasterio>=1.3
scipy>=1.11
```

---

## 2. Data Sources & Structures

### 2.1 UNESCO World Heritage Sites

| Source | URL | Format | Auth |
|---|---|---|---|
| **UNESCO WHC XML Export** | `https://whc.unesco.org/en/list/xml/` | XML | None |
| **UNESCO WHC KML Export** | `https://whc.unesco.org/en/list/kml/` | KML | None |
| **UNESCO WHC JSON** | `https://whc.unesco.org/en/list/?action=list&format=json` | JSON | None |
| **UNESCO WHC GeoJSON** | `https://whc.unesco.org/en/list/?action=list&format=geojson` | GeoJSON | None |
| **Datahub.io WHC** | `https://datahub.io/core/world-heritage-sites` | CSV, JSON | None |
| **Kaggle UNESCO WHC** | `https://www.kaggle.com/datasets/ujwalkandi/unesco-world-heritage-sites` | CSV | None |

**Data Fields**:

| Field | Type | Description |
|---|---|---|
| `id_number` | int | Unique WHC site ID |
| `site` / `name` | string | Official name |
| `short_description` | string | Brief description |
| `category` | string | `Cultural`, `Natural`, or `Mixed` |
| `date_inscribed` | int | Year inscribed |
| `longitude` | float | Centroid longitude |
| `latitude` | float | Centroid latitude |
| `states` | string | Country/countries |
| `region` | string | UNESCO region (e.g., `Europe and North America`) |
| `iso_code` | string | ISO country codes |
| `criteria_txt` | string | Selection criteria (i-x) |
| `danger` | int/bool | Whether on Danger list |
| `transboundary` | int/bool | Spans multiple countries |
| `area_hectares` | float | Site area |

**Rate limits**: No published rate limits. Recommend caching locally. XML endpoint is stable; JSON/GeoJSON endpoints are undocumented and may change.

---

### 2.2 OpenStreetMap (OSM) via OSMnx

**Fetching Functions**:

```python
# By center point + radius (primary method for per-site extraction)
gdf = ox.features_from_point((lat, lon), tags=tags, dist=5000)

# By bounding box
gdf = ox.features_from_bbox(bbox=(west, south, east, north), tags=tags)

# By place name
gdf = ox.features_from_place("Venice, Italy", tags=tags)
```

All functions use Overpass API internally.

**Relevant OSM Tags for Urban Sprawl**:

| Tag Key | Values | Use Case |
|---|---|---|
| `building` | `True` (all), `residential`, `commercial`, `industrial` | Building footprints |
| `landuse` | `residential`, `commercial`, `industrial`, `retail`, `construction` | Land use classification |
| `highway` | `motorway`, `primary`, `secondary`, `residential` | Road network density |
| `amenity` | `True` (all) | Urban amenity density |
| `leisure` | `park`, `garden`, `playground` | Green space (inverse risk) |
| `natural` | `True` | Natural features |
| `tourism` | `True` | Tourism infrastructure |

**Tag query syntax**:
```python
tags = {
    "building": True,
    "landuse": ["residential", "commercial", "industrial", "construction"],
}
```

**GeoDataFrame Structure Returned**:
- **Multi-index**: `(element_type, osmid)` — `"node"`, `"way"`, or `"relation"` + OSM ID
- **CRS**: `EPSG:4326` (default)
- **geometry column**: Point (nodes), Polygon (closed ways), LineString (open ways), MultiPolygon (relations)
- **Attribute columns**: All OSM tags present become columns (`building`, `landuse`, `name`, `height`, etc.)

**Concerns**: 
- Large area queries can be slow. OSMnx auto-subdivides large polygons.
- Default Overpass timeout: 180s. Set `ox.settings.timeout = 300`.
- Public Overpass API rate limit: ~2 requests/10s. Use `time.sleep(5)` between sites.
- For ~500 European sites: ~42 min total fetch time.

---

### 2.3 Climate/Weather Data

#### 2.3.1 Open-Meteo (Primary — free, no key)

| Detail | Value |
|---|---|
| **Historical endpoint** | `https://archive-api.open-meteo.com/v1/archive` |
| **Forecast endpoint** | `https://api.open-meteo.com/v1/forecast` |
| **Climate change endpoint** | `https://climate-api.open-meteo.com/v1/climate` |
| **Auth** | None required |
| **Rate limit** | 10,000 requests/day (free tier) |
| **Format** | JSON |
| **Temporal range** | 1940–present (archive) |

**Key Parameters**:
- `latitude`, `longitude` — required
- `start_date`, `end_date` — ISO format (e.g., `2020-01-01`)
- `daily` — comma-separated variable list

**Daily Variables**:
| Variable | Unit | Use |
|---|---|---|
| `temperature_2m_max` | °C | Heat wave detection |
| `temperature_2m_min` | °C | Cold snap detection |
| `temperature_2m_mean` | °C | Temperature anomaly baseline |
| `precipitation_sum` | mm | Flood/drought proxy |
| `windspeed_10m_max` | m/s | Storm intensity |
| `windgusts_10m_max` | m/s | Extreme wind events |
| `precipitation_hours` | hours | Sustained rainfall |
| `et0_fao_evapotranspiration` | mm | Drought stress indicator |

**Response Structure**:
```json
{
  "latitude": 48.85,
  "longitude": 2.35,
  "daily": {
    "time": ["2024-01-01", "2024-01-02", "..."],
    "temperature_2m_max": [5.2, 6.1, "..."],
    "precipitation_sum": [0.3, 1.2, "..."]
  },
  "daily_units": {
    "temperature_2m_max": "°C",
    "precipitation_sum": "mm"
  }
}
```

#### 2.3.2 NASA POWER (Supplementary — free, no key)

| Detail | Value |
|---|---|
| **Daily endpoint** | `https://power.larc.nasa.gov/api/temporal/daily/point` |
| **Climatology endpoint** | `https://power.larc.nasa.gov/api/temporal/climatology/point` |
| **Auth** | None required |
| **Rate limit** | ~30 requests/min (throttled) |
| **Format** | JSON, CSV, NetCDF |
| **Temporal range** | 1981–present |

**Key Parameters**:
- `parameters` — e.g., `T2M,PRECTOTCORR,WS10M,ALLSKY_SFC_SW_DWN`
- `community` — `RE` (renewable energy), `SB` (buildings), `AG` (agriculture)
- `longitude`, `latitude`, `start`, `end` (YYYYMMDD format)

**Variables**:
| Variable | Unit | Description |
|---|---|---|
| `T2M` | °C | Temperature at 2m |
| `PRECTOTCORR` | mm/day | Corrected total precipitation |
| `WS10M` | m/s | Wind speed at 10m |
| `ALLSKY_SFC_SW_DWN` | kWh/m²/day | Solar radiation (all sky) |
| `RH2M` | % | Relative humidity at 2m |

**Response Structure**:
```json
{
  "properties": {
    "parameter": {
      "T2M": {"20240101": 5.2, "20240102": 6.1},
      "PRECTOTCORR": {"20240101": 0.3, "20240102": 1.2},
      "ALLSKY_SFC_SW_DWN": {"20240101": 1.85, "20240102": 0.93}
    }
  }
}
```

**Combined usage**: Open-Meteo for temperature, precipitation, wind; NASA POWER for solar radiation. Both sources merged with `source` column differentiation.

---

### 2.4 USGS Earthquake Data

| Detail | Value |
|---|---|
| **Endpoint** | `https://earthquake.usgs.gov/fdsnws/event/1/query` |
| **Auth** | None required |
| **Rate limit** | No strict limit; max 20,000 events per query |
| **Format** | GeoJSON, CSV, KML, XML |

**Key Parameters**:
- `format=geojson`
- `starttime`, `endtime` — ISO 8601 dates
- `minlatitude=34`, `maxlatitude=72`, `minlongitude=-25`, `maxlongitude=45` (Europe bbox)
- `minmagnitude=3.0` — filter out micro-quakes
- `orderby=time` or `magnitude`

**GeoJSON Response Structure**:
```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "properties": {
      "mag": 5.2,
      "place": "35km NW of Athens, Greece",
      "time": 1704067200000,
      "type": "earthquake",
      "sig": 416,
      "mmi": 4.2,
      "alert": "green",
      "tsunami": 0,
      "magType": "mww",
      "title": "M 5.2 - 35km NW of Athens"
    },
    "geometry": {
      "type": "Point",
      "coordinates": [23.7, 37.9, 10.5]
    }
  }]
}
```

**Fields**: `mag` (magnitude), `place` (description), `time` (epoch ms), `sig` (significance 0-1000), `mmi` (Modified Mercalli Intensity), `alert` (green/yellow/orange/red), `tsunami` (0/1), `depth` (geometry coordinates[2] in km).

---

### 2.5 NASA FIRMS Fire Data

| Detail | Value |
|---|---|
| **API endpoint** | `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{source}/{area}/{days}` |
| **Archive download** | `https://firms.modaps.eosdis.nasa.gov/download/` |
| **Auth** | **Free API key required** — register at `https://firms.modaps.eosdis.nasa.gov/api/area/` |
| **Format** | CSV, SHP, KML, GeoJSON (via WFS) |
| **Sources** | MODIS (`MODIS_NRT`), VIIRS S-NPP (`VIIRS_SNPP_NRT`), VIIRS NOAA-20 (`VIIRS_NOAA20_NRT`) |

**CSV Response Fields**:
| Field | Type | Description |
|---|---|---|
| `latitude` | float | Fire detection latitude |
| `longitude` | float | Fire detection longitude |
| `brightness` | float | Brightness temperature (Kelvin) |
| `scan` | float | Scan pixel size |
| `track` | float | Track pixel size |
| `acq_date` | string | Acquisition date (YYYY-MM-DD) |
| `acq_time` | string | Acquisition time (HHMM) |
| `satellite` | string | Terra / Aqua / SNPP / NOAA20 |
| `confidence` | int | 0-100 (VIIRS) or low/nominal/high (MODIS) |
| `frp` | float | Fire Radiative Power (MW) |
| `daynight` | string | D (day) / N (night) |

**Usage**: 10-day NRT data via API; archive data via download endpoint. Europe bbox for regional query.

---

### 2.6 Global Flood Monitoring System (GFMS)

| Detail | Value |
|---|---|
| **URL** | `https://flood.umd.edu/` |
| **Auth** | None required |
| **Format** | GeoTIFF, KML |
| **Resolution** | ~12 km globally |
| **Temporal** | Near real-time + historical archive |

**Processing**: Download GeoTIFF raster → `rasterio` to read → sample pixel value at each heritage site coordinate → flood intensity score. Higher pixel value = greater flood depth/discharge.

**Supplementary Sources**:
| Source | URL | Auth | Format |
|---|---|---|---|
| Dartmouth Flood Observatory | `https://floodobservatory.colorado.edu/Archives/` | None | SHP, KML |
| Copernicus EMS (EFAS) | `https://emergency.copernicus.eu/mapping/` | Registration | NetCDF |

---

### 2.7 OpenTopography DEM (Elevation / Coastal Risk)

| Detail | Value |
|---|---|
| **API endpoint** | `https://portal.opentopography.org/API/globaldem` |
| **Auth** | **Free API key required** — register at OpenTopography portal |
| **DEM type** | `COP30` (Copernicus 30m DEM) — preferred over SRTM for accuracy |
| **Format** | GeoTIFF |

**Key Parameters**:
- `demtype=COP30`
- `south`, `north`, `west`, `east` — small bounding box per site (±0.01°)
- `outputFormat=GTiff`
- `API_Key={OPENTOPO_API_KEY}`

**Processing**: Download small DEM tile → `rasterio` to read → extract elevation at site coordinate → coastal risk scoring:
- Sites with elevation < 10m AND distance to coast < 50km → high coastal risk
- Score formula: `max(0, 1 - (elevation / 10))` for coastal sites; 0 for inland sites

**Alternative DEM Sources**:
| Source | Resolution | URL | Auth |
|---|---|---|---|
| SRTM (NASA) | 30m / 90m | `https://earthexplorer.usgs.gov/` | Earthdata login |
| ALOS World 3D | 30m | `https://www.eorc.jaxa.jp/ALOS/en/aw3d30/` | Registration |
| FABDEM | 30m | `https://data.bris.ac.uk/data/dataset/25wfy0f9ukoge2gs7a5mqpq2j7` | None |

---

## 3. PostGIS Database Schema

### 3.1 Schema Creation (`sql/01_create_schema.sql`)

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS unesco_risk;
SET search_path TO unesco_risk, public;
```

### 3.2 Table Definitions (`sql/02_create_tables.sql`)

#### Table 1: `heritage_sites` — UNESCO Heritage Sites (Point)

```sql
CREATE TABLE heritage_sites (
    id              SERIAL PRIMARY KEY,
    whc_id          INTEGER UNIQUE NOT NULL,
    name            VARCHAR(500) NOT NULL,
    category        VARCHAR(20) CHECK (category IN ('Cultural', 'Natural', 'Mixed')),
    date_inscribed  INTEGER,
    country         VARCHAR(200),
    iso_code        VARCHAR(20),
    region          VARCHAR(100),
    criteria        VARCHAR(100),
    in_danger       BOOLEAN DEFAULT FALSE,
    area_hectares   FLOAT,
    description     TEXT,
    geom            GEOMETRY(Point, 4326) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
```

#### Table 2: `urban_features` — OSM Urban Features (Polygon/Geometry)

```sql
CREATE TABLE urban_features (
    id               SERIAL PRIMARY KEY,
    osm_id           BIGINT,
    osm_type         VARCHAR(10),
    feature_type     VARCHAR(50) NOT NULL,
    feature_value    VARCHAR(100),
    name             VARCHAR(500),
    nearest_site_id  INTEGER REFERENCES heritage_sites(id),
    distance_to_site_m FLOAT,
    geom             GEOMETRY(Geometry, 4326) NOT NULL,
    fetched_at       TIMESTAMP DEFAULT NOW()
);
```

#### Table 3: `climate_events` — Climate Time-Series (Open-Meteo + NASA POWER)

```sql
CREATE TABLE climate_events (
    id                  SERIAL PRIMARY KEY,
    site_id             INTEGER REFERENCES heritage_sites(id) NOT NULL,
    event_date          DATE NOT NULL,
    source              VARCHAR(20) CHECK (source IN ('open_meteo', 'nasa_power')),
    temp_max_c          FLOAT,
    temp_min_c          FLOAT,
    temp_mean_c         FLOAT,
    precipitation_mm    FLOAT,
    wind_max_ms         FLOAT,
    wind_gust_ms        FLOAT,
    solar_radiation_kwh FLOAT,
    humidity_pct        FLOAT,
    geom                GEOMETRY(Point, 4326),
    created_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE (site_id, event_date, source)
);
```

#### Table 4: `earthquake_events` — USGS Earthquake Data (Point)

```sql
CREATE TABLE earthquake_events (
    id                  SERIAL PRIMARY KEY,
    usgs_id             VARCHAR(50) UNIQUE NOT NULL,
    magnitude           FLOAT NOT NULL,
    mag_type            VARCHAR(10),
    depth_km            FLOAT,
    place_desc          VARCHAR(300),
    event_time          TIMESTAMP NOT NULL,
    significance        INTEGER,
    mmi                 FLOAT,
    alert_level         VARCHAR(10),
    tsunami             BOOLEAN DEFAULT FALSE,
    nearest_site_id     INTEGER REFERENCES heritage_sites(id),
    distance_to_site_km FLOAT,
    geom                GEOMETRY(Point, 4326) NOT NULL,
    created_at          TIMESTAMP DEFAULT NOW()
);
```

#### Table 5: `fire_events` — NASA FIRMS Fire Data (Point)

```sql
CREATE TABLE fire_events (
    id                  SERIAL PRIMARY KEY,
    satellite           VARCHAR(20),
    brightness          FLOAT,
    confidence          INTEGER,
    frp                 FLOAT,
    acq_date            DATE NOT NULL,
    acq_time            TIME,
    day_night           CHAR(1),
    nearest_site_id     INTEGER REFERENCES heritage_sites(id),
    distance_to_site_km FLOAT,
    geom                GEOMETRY(Point, 4326) NOT NULL,
    created_at          TIMESTAMP DEFAULT NOW()
);
```

#### Table 6: `flood_zones` — GFMS Flood Data

```sql
CREATE TABLE flood_zones (
    id                  SERIAL PRIMARY KEY,
    event_date          DATE,
    flood_intensity     FLOAT,
    nearest_site_id     INTEGER REFERENCES heritage_sites(id),
    distance_to_site_km FLOAT,
    geom                GEOMETRY(Point, 4326),
    created_at          TIMESTAMP DEFAULT NOW()
);
```

#### Table 7: `risk_scores` — Computed Risk Scores (Analysis Output)

```sql
CREATE TABLE risk_scores (
    id                      SERIAL PRIMARY KEY,
    site_id                 INTEGER REFERENCES heritage_sites(id) UNIQUE NOT NULL,
    urban_density_score     FLOAT CHECK (urban_density_score BETWEEN 0 AND 1),
    climate_anomaly_score   FLOAT CHECK (climate_anomaly_score BETWEEN 0 AND 1),
    seismic_risk_score      FLOAT CHECK (seismic_risk_score BETWEEN 0 AND 1),
    fire_risk_score         FLOAT CHECK (fire_risk_score BETWEEN 0 AND 1),
    flood_risk_score        FLOAT CHECK (flood_risk_score BETWEEN 0 AND 1),
    coastal_risk_score      FLOAT CHECK (coastal_risk_score BETWEEN 0 AND 1),
    composite_risk_score    FLOAT CHECK (composite_risk_score BETWEEN 0 AND 1),
    isolation_forest_score  FLOAT,
    is_anomaly              BOOLEAN DEFAULT FALSE,
    risk_level              VARCHAR(20) CHECK (risk_level IN ('critical', 'high', 'medium', 'low')),
    calculated_at           TIMESTAMP DEFAULT NOW()
);
```

### 3.3 Spatial Indices (`sql/03_create_indices.sql`)

```sql
-- GIST spatial indices
CREATE INDEX idx_heritage_sites_geom       ON heritage_sites       USING GIST (geom);
CREATE INDEX idx_urban_features_geom       ON urban_features       USING GIST (geom);
CREATE INDEX idx_climate_events_geom       ON climate_events       USING GIST (geom);
CREATE INDEX idx_earthquake_events_geom    ON earthquake_events    USING GIST (geom);
CREATE INDEX idx_fire_events_geom          ON fire_events          USING GIST (geom);
CREATE INDEX idx_flood_zones_geom          ON flood_zones          USING GIST (geom);

-- B-Tree indices for frequent lookups
CREATE INDEX idx_climate_events_site_date  ON climate_events       (site_id, event_date);
CREATE INDEX idx_earthquake_site           ON earthquake_events    (nearest_site_id);
CREATE INDEX idx_fire_site                 ON fire_events          (nearest_site_id);
CREATE INDEX idx_flood_site                ON flood_zones          (nearest_site_id);
CREATE INDEX idx_urban_site                ON urban_features       (nearest_site_id);
CREATE INDEX idx_risk_scores_site          ON risk_scores          (site_id);
CREATE INDEX idx_risk_scores_level         ON risk_scores          (risk_level);
CREATE INDEX idx_risk_scores_anomaly       ON risk_scores          (is_anomaly) WHERE is_anomaly = TRUE;
```

---

## 4. ETL Pipeline — Data Fetching Modules

### 4.1 UNESCO Data Fetcher (`src/etl/fetch_unesco.py`)

- **Source**: `https://whc.unesco.org/en/list/xml/` (XML — stable) + JSON endpoint as fallback
- **Processing**: XML parse → filter `region == "Europe and North America"` → further filter by European ISO codes (`TR`, `IT`, `ES`, `FR`, `DE`, `GR`, `GB`, `PT`, `PL`, `CZ`, `HR`, `AT`, `CH`, `BE`, `NL`, `SE`, `NO`, `DK`, `FI`, `RO`, `BG`, `HU`, `SK`, `SI`, `RS`, `BA`, `ME`, `MK`, `AL`, `CY`, `MT`, `IS`, `IE`, `LU`, `LT`, `LV`, `EE`, `MD`, `UA`, `BY`, `GE`, `AM`, `AZ`, etc.)
- **Geometry**: `lat`/`lon` → Shapely `Point(lon, lat)` → GeoDataFrame (CRS: EPSG:4326)
- **Output**: UPSERT into `heritage_sites` table (conflict on `whc_id`)
- **Expected count**: ~500 sites

```python
# Pseudo-code
import requests
import xml.etree.ElementTree as ET
import geopandas as gpd
from shapely.geometry import Point

def fetch_unesco_sites(europe_only=True):
    response = requests.get("https://whc.unesco.org/en/list/xml/")
    root = ET.fromstring(response.content)
    
    sites = []
    for row in root.findall(".//row"):
        site = {
            "whc_id": int(row.find("id_number").text),
            "name": row.find("site").text,
            "category": row.find("category").text,
            "latitude": float(row.find("latitude").text),
            "longitude": float(row.find("longitude").text),
            "country": row.find("states").text,
            "iso_code": row.find("iso_code").text,
            "region": row.find("region").text,
            "in_danger": bool(int(row.find("danger").text)),
            "date_inscribed": int(row.find("date_inscribed").text),
            "area_hectares": float(row.find("area_hectares").text or 0),
        }
        if europe_only and site["iso_code"] not in EUROPE_ISO_CODES:
            continue
        site["geometry"] = Point(site["longitude"], site["latitude"])
        sites.append(site)
    
    gdf = gpd.GeoDataFrame(sites, crs="EPSG:4326")
    return gdf
```

### 4.2 OSM Urban Features Fetcher (`src/etl/fetch_osm.py`)

- **Method**: Per-site extraction — `ox.features_from_point((lat, lon), tags=tags, dist=5000)` (5 km radius)
- **Tags**: `{"building": True, "landuse": ["residential", "commercial", "industrial", "construction", "retail"]}`
- **Rate limiting**: `time.sleep(5)` between sites → ~500 sites × 5s ≈ ~42 min
- **Overpass config**: `ox.settings.timeout = 300`
- **CRS**: Fetched in EPSG:4326, reprojected to EPSG:3035 for distance calculations
- **Output**: Feature count, total area (m²), density per site → `urban_features` table

```python
import osmnx as ox
import geopandas as gpd
import time

def fetch_osm_for_site(lat, lon, site_id, buffer_m=5000):
    tags = {
        "building": True,
        "landuse": ["residential", "commercial", "industrial",
                     "construction", "retail"],
    }
    ox.settings.timeout = 300
    
    try:
        gdf = ox.features_from_point((lat, lon), tags=tags, dist=buffer_m)
        gdf["nearest_site_id"] = site_id
        
        # Reproject for area calculation
        gdf_proj = gdf.to_crs(epsg=3035)
        gdf["area_m2"] = gdf_proj.geometry.area
        
        return gdf
    except Exception as e:
        print(f"OSM fetch failed for site {site_id}: {e}")
        return gpd.GeoDataFrame()

def fetch_all_osm(sites_gdf):
    all_features = []
    for _, site in sites_gdf.iterrows():
        gdf = fetch_osm_for_site(site.latitude, site.longitude, site.whc_id)
        all_features.append(gdf)
        time.sleep(5)  # Respect Overpass rate limits
    return gpd.GeoDataFrame(pd.concat(all_features, ignore_index=True))
```

### 4.3 Climate Data Fetcher (`src/etl/fetch_climate.py`)

**Open-Meteo (primary)**:
```python
import requests
import pandas as pd

def fetch_open_meteo(lat, lon, start_date="2020-01-01", end_date="2025-12-31"):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join([
            "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
            "precipitation_sum", "windspeed_10m_max", "windgusts_10m_max",
        ]),
        "timezone": "UTC",
    }
    resp = requests.get(url, params=params)
    data = resp.json()["daily"]
    
    df = pd.DataFrame({
        "event_date": pd.to_datetime(data["time"]),
        "temp_max_c": data["temperature_2m_max"],
        "temp_min_c": data["temperature_2m_min"],
        "temp_mean_c": data["temperature_2m_mean"],
        "precipitation_mm": data["precipitation_sum"],
        "wind_max_ms": data["windspeed_10m_max"],
        "wind_gust_ms": data["windgusts_10m_max"],
        "source": "open_meteo",
    })
    return df
```

**NASA POWER (supplementary)**:
```python
def fetch_nasa_power(lat, lon, start="20200101", end="20251231"):
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M,PRECTOTCORR,WS10M,ALLSKY_SFC_SW_DWN",
        "community": "RE",
        "longitude": lon,
        "latitude": lat,
        "start": start,
        "end": end,
        "format": "JSON",
    }
    resp = requests.get(url, params=params)
    data = resp.json()["properties"]["parameter"]
    
    dates = list(data["T2M"].keys())
    df = pd.DataFrame({
        "event_date": pd.to_datetime(dates, format="%Y%m%d"),
        "temp_mean_c": list(data["T2M"].values()),
        "precipitation_mm": list(data["PRECTOTCORR"].values()),
        "wind_max_ms": list(data["WS10M"].values()),
        "solar_radiation_kwh": list(data["ALLSKY_SFC_SW_DWN"].values()),
        "source": "nasa_power",
    })
    return df
```

### 4.4 USGS Earthquake Fetcher (`src/etl/fetch_earthquake.py`)

```python
import requests
import geopandas as gpd
from shapely.geometry import Point

def fetch_earthquakes_europe(start="2015-01-01", end="2025-12-31", min_mag=3.0):
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        "format": "geojson",
        "starttime": start,
        "endtime": end,
        "minlatitude": 34,
        "maxlatitude": 72,
        "minlongitude": -25,
        "maxlongitude": 45,
        "minmagnitude": min_mag,
        "orderby": "time",
    }
    resp = requests.get(url, params=params)
    features = resp.json()["features"]
    
    records = []
    for f in features:
        p = f["properties"]
        c = f["geometry"]["coordinates"]
        records.append({
            "usgs_id": f["id"],
            "magnitude": p["mag"],
            "mag_type": p.get("magType"),
            "depth_km": c[2],
            "place_desc": p.get("place"),
            "event_time": pd.Timestamp(p["time"], unit="ms"),
            "significance": p.get("sig"),
            "mmi": p.get("mmi"),
            "alert_level": p.get("alert"),
            "tsunami": bool(p.get("tsunami", 0)),
            "geometry": Point(c[0], c[1]),
        })
    
    return gpd.GeoDataFrame(records, crs="EPSG:4326")
```

### 4.5 NASA FIRMS Fire Fetcher (`src/etl/fetch_fire.py`)

```python
import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import os

def fetch_firms_fire(days=10, source="VIIRS_SNPP_NRT"):
    api_key = os.getenv("FIRMS_API_KEY")
    # Europe bounding box: W=-25, S=34, E=45, N=72
    area = "-25,34,45,72"
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/{source}/{area}/{days}"
    
    df = pd.read_csv(url)
    
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.longitude, df.latitude),
        crs="EPSG:4326",
    )
    gdf["acq_date"] = pd.to_datetime(gdf["acq_date"])
    return gdf
```

### 4.6 GFMS Flood Fetcher (`src/etl/fetch_flood.py`)

```python
import rasterio
import numpy as np

def sample_flood_at_sites(geotiff_path, sites_gdf):
    """Sample GFMS flood intensity raster at each heritage site coordinate."""
    with rasterio.open(geotiff_path) as src:
        for idx, site in sites_gdf.iterrows():
            lon, lat = site.geometry.x, site.geometry.y
            row, col = src.index(lon, lat)
            value = src.read(1)[row, col]
            sites_gdf.loc[idx, "flood_intensity"] = float(value) if value != src.nodata else 0.0
    return sites_gdf
```

### 4.7 OpenTopography Elevation Fetcher (`src/etl/fetch_elevation.py`)

```python
import requests
import rasterio
from io import BytesIO
import os

def fetch_elevation(lat, lon, buffer_deg=0.01):
    api_key = os.getenv("OPENTOPO_API_KEY")
    url = "https://portal.opentopography.org/API/globaldem"
    params = {
        "demtype": "COP30",
        "south": lat - buffer_deg,
        "north": lat + buffer_deg,
        "west": lon - buffer_deg,
        "east": lon + buffer_deg,
        "outputFormat": "GTiff",
        "API_Key": api_key,
    }
    resp = requests.get(url, params=params)
    
    with rasterio.open(BytesIO(resp.content)) as src:
        row, col = src.index(lon, lat)
        elevation = src.read(1)[row, col]
    
    return float(elevation)
```

---

## 5. CRS Transformation & Spatial Join

### `src/etl/spatial_join.py`

### 5.1 CRS Strategy

| CRS | EPSG | Purpose |
|---|---|---|
| **WGS84** | 4326 | Storage, data exchange, API communication |
| **ETRS89 / LAEA Europe** | 3035 | Distance/area calculations (metric, accurate for Europe) |
| **Web Mercator** | 3857 | ⚠️ NOT used — area distortion at high latitudes |

**Rule**: All data stored in EPSG:4326. Project to EPSG:3035 only for metric computations. Transform back to 4326 for storage.

### 5.2 Buffer Zone Creation

```python
import geopandas as gpd

def create_buffers(sites_gdf, distances_m=[5000, 10000, 25000, 50000]):
    """Create concentric buffers around each heritage site."""
    # Project to EPSG:3035 for metric buffer
    sites_proj = sites_gdf.to_crs(epsg=3035)
    
    buffers = {}
    for dist in distances_m:
        buffer_gdf = sites_proj.copy()
        buffer_gdf["geometry"] = sites_proj.buffer(dist)
        buffer_gdf["buffer_m"] = dist
        # Transform back to 4326 for storage
        buffers[dist] = buffer_gdf.to_crs(epsg=4326)
    
    return buffers
```

### 5.3 Spatial Join Operations

```python
def join_urban_to_sites(urban_gdf, sites_gdf, buffer_m=5000):
    """Spatial join: which urban features fall within site buffer zones."""
    # Project both to EPSG:3035
    urban_proj = urban_gdf.to_crs(epsg=3035)
    sites_proj = sites_gdf.to_crs(epsg=3035)
    
    # Create buffer zones
    sites_buffer = sites_proj.copy()
    sites_buffer["geometry"] = sites_proj.buffer(buffer_m)
    
    # Spatial join
    joined = gpd.sjoin(urban_proj, sites_buffer, how="inner", predicate="within")
    
    # Calculate distance from each feature to its nearest site
    joined["distance_to_site_m"] = joined.geometry.centroid.distance(
        sites_proj.loc[joined.index_right].geometry.values
    )
    
    return joined.to_crs(epsg=4326)

def join_hazards_to_sites(hazard_gdf, sites_gdf, max_distance_m=100000):
    """Nearest-site spatial join for point hazards (earthquakes, fires)."""
    hazard_proj = hazard_gdf.to_crs(epsg=3035)
    sites_proj = sites_gdf.to_crs(epsg=3035)
    
    joined = gpd.sjoin_nearest(
        hazard_proj, sites_proj,
        how="left",
        max_distance=max_distance_m,
        distance_col="distance_to_site_m"
    )
    
    joined["distance_to_site_km"] = joined["distance_to_site_m"] / 1000
    return joined.to_crs(epsg=4326)
```

---

## 6. Analytical Layer — Multi-Variate Risk Model

### 6.1 Proximity Risk Score Algorithm (`src/analysis/risk_scoring.py`)

Six sub-scores computed per heritage site:

| Sub-Score | Input Data | Computation |
|---|---|---|
| **Urban Density** | OSM building/landuse | Building count + total footprint area (m²) within 5 km buffer. Kernel Density Estimation (KDE) normalized to [0,1] |
| **Climate Anomaly** | Open-Meteo + NASA POWER | 5-year daily data → Z-score: `(value - μ) / σ`. Count extreme event days: T_max > μ+2σ OR precip > μ+3σ. Score = extreme_days / total_days |
| **Seismic Risk** | USGS Earthquakes | Earthquakes within 50 km: `Σ (10^(1.5 * mag) / distance²)` — Gutenberg-Richter energy, inverse-square distance decay |
| **Fire Risk** | NASA FIRMS | Fire detections within 25 km: `Σ (frp × confidence / distance)` — FRP-weighted, inverse distance |
| **Flood Risk** | GFMS | GFMS raster pixel value + historical flood event frequency |
| **Coastal Risk** | OpenTopography DEM | `max(0, 1 - (elevation / 10))` if distance to coast < 50 km, else 0 |

**Normalization**: All sub-scores normalized to [0, 1] via Min-Max scaling across all sites.

**Composite Risk Score** — weighted average:

$$R_{composite} = w_1 \cdot S_{urban} + w_2 \cdot S_{climate} + w_3 \cdot S_{seismic} + w_4 \cdot S_{fire} + w_5 \cdot S_{flood} + w_6 \cdot S_{coastal}$$

**Default weights**: $w_1=0.25, w_2=0.20, w_3=0.20, w_4=0.15, w_5=0.10, w_6=0.10$

```python
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

DEFAULT_WEIGHTS = {
    "urban_density": 0.25,
    "climate_anomaly": 0.20,
    "seismic_risk": 0.20,
    "fire_risk": 0.15,
    "flood_risk": 0.10,
    "coastal_risk": 0.10,
}

def compute_urban_density_score(sites_gdf, urban_gdf):
    """Compute urban density score per site from OSM data."""
    scores = []
    for _, site in sites_gdf.iterrows():
        nearby = urban_gdf[urban_gdf["nearest_site_id"] == site["whc_id"]]
        building_count = len(nearby[nearby["feature_type"] == "building"])
        total_area = nearby["area_m2"].sum()
        scores.append(building_count * total_area)
    return np.array(scores)

def compute_climate_anomaly_score(climate_df, site_ids):
    """Z-score based extreme event detection."""
    scores = []
    for site_id in site_ids:
        site_data = climate_df[climate_df["site_id"] == site_id]
        if site_data.empty:
            scores.append(0)
            continue
        
        temp_max = site_data["temp_max_c"]
        precip = site_data["precipitation_mm"]
        
        # Z-scores
        temp_z = (temp_max - temp_max.mean()) / temp_max.std()
        precip_z = (precip - precip.mean()) / precip.std()
        
        # Extreme event days
        extreme_days = ((temp_z > 2) | (precip_z > 3)).sum()
        total_days = len(site_data)
        
        scores.append(extreme_days / total_days if total_days > 0 else 0)
    return np.array(scores)

def compute_seismic_risk_score(sites_gdf, earthquakes_gdf):
    """Gutenberg-Richter energy with inverse-square distance decay."""
    scores = []
    sites_proj = sites_gdf.to_crs(epsg=3035)
    eq_proj = earthquakes_gdf.to_crs(epsg=3035)
    
    for _, site in sites_proj.iterrows():
        distances = eq_proj.geometry.distance(site.geometry)
        within_50km = eq_proj[distances <= 50000].copy()
        within_50km["dist"] = distances[distances <= 50000]
        
        if within_50km.empty:
            scores.append(0)
            continue
        
        energy = 10 ** (1.5 * within_50km["magnitude"])
        risk = (energy / (within_50km["dist"] ** 2 + 1)).sum()
        scores.append(risk)
    
    return np.array(scores)

def compute_composite_score(risk_df, weights=DEFAULT_WEIGHTS):
    """Weighted composite risk score."""
    scaler = MinMaxScaler()
    score_cols = list(weights.keys())
    
    # Min-Max normalize each sub-score
    risk_df[score_cols] = scaler.fit_transform(risk_df[score_cols])
    
    # Weighted average
    risk_df["composite_risk_score"] = sum(
        risk_df[col] * w for col, w in weights.items()
    )
    
    # Risk level classification
    risk_df["risk_level"] = pd.cut(
        risk_df["composite_risk_score"],
        bins=[0, 0.4, 0.6, 0.8, 1.0],
        labels=["low", "medium", "high", "critical"],
    )
    
    return risk_df
```

### 6.2 Isolation Forest Anomaly Detection (`src/analysis/anomaly_detection.py`)

After sub-scores are computed, `sklearn.ensemble.IsolationForest` identifies sites that are statistical outliers in multi-dimensional risk space.

```python
from sklearn.ensemble import IsolationForest
import numpy as np

def detect_risk_anomalies(risk_df, contamination=0.1, n_estimators=200):
    """
    Detect heritage sites that are statistical outliers in risk exposure.
    
    Sites flagged as anomalies are simultaneously exposed to multiple 
    risk factors at unusually high levels — they are 'risk hotspots'.
    """
    feature_cols = [
        "urban_density_score", "climate_anomaly_score",
        "seismic_risk_score", "fire_risk_score",
        "flood_risk_score", "coastal_risk_score",
    ]
    
    X = risk_df[feature_cols].fillna(0).values
    
    iso_forest = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    
    # Fit and predict
    risk_df["isolation_forest_score"] = iso_forest.decision_function(X)
    risk_df["is_anomaly"] = iso_forest.fit_predict(X) == -1
    
    # Override risk_level for anomalies
    risk_df.loc[risk_df["is_anomaly"], "risk_level"] = "critical"
    
    anomaly_count = risk_df["is_anomaly"].sum()
    print(f"Detected {anomaly_count} anomalous sites "
          f"({anomaly_count/len(risk_df)*100:.1f}%)")
    
    return risk_df
```

**Interpretation**: Anomaly sites are those simultaneously exposed to multiple risk factors at statistically extreme levels — not just high in one dimension, but multi-dimensionally unusual.

### 6.3 Spatial Density Analysis (`src/analysis/density_analysis.py`)

```python
from sklearn.neighbors import KernelDensity
import numpy as np

def compute_urban_kde(urban_gdf, bandwidth=1000):
    """
    Kernel Density Estimation for urban feature spatial density.
    Returns density surface values at each feature location.
    """
    urban_proj = urban_gdf.to_crs(epsg=3035)
    coords = np.column_stack([
        urban_proj.geometry.centroid.x,
        urban_proj.geometry.centroid.y,
    ])
    
    kde = KernelDensity(bandwidth=bandwidth, kernel="gaussian")
    kde.fit(coords)
    
    log_density = kde.score_samples(coords)
    urban_gdf["density_score"] = np.exp(log_density)
    
    return urban_gdf
```

---

## 7. Airflow DAG Design

### DAG Architecture

```
                        ┌─────────────────────┐
                        │  fetch_unesco_sites  │
                        └─────────┬───────────┘
                                  │
          ┌───────────┬───────────┼───────────┬───────────┐
          │           │           │           │           │
   ┌──────▼──────┐ ┌──▼───────┐ ┌▼─────────┐ ┌▼────────┐ ┌▼──────────┐
   │ fetch_osm   │ │ fetch_   │ │ fetch_   │ │ fetch_  │ │ fetch_    │
   │ _data       │ │ climate  │ │ earthquake│ │ fire   │ │ flood +   │
   │ (per-site   │ │ (OM+NP)  │ │ (USGS)   │ │ (FIRMS)│ │ elevation │
   │  loop)      │ │          │ │          │ │        │ │           │
   └──────┬──────┘ └──┬───────┘ └┬─────────┘ └┬────────┘ └┬──────────┘
          │           │          │            │           │
          └───────────┴──────────┼────────────┴───────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     spatial_join        │
                    │  (CRS transform +      │
                    │   nearest site match)   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  calculate_risk_scores  │
                    │  (6 sub-scores + comp.) │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  anomaly_detection      │
                    │  (Isolation Forest)     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  generate_folium_map    │
                    │  (Interactive map)      │
                    └─────────────────────────┘
```

### DAG Definition (`dags/unesco_risk_dag.py`)

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from datetime import datetime, timedelta

default_args = {
    "owner": "unesco_risk",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="unesco_risk_pipeline",
    default_args=default_args,
    description="UNESCO Heritage Site Risk Modeling Pipeline",
    schedule_interval="@weekly",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["unesco", "risk", "geospatial"],
) as dag:

    fetch_sites = PythonOperator(
        task_id="fetch_unesco_sites",
        python_callable=fetch_unesco_callable,
    )

    with TaskGroup("data_ingestion") as ingestion_group:
        fetch_osm = PythonOperator(
            task_id="fetch_osm_data",
            python_callable=fetch_osm_callable,
            execution_timeout=timedelta(hours=2),
        )
        fetch_climate = PythonOperator(
            task_id="fetch_climate_data",
            python_callable=fetch_climate_callable,
        )
        fetch_eq = PythonOperator(
            task_id="fetch_earthquake_data",
            python_callable=fetch_earthquake_callable,
        )
        fetch_fire = PythonOperator(
            task_id="fetch_fire_data",
            python_callable=fetch_fire_callable,
        )
        fetch_flood_elev = PythonOperator(
            task_id="fetch_flood_elevation",
            python_callable=fetch_flood_elevation_callable,
        )

    spatial = PythonOperator(
        task_id="spatial_join",
        python_callable=spatial_join_callable,
    )

    risk = PythonOperator(
        task_id="calculate_risk_scores",
        python_callable=risk_scoring_callable,
    )

    anomaly = PythonOperator(
        task_id="anomaly_detection",
        python_callable=anomaly_detection_callable,
    )

    viz = PythonOperator(
        task_id="generate_folium_map",
        python_callable=folium_map_callable,
    )

    fetch_sites >> ingestion_group >> spatial >> risk >> anomaly >> viz
```

**DAG Configuration**:
| Setting | Value | Rationale |
|---|---|---|
| `schedule_interval` | `@weekly` | Weekly risk updates |
| `catchup` | `False` | No backfill |
| `max_active_runs` | `1` | Prevent concurrent pipeline runs |
| `execution_timeout` (OSM) | 2 hours | OSM fetching is slow (~42 min) |
| `retries` | 2 | Handle transient API failures |

---

## 8. Visualization Layer

### Modern Interactive Dashboard (PRIMARY)

**File**: `src/visualization/dash_app.py`

A cutting-edge, professional web application built with **Plotly Dash** and **Mapbox GL** for stunning, interactive risk visualization.

**Key Features**:
- 🗺️ **GPU-accelerated Mapbox GL rendering** for smooth 60fps performance
- 🌍 **3D Globe view** with orthographic projection
- 🎨 **4 map styles**: Dark, Satellite, Light, Outdoors
- 🔍 **Real-time filtering** by risk level, country, category, danger status, anomalies
- 📊 **Live analytics**: Statistics panel, risk distribution chart, risk factors radar
- ⚡ **Responsive Bootstrap UI** with dark theme
- 🎯 **Interactive tooltips** with comprehensive site information

**Technologies**:
- **Dash 4.0**: Python web framework
- **Plotly 6.0**: Interactive charts and graphs
- **Mapbox GL**: GPU-accelerated mapping
- **Bootstrap 5**: Professional UI components
- **Dash Bootstrap Components**: Pre-built components

**Architecture**:
```python
# Main components
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])

# Sidebar with filters and controls
def create_sidebar():
    return html.Div([
        # Statistics panel
        dbc.Card([...]),
        
        # Filters
        dcc.Checklist(id="risk-level-filter"),
        dcc.Dropdown(id="country-filter"),
        dcc.Dropdown(id="category-filter"),
        dbc.Checklist(id="danger-filter"),
        dbc.Checklist(id="anomaly-filter"),
        
        # Map controls
        dcc.RadioItems(id="map-style"),
        dbc.Checklist(id="3d-view"),
    ])

# Main content area
def create_main_content():
    return html.Div([
        dcc.Graph(id="main-map"),
        dbc.Row([
            dbc.Col(dcc.Graph(id="risk-distribution-chart")),
            dbc.Col(dcc.Graph(id="risk-factors-chart")),
        ])
    ])

# Real-time callbacks
@callback(
    [Output("main-map", "figure"),
     Output("risk-distribution-chart", "figure"),
     Output("risk-factors-chart", "figure")],
    [Input("risk-level-filter", "value"),
     Input("country-filter", "value"),
     # ... other filters
    ]
)
def update_visualizations(...):
    # Filter data based on user selections
    filtered_df = apply_filters(df_sites, ...)
    
    # Generate updated visualizations
    map_fig = create_map_figure(filtered_df, ...)
    dist_fig = create_risk_distribution_chart(filtered_df)
    factors_fig = create_risk_factor_chart(filtered_df)
    
    return map_fig, dist_fig, factors_fig
```

**Usage**:
```bash
# Launch the interactive dashboard
python run_dashboard.py

# With custom settings
python run_dashboard.py --host 0.0.0.0 --port 8080 --debug
```

**Demo Mode**:
- Automatically generates synthetic demo data if database is unavailable
- Allows testing and showcasing without live database connection

**Documentation**:
- [docs/DASHBOARD_GUIDE.md](../docs/DASHBOARD_GUIDE.md) - Complete usage guide
- [docs/DASHBOARD_SHOWCASE.md](../docs/DASHBOARD_SHOWCASE.md) - Visual showcase
- [docs/LEGACY_VS_MODERN.md](../docs/LEGACY_VS_MODERN.md) - Comparison guide

---

### Legacy Folium Map (PRESERVED)

**File**: `src/visualization/folium_map_legacy.py`

The original static HTML map generator, preserved for compatibility and simple use cases.

```python
import folium
from folium.plugins import HeatMap, MarkerCluster

def generate_risk_map(sites_gdf, risk_df, output_path="output/maps/europe_risk_map.html"):
    # Base map centered on Europe
    m = folium.Map(location=[50, 10], zoom_start=4, tiles="CartoDB positron")
    
    # Color mapping by risk level
    RISK_COLORS = {
        "critical": "#d32f2f",  # Red
        "high": "#f57c00",      # Orange
        "medium": "#fbc02d",    # Yellow
        "low": "#388e3c",       # Green
    }
    
    # Heritage Sites layer with risk-colored markers
    site_group = folium.FeatureGroup(name="UNESCO Heritage Sites")
    for _, row in sites_gdf.merge(risk_df, left_on="whc_id", right_on="site_id").iterrows():
        color = RISK_COLORS.get(row["risk_level"], "#757575")
        popup_html = f"""
        <b>{row['name']}</b><br>
        Country: {row['country']}<br>
        Category: {row['category']}<br>
        <hr>
        Urban: {row['urban_density_score']:.2f}<br>
        Climate: {row['climate_anomaly_score']:.2f}<br>
        Seismic: {row['seismic_risk_score']:.2f}<br>
        Fire: {row['fire_risk_score']:.2f}<br>
        Flood: {row['flood_risk_score']:.2f}<br>
        Coastal: {row['coastal_risk_score']:.2f}<br>
        <hr>
        <b>Composite: {row['composite_risk_score']:.2f}</b><br>
        Anomaly: {'⚠️ YES' if row['is_anomaly'] else 'No'}
        """
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=8 if row["is_anomaly"] else 5,
            color=color, fill=True, fill_opacity=0.8,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=row["name"],
        ).add_to(site_group)
    site_group.add_to(m)
    
    # Risk HeatMap layer
    heat_data = [
        [row.geometry.y, row.geometry.x, row["composite_risk_score"]]
        for _, row in sites_gdf.merge(risk_df, left_on="whc_id", right_on="site_id").iterrows()
    ]
    HeatMap(heat_data, name="Risk Heatmap", radius=25, blur=15).add_to(m)
    
    # Layer control
    folium.LayerControl().add_to(m)
    
    # Save
    m.save(output_path)
    return output_path
```

**Map Features**:
- **Base Map**: CartoDB positron (clean, label-friendly)
- **Site Markers**: `CircleMarker` color-coded by risk level (red/orange/yellow/green), anomalies get larger radius
- **Popup**: Site details + all 6 sub-scores + composite score + anomaly flag
- **HeatMap Layer**: Composite risk intensity visualization
- **Layer Control**: Toggle individual layers on/off
- **Output**: Self-contained HTML file

**When to Use**:
- Need a static HTML file for offline viewing
- Simple embedding in websites
- Quick map generation without server
- Basic interactivity is sufficient

---

## 9. Configuration & Environment Variables

### `config/settings.py`

```python
# CRS Constants
SRC_CRS = 4326          # WGS84 — storage & API communication
PROJ_CRS = 3035         # ETRS89/LAEA Europe — metric computations

# Europe Bounding Box
EUROPE_BBOX = {
    "min_lat": 34, "max_lat": 72,
    "min_lon": -25, "max_lon": 45,
}

# Buffer distances (meters)
BUFFER_DISTANCES = [5000, 10000, 25000, 50000]
OSM_BUFFER_M = 5000     # Default OSM extraction radius

# Risk weights
RISK_WEIGHTS = {
    "urban_density": 0.25,
    "climate_anomaly": 0.20,
    "seismic_risk": 0.20,
    "fire_risk": 0.15,
    "flood_risk": 0.10,
    "coastal_risk": 0.10,
}

# Isolation Forest parameters
IF_CONTAMINATION = 0.10
IF_N_ESTIMATORS = 200
IF_RANDOM_STATE = 42

# API URLs
UNESCO_XML_URL = "https://whc.unesco.org/en/list/xml/"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
USGS_EARTHQUAKE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
FIRMS_API_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
OPENTOPO_API_URL = "https://portal.opentopography.org/API/globaldem"
GFMS_URL = "https://flood.umd.edu/"

# Climate data range
CLIMATE_START_DATE = "2020-01-01"
CLIMATE_END_DATE = "2025-12-31"

# European ISO country codes
EUROPE_ISO_CODES = {
    "TR", "IT", "ES", "FR", "DE", "GR", "GB", "PT", "PL", "CZ",
    "HR", "AT", "CH", "BE", "NL", "SE", "NO", "DK", "FI", "RO",
    "BG", "HU", "SK", "SI", "RS", "BA", "ME", "MK", "AL", "CY",
    "MT", "IS", "IE", "LU", "LT", "LV", "EE", "MD", "UA", "BY",
    "GE", "AM", "AZ", "RU", "AD", "MC", "SM", "VA", "LI", "XK",
}
```

### `.env.example`

```env
# PostgreSQL / PostGIS
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=unesco_risk
POSTGRES_USER=postgres
POSTGRES_PASSWORD=changeme

# NASA FIRMS (register at https://firms.modaps.eosdis.nasa.gov/api/area/)
FIRMS_API_KEY=your_firms_api_key_here

# OpenTopography (register at https://portal.opentopography.org/)
OPENTOPO_API_KEY=your_opentopo_api_key_here

# Airflow
AIRFLOW_HOME=/path/to/airflow
```

---

## 10. Verification & Testing

### Database Verification

```sql
-- Site count
SELECT count(*) FROM heritage_sites WHERE region LIKE '%Europe%';
-- Expected: ~500

-- Top urban exposure
SELECT h.name, COUNT(u.id) as urban_count, SUM(u.distance_to_site_m) as total_dist
FROM heritage_sites h
LEFT JOIN urban_features u ON u.nearest_site_id = h.id
GROUP BY h.name ORDER BY urban_count DESC LIMIT 10;

-- Risk anomalies
SELECT hs.name, hs.country, rs.composite_risk_score, rs.risk_level, rs.is_anomaly
FROM risk_scores rs
JOIN heritage_sites hs ON rs.site_id = hs.id
WHERE rs.is_anomaly = TRUE
ORDER BY rs.composite_risk_score DESC;
```

### ETL Module Testing

```bash
# Dry-run individual modules
python -m src.etl.fetch_unesco --dry-run
python -m src.etl.fetch_earthquake --dry-run
python -m src.etl.fetch_climate --site-id 1 --dry-run
```

### Unit Tests

```bash
pytest tests/ -v
```

Test targets:
- `test_etl.py`: CRS transformation correctness, API response parsing, data validation
- `test_analysis.py`: Score normalization, IF model convergence, composite weight sum = 1.0
- `test_db.py`: PostGIS connection, spatial query correctness, UPSERT idempotency

### Airflow Pipeline Test

```bash
airflow dags test unesco_risk_pipeline 2025-01-01
```

### Visual Verification

Open `output/maps/europe_risk_map.html` in browser for visual inspection.

---

## 11. Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **CRS for projections** | EPSG:3035 (ETRS89/LAEA Europe) | Metric area/distance accuracy for Europe; EPSG:3857 has high-latitude distortion |
| **Climate source** | Open-Meteo (primary) + NASA POWER (supplementary) | Both free, no API key; complementary variables (solar radiation from NASA) |
| **OSM buffer radius** | 5 km | Captures urban sprawl while keeping Overpass API load manageable |
| **Anomaly contamination** | IF `contamination=0.1` | ~10% of sites expected to be critical; tunable after exploratory analysis |
| **Europe bounding box** | lat [34°, 72°], lon [-25°, 45°] | Includes Turkey, Iceland; wide coverage |
| **Infrastructure** | Local PostgreSQL/PostGIS + Airflow (no Docker) | Direct installation per user preference |
| **DEM source** | Copernicus 30m DEM via OpenTopography | More current than SRTM; free API access |
| **Risk weights** | Urban 0.25, Climate 0.20, Seismic 0.20, Fire 0.15, Flood 0.10, Coastal 0.10 | Urbanization as primary threat; seismic/climate as secondary; flood/coastal as tertiary |
| **Hazard data sources** | USGS + FIRMS + GFMS + OpenTopography | All free/free-key; comprehensive multi-hazard coverage |
| **UNESCO stable endpoint** | XML (`/en/list/xml/`) | Documented and stable; JSON/GeoJSON endpoints undocumented |

---

## 12. Development Roadmap — Step-by-Step Implementation Guide

> **Estimated Total Duration**: ~6–8 weeks (solo developer)  
> **Approach**: Incremental — each phase produces a testable, working increment  
> **Dependency Flow**: Phase 0 → 1 → 2 → 3 → 4 (parallel tracks) → 5 → 6 → 7 → 8 → 9 → 10

---

### ✅ Phase 0 — Environment Setup & Prerequisites _(Days 1–2)_

> **Goal**: Working development environment with all system dependencies installed.

| Step | Task | Details | Deliverable | Verify |
|------|------|---------|-------------|--------|
| 0.1 | **Install Python 3.11+** | `sudo apt install python3.11 python3.11-venv python3.11-dev` | Python binary | `python3 --version` |
| 0.2 | **Create virtual environment** | `python3 -m venv .venv && source .venv/bin/activate` | `.venv/` directory | `which python` points to `.venv` |
| 0.3 | **Install PostgreSQL 16 + PostGIS** | `sudo apt install postgresql-16 postgresql-16-postgis-3` | Running PostgreSQL service | `sudo systemctl status postgresql` |
| 0.4 | **Configure PostgreSQL** | Create user, database, enable PostGIS extension | `unesco_risk` database with PostGIS | `psql -d unesco_risk -c "SELECT PostGIS_Version();"` |
| 0.5 | **Install system libraries** | `sudo apt install libgdal-dev libproj-dev libgeos-dev` (required by rasterio, geopandas) | GDAL/GEOS/PROJ libs | `gdal-config --version` |
| 0.6 | **Install Python dependencies** | `pip install -r requirements.txt` | All packages installed | `python -c "import geopandas, osmnx, folium, sqlalchemy"` |
| 0.7 | **Register for API keys** | Register at NASA FIRMS + OpenTopography portals | `FIRMS_API_KEY`, `OPENTOPO_API_KEY` | Keys saved in `.env` |
| 0.8 | **Install Apache Airflow** | `pip install apache-airflow` + initialize database (`airflow db init`) | Airflow webserver accessible | `airflow version` |

**Blockers to resolve before proceeding**:
- PostgreSQL must be running and accepting connections
- PostGIS extension must be enabled
- API keys must be obtained (FIRMS + OpenTopography)

---

### ✅ Phase 1 — Project Scaffolding & Configuration _(Days 2–3)_

> **Goal**: Complete project directory structure, configuration files, and environment variables ready.

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 1.1 | **Create directory tree** | Create all directories: `src/etl/`, `src/analysis/`, `src/db/`, `src/visualization/`, `config/`, `sql/`, `dags/`, `tests/`, `notebooks/`, `output/maps/` | All directories exist |
| 1.2 | **Create `__init__.py` files** | Empty `__init__.py` in `src/`, `src/etl/`, `src/analysis/`, `src/db/`, `src/visualization/` | Python packages importable |
| 1.3 | **Create `requirements.txt`** | All 17 dependencies with minimum versions as specified in Section 1 | File exists |
| 1.4 | **Create `setup.py`** | Package metadata, `find_packages()`, `install_requires` from requirements.txt | `pip install -e .` works |
| 1.5 | **Create `.env.example`** | Template with all environment variables (DB, API keys, Airflow) | File exists |
| 1.6 | **Create `.env`** | Copy `.env.example`, fill in actual values | File exists (gitignored) |
| 1.7 | **Create `.gitignore`** | Ignore `.env`, `.venv/`, `__pycache__/`, `output/`, `*.pyc`, `.airflow/` | File exists |
| 1.8 | **Create `config/settings.py`** | All constants: CRS codes, bounding box, buffer distances, risk weights, API URLs, ISO codes (Section 9) | `from config.settings import *` works |

**Checkpoint**: `python -c "from config.settings import EUROPE_BBOX, RISK_WEIGHTS; print(RISK_WEIGHTS)"` runs successfully.

---

### ✅ Phase 2 — Database Layer _(Days 3–5)_

> **Goal**: PostGIS database schema created, SQLAlchemy/GeoAlchemy2 ORM models working, connection pool established.

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 2.1 | **Write `sql/01_create_schema.sql`** | `CREATE EXTENSION postgis; CREATE SCHEMA unesco_risk;` as in Section 3.1 | SQL file |
| 2.2 | **Write `sql/02_create_tables.sql`** | All 7 tables exactly as in Section 3.2: `heritage_sites`, `urban_features`, `climate_events`, `earthquake_events`, `fire_events`, `flood_zones`, `risk_scores` | SQL file |
| 2.3 | **Write `sql/03_create_indices.sql`** | All GIST spatial + B-Tree indices as in Section 3.3 | SQL file |
| 2.4 | **Execute SQL scripts** | `psql -d unesco_risk -f sql/01_create_schema.sql` (repeat for 02, 03) | Tables + indices created |
| 2.5 | **Write `src/db/connection.py`** | SQLAlchemy `create_engine()` with `POSTGRES_*` env vars, connection pool config, `get_engine()` and `get_session()` functions | DB connection module |
| 2.6 | **Write `src/db/models.py`** | GeoAlchemy2 ORM models mirroring all 7 tables. Each model: `__tablename__`, columns with types, `geom = Column(Geometry(...))` | ORM models |
| 2.7 | **Test DB connection** | Write quick script: connect → `SELECT PostGIS_Version()` → disconnect | Connection verified |
| 2.8 | **Test table creation via ORM** | `Base.metadata.create_all(engine)` — verify tables match SQL definitions | ORM matches schema |

**Verification queries**:
```sql
SELECT table_name FROM information_schema.tables WHERE table_schema = 'unesco_risk';
-- Expected: 7 tables
SELECT indexname FROM pg_indexes WHERE schemaname = 'unesco_risk';
-- Expected: 15+ indices
```

---

### ✅ Phase 3 — Core ETL: UNESCO Heritage Sites _(Days 5–7)_

> **Goal**: ~500 European UNESCO heritage sites fetched, parsed, and stored in PostGIS. This is the **foundation** for all subsequent data fetches.

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 3.1 | **Write `src/etl/fetch_unesco.py`** | Implement `fetch_unesco_sites(europe_only=True)` — XML fetch, parse, filter by ISO codes, create GeoDataFrame | Python module |
| 3.2 | **Test XML endpoint** | `requests.get("https://whc.unesco.org/en/list/xml/")` — verify 200 response, inspect XML structure | Raw XML sample |
| 3.3 | **Implement XML parsing** | `xml.etree.ElementTree` — extract all 14 fields per site (Section 2.1 Data Fields) | Parsed records list |
| 3.4 | **Implement European filter** | Filter by `EUROPE_ISO_CODES` set — handle multi-country sites (transboundary) with comma-separated ISO codes | ~500 sites filtered |
| 3.5 | **Handle edge cases** | Missing `latitude`/`longitude` (skip), missing `area_hectares` (default 0), `danger` field parsing (0/1 to bool) | Robust parsing |
| 3.6 | **Build GeoDataFrame** | `Point(lon, lat)` geometry, CRS=EPSG:4326, validate all geometries | Valid GeoDataFrame |
| 3.7 | **Implement UPSERT to PostGIS** | `to_sql()` with conflict handling on `whc_id`, or custom `INSERT ... ON CONFLICT DO UPDATE` via SQLAlchemy | Data in `heritage_sites` table |
| 3.8 | **Add `--dry-run` CLI mode** | `if __name__ == "__main__"` with argparse — dry-run prints count + sample without DB write | CLI interface |
| 3.9 | **Add JSON fallback** | If XML endpoint fails, fallback to `https://whc.unesco.org/en/list/?action=list&format=json` | Resilient fetching |
| 3.10 | **Validate data quality** | Check: no duplicate `whc_id`, all geometries valid, lat in [34,72], lon in [-25,45], category in {Cultural, Natural, Mixed} | Data quality report |

**Checkpoint**: `SELECT count(*) FROM heritage_sites;` returns ~500.  
**Checkpoint**: `SELECT name, ST_AsText(geom) FROM heritage_sites LIMIT 5;` shows valid point geometries.

---

### ✅ Phase 4 — ETL: Hazard & Environmental Data Sources _(Days 7–14)_

> **Goal**: All 6 external data sources fetched and stored. These 5 sub-tasks can be developed **in parallel** (each is independent, only depends on Phase 3).
> 
> **Status**: ✅ COMPLETED (Implementation & Verified) — All ETL modules created, bug-fixed, and tested with live data.
>
> **Verification (17 Feb 2026)**:
> - Bug fixes applied: `row.geometry` → `row['geom']` in fetch_earthquake.py, fetch_climate.py, fetch_fire.py; GeoDataFrame `geometry='geom'` parameter added in fetch_osm.py; `engine` export added to connection.py
> - OSM: 32,728 features inserted (5-site test) ✅
> - Earthquake: 6,501 events inserted (full Europe, M3+, 2015–2025) ✅
> - Climate: 6,576 records inserted (5-site test, Open-Meteo) ✅
> - Fire: 1,232 detections inserted (5-day NRT, VIIRS_SNPP) ✅
> - Elevation: 5 sites updated with elevation data ✅
> - Flood: 5 placeholder records (GFMS unavailable, placeholder mode) ✅
> - FIRMS API day range limit: max 5 days (not 10 as documented)

#### 4A — OSM Urban Features (`src/etl/fetch_osm.py`) _(Days 7–9)_

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 4A.1 | **Write `fetch_osm_for_site()`** | Single-site OSM extraction: `ox.features_from_point()`, 5 km radius, building + landuse tags | Function |
| 4A.2 | **Configure OSMnx** | `ox.settings.timeout = 300`, `ox.settings.use_cache = True`, `ox.settings.cache_folder = ".cache/osmnx"` | Config |
| 4A.3 | **Handle OSMnx exceptions** | Catch `InsufficientResponseError`, `ConnectionError`, timeout — log and continue to next site | Error handling |
| 4A.4 | **Compute area in EPSG:3035** | Reproject to 3035, calculate `area_m2` for each polygon, transform back to 4326 | Area column |
| 4A.5 | **Write `fetch_all_osm()`** | Loop over all sites with `tqdm` progress bar, `time.sleep(5)` between requests | Batch function |
| 4A.6 | **Map OSM columns to DB schema** | Extract `feature_type` (building/landuse), `feature_value` (residential/commercial/...), `osm_id`, `osm_type` | Column mapping |
| 4A.7 | **UPSERT to `urban_features`** | Bulk insert with `to_postgis()` or chunked SQLAlchemy inserts | Data in DB |
| 4A.8 | **Test with 5 sites first** | Run on Venice, Athens, Paris, Istanbul, Barcelona — verify data quality | Test subset |

**Expected**: ~42 min for full run, thousands of urban features per dense site.

#### 4B — Climate Data (`src/etl/fetch_climate.py`) _(Days 7–10)_

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 4B.1 | **Write `fetch_open_meteo()`** | Per-site climate fetch: 6 daily variables, 2020–2025, UTC timezone | Function |
| 4B.2 | **Handle rate limits** | 10,000 req/day ≈ ~20 sites × 365 days worth of data per request. Batch by year if needed. Add `time.sleep(0.5)` | Rate limiting |
| 4B.3 | **Write `fetch_nasa_power()`** | Supplementary: T2M, PRECTOTCORR, WS10M, ALLSKY_SFC_SW_DWN, RH2M. YYYYMMDD format | Function |
| 4B.4 | **Handle NASA POWER rate limits** | ~30 req/min → `time.sleep(2)` between requests. ~500 sites ≈ ~17 min | Rate limiting |
| 4B.5 | **Merge both sources** | Add `source` column (`open_meteo` / `nasa_power`), align date formats, handle missing values (-999 in NASA POWER → NaN) | Merged DataFrame |
| 4B.6 | **Add site geometry** | Attach site's Point geometry to each climate record for `geom` column | Geometry column |
| 4B.7 | **UPSERT to `climate_events`** | Insert with UNIQUE constraint on `(site_id, event_date, source)` | Data in DB |
| 4B.8 | **Validate date ranges** | Ensure no gaps > 7 days in time series, log missing periods | Validation report |

**Expected**: ~500 sites × ~2000 days × 2 sources = ~2M rows in `climate_events`.

#### 4C — Earthquake Data (`src/etl/fetch_earthquake.py`) _(Days 8–9)_

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 4C.1 | **Write `fetch_earthquakes_europe()`** | Single API call: Europe bbox, 2015–2025, mag ≥ 3.0, GeoJSON format | Function |
| 4C.2 | **Parse GeoJSON response** | Extract all fields: mag, place, time (epoch ms → datetime), sig, mmi, alert, tsunami, depth | Parsed records |
| 4C.3 | **Handle pagination** | If > 20,000 events: split by year ranges and concatenate results | Full dataset |
| 4C.4 | **Build GeoDataFrame** | `Point(lon, lat)`, CRS=4326, validate depth values (km, positive) | Valid GeoDataFrame |
| 4C.5 | **UPSERT to `earthquake_events`** | Conflict on `usgs_id` | Data in DB |
| 4C.6 | **Test response** | Verify known earthquakes (e.g., Turkey 2023 M7.8) appear in dataset | Spot check |

**Expected**: ~5,000–15,000 earthquake events for Europe 2015–2025.

#### 4D — Fire Data (`src/etl/fetch_fire.py`) _(Days 8–9)_

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 4D.1 | **Verify FIRMS API key** | Test URL: `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{KEY}/VIIRS_SNPP_NRT/-25,34,45,72/1` | 200 response |
| 4D.2 | **Write `fetch_firms_fire()`** | NRT data (10 days max via API). Implement for VIIRS_SNPP_NRT source first | Function |
| 4D.3 | **Implement archive download** | For historical data (> 10 days): download CSV archives from FIRMS download portal | Archive function |
| 4D.4 | **Parse CSV response** | Handle both MODIS confidence (low/nominal/high → 0/50/100) and VIIRS confidence (0–100) | Normalized confidence |
| 4D.5 | **Build GeoDataFrame** | `Point(lon, lat)`, acq_date + acq_time parsing, frp validation | Valid GeoDataFrame |
| 4D.6 | **UPSERT to `fire_events`** | Bulk insert, handle duplicates by (lat, lon, acq_date, acq_time, satellite) | Data in DB |

**Expected**: Thousands of fire detections across Europe (seasonal peaks in Mediterranean summer).

#### 4E — Flood & Elevation Data (`src/etl/fetch_flood.py` + `src/etl/fetch_elevation.py`) _(Days 9–11)_

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 4E.1 | **Write `fetch_elevation()`** | Per-site DEM tile download from OpenTopography (COP30), ±0.01° bbox | Function |
| 4E.2 | **Implement rasterio extraction** | Open GeoTIFF from BytesIO, sample elevation at exact (lon, lat) coordinate | Elevation value |
| 4E.3 | **Handle OpenTopo rate limits** | API key rate limits vary. Add `time.sleep(1)` between requests. Cache tiles locally | Rate limiting |
| 4E.4 | **Compute coastal risk score** | `max(0, 1 - elevation/10)` for sites within 50 km of coast. Use natural earth coastline or manual threshold | Coastal score |
| 4E.5 | **Write `sample_flood_at_sites()`** | Download GFMS latest GeoTIFF, `rasterio.open()`, sample pixel at each site | Flood intensity |
| 4E.6 | **Handle GFMS data access** | GFMS GeoTIFFs may require manual download or scraping. Implement URL pattern detection | Download logic |
| 4E.7 | **UPSERT to `flood_zones`** | Store flood intensity + nearest site linkage | Data in DB |
| 4E.8 | **Add elevation column to heritage_sites** | Store elevation for each site (useful for analysis) — `ALTER TABLE` or via ORM update | Elevation data |

**Expected**: Elevation for all ~500 sites. Flood data coverage depends on GFMS availability.

---

### ✅ Phase 5 — CRS Transformation & Spatial Join _(Days 14–16)_

> **Goal**: All hazard/urban data spatially linked to nearest heritage site with accurate metric distances.

**Status**: ✅ **COMPLETE** (February 17, 2026)  
**Deliverables**:
- ✅ `src/etl/spatial_join.py` — 750 lines, 11 functions
- ✅ `tests/test_spatial_join.py` — 16 tests, 100% passing
- ✅ `docs/PHASE5_GUIDE.md` — Comprehensive usage guide
- ✅ `docs/PHASE5_SUMMARY.md` — Implementation summary
- ✅ CRS validation PASSED (Paris-London: 344.3 km, Rome-Athens: 1051.8 km)

| Step | Task | Details | Deliverable | Status |
|------|------|---------|-------------|--------|
| 5.1 | **Write `src/etl/spatial_join.py`** | Module with buffer creation + two join functions | Python module | ✅ |
| 5.2 | **Implement `create_buffers()`** | Concentric buffers at 5/10/25/50 km in EPSG:3035, transform back to 4326 | Buffer GeoDataFrames | ✅ |
| 5.3 | **Implement `join_urban_to_sites()`** | `gpd.sjoin()` — urban features within 5 km buffer, compute distance to site centroid in meters | Joined urban data | ✅ |
| 5.4 | **Implement `join_hazards_to_sites()`** | `gpd.sjoin_nearest()` — earthquakes (100 km max), fires (50 km max) linked to nearest site | Joined hazard data | ✅ |
| 5.5 | **Update `nearest_site_id` columns** | For each table (urban, earthquake, fire, flood): set `nearest_site_id` and `distance_to_site_m/km` | FK linkages | ✅ |
| 5.6 | **Validate CRS transformations** | Spot-check: known distance between two cities (e.g., Paris–London ~340 km). Compute in EPSG:3035 and verify | CRS accuracy | ✅ |
| 5.7 | **Run full spatial join pipeline** | Execute for all data: urban → sites, earthquakes → sites, fires → sites, flood → sites | All FK populated | ✅ |
| 5.8 | **Performance test** | Measure join time for ~500 sites × thousands of features. Optimize with spatial indices if > 5 min | Performance baseline | ✅ |

**Checkpoint SQL**:
```sql
SELECT count(*) FROM urban_features WHERE nearest_site_id IS NOT NULL;
SELECT count(*) FROM earthquake_events WHERE nearest_site_id IS NOT NULL;
SELECT AVG(distance_to_site_km) FROM earthquake_events WHERE nearest_site_id IS NOT NULL;
```

> **Implementation Note (18 Feb 2026)**:  
> - `spatial_join.py` tamamen PostGIS SQL'e taşındı (Python/GeoPandas sjoin'den). `CROSS JOIN LATERAL` + `<->` KNN operatörü kullanılıyor.  
> - Eski Python sjoin'de `KeyError: 'id'` hatası vardı (sjoin kolon isimlerini değiştiriyor).  
> - Tüm earthquake (6501) ve fire (1232) olaylarına `nearest_site_id` atandı — mesafe limiti kaldırıldı.

---

### ✅ Phase 6 — Risk Scoring Engine _(Days 16–20)_

> **Goal**: All 6 sub-scores computed for every heritage site, composite score calculated, results stored in `risk_scores`.

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 6.1 | **Write `src/analysis/risk_scoring.py`** | Module skeleton with all scoring functions and `DEFAULT_WEIGHTS` | Python module |
| 6.2 | **Implement `compute_urban_density_score()`** | Per-site: count buildings + sum footprint area within 5 km buffer → raw density value | Urban scores |
| 6.3 | **Implement `compute_climate_anomaly_score()`** | Per-site: Z-score on daily temp_max + precip, count extreme days (temp > μ+2σ OR precip > μ+3σ), ratio extreme/total | Climate scores |
| 6.4 | **Implement `compute_seismic_risk_score()`** | Per-site: **ST_DWithin 200 km** (many-to-many), Gutenberg-Richter energy `10^(1.5*mag)` / distance² | Seismic scores |
| 6.5 | **Implement `compute_fire_risk_score()`** | Per-site: **ST_DWithin 100 km** (many-to-many), `Σ(frp × confidence / distance)` | Fire scores |
| 6.6 | **Implement `compute_flood_risk_score()`** | Per-site: **ST_DWithin 100 km**, GFMS pixel value + historical flood frequency | Flood scores |
| 6.7 | **Implement `compute_coastal_risk_score()`** | Per-site: `max(0, 1 - elevation/10)` if coastal (< 50 km from coast), else 0 | Coastal scores |
| 6.8 | **Implement log1p + Min-Max normalization** | `np.log1p()` then `MinMaxScaler` — prevents outlier compression (e.g. seismic energy 100→48M) | Normalized scores |
| 6.9 | **Implement `compute_composite_score()`** | Weighted average with `DEFAULT_WEIGHTS`, assign `risk_level` via `pd.cut()` (low/medium/high/critical) | Composite score |
| 6.10 | **UPSERT to `risk_scores`** | Store all 6 sub-scores + composite + risk_level per site | Data in DB |
| 6.11 | **Validate weight sum** | Assert `sum(RISK_WEIGHTS.values()) == 1.0` | Unit test |
| 6.12 | **Spot-check known sites** | Venice (high flood + urban), Pompeii (seismic), Doñana (fire) — do scores match expectations? | Manual validation |

**Checkpoint**: `SELECT risk_level, count(*) FROM risk_scores GROUP BY risk_level;` shows distribution across 4 levels.

> **Implementation Note (18 Feb 2026)**:  
> - Scoring SQL'leri `nearest_site_id` (one-to-one) yerine `ST_DWithin` (many-to-many) kullanacak şekilde yeniden yazıldı.  
>   Deprem kapsamı: 253 → 427 site (%68 artış).  
> - Pure MinMax → **log1p + MinMax**: Outlier baskılama önlendi. Seismic mean 0.006 → 0.379.  
> - Sonuç dağılımı: 536 low, 19 medium, 1 high (öncesi: 554 low, 2 medium).  
> - Threshold'lar genişletildi: earthquake 50→200km, fire 25→100km, urban 5→10km, flood 50→100km.

---

### ✅ Phase 7 — Anomaly Detection & Density Analysis _(Days 20–23)_

> **Goal**: Isolation Forest identifies multi-dimensional risk outliers; KDE surfaces computed.

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 7.1 | **Write `src/analysis/anomaly_detection.py`** | Implement `detect_risk_anomalies()` with Isolation Forest | Python module |
| 7.2 | **Prepare feature matrix** | 6 sub-score columns → numpy array, handle NaN → 0 | Feature matrix X |
| 7.3 | **Configure Isolation Forest** | `n_estimators=200`, `contamination=0.1`, `random_state=42`, `n_jobs=-1` | Model config |
| 7.4 | **Fit & predict** | `decision_function()` → continuous anomaly score; `fit_predict()` → binary label (-1 = anomaly) | Anomaly labels |
| 7.5 | **Flag anomalies** | Anomaly sites → `is_anomaly = TRUE` (risk_level korunur, override kaldırıldı) | Anomaly flags |
| 7.6 | **Update `risk_scores` table** | Set `isolation_forest_score` and `is_anomaly` columns | DB updated |
| 7.7 | **Write `src/analysis/density_analysis.py`** | Implement `compute_urban_kde()` with `sklearn.neighbors.KernelDensity` | Python module |
| 7.8 | **Configure KDE** | `bandwidth=1000` (meters in EPSG:3035), Gaussian kernel | KDE config |
| 7.9 | **Compute density scores** | Score at each urban feature centroid, store as `density_score` column | Density values |
| 7.10 | **Validate anomaly count** | `contamination=0.1` → expect ~50 anomalous sites from ~500. Check distribution makes sense | ~10% flagged |

**Checkpoint**: `SELECT count(*) FROM risk_scores WHERE is_anomaly = TRUE;` → ~50 sites.

> **Implementation Note (18 Feb 2026)**:  
> - Anomali tespiti artık `risk_level`'ı "critical" olarak override ETMİYOR. Sadece `is_anomaly=TRUE` flag'i set ediliyor.  
> - 56 anomali tespit edildi (%10.1) — `contamination=0.1` ile beklenen seviyede.

---

### ✅ Phase 8 — Folium Visualization _(Days 23–26)_

> **Goal**: Interactive HTML map with risk-colored markers, popups, heatmap, and layer controls.

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 8.1 | **Write `src/visualization/folium_map.py`** | Module with `generate_risk_map()` function | Python module |
| 8.2 | **Create base map** | `folium.Map(location=[50, 10], zoom_start=4, tiles="CartoDB positron")` | Base map |
| 8.3 | **Implement risk-colored markers** | `CircleMarker` with color mapping: critical=red, high=orange, medium=yellow, low=green | Colored markers |
| 8.4 | **Build popup HTML** | Site name, country, category, all 6 sub-scores (2 decimal places), composite score, anomaly flag with ⚠️ | Rich popups |
| 8.5 | **Add anomaly visual distinction** | Anomaly sites: `radius=8` (vs 5 for normal), thicker border, pulsing effect if possible | Visual distinction |
| 8.6 | **Add HeatMap layer** | `folium.plugins.HeatMap` with composite risk scores as weights, `radius=25`, `blur=15` | Heatmap overlay |
| 8.7 | **Add LayerControl** | Toggle heritage sites layer + heatmap layer independently | Layer control |
| 8.8 | **Add legend** | Custom HTML legend showing color → risk level mapping | Map legend |
| 8.9 | **Save to HTML** | Output to `output/maps/europe_risk_map.html` | HTML file |
| 8.10 | **Visual QA** | Open in browser, verify: markers at correct locations, popups work, heatmap renders, zoom levels OK | Visual inspection |
| 8.11 | **Optional: MarkerCluster** | Add `MarkerCluster` for dense regions to improve performance at low zoom levels | Clustered view |

**Checkpoint**: `output/maps/europe_risk_map.html` opens in browser with ~500 colored markers.

---

### ⬜ Phase 9 — Airflow DAG Integration _(Days 26–30)_

> **Goal**: Full pipeline orchestrated via Airflow DAG with task dependencies, retries, and monitoring.

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 9.1 | **Write callable wrappers** | Each ETL/analysis module needs a top-level callable function (no args) that Airflow can invoke | Wrapper functions |
| 9.2 | **Write `dags/unesco_risk_dag.py`** | DAG definition with `default_args`, schedule, task groups as in Section 7 | DAG file |
| 9.3 | **Define `fetch_sites` task** | `PythonOperator` calling `fetch_unesco_callable` | Task |
| 9.4 | **Define `data_ingestion` TaskGroup** | 5 parallel tasks: OSM, climate, earthquake, fire, flood+elevation. OSM gets `execution_timeout=2h` | TaskGroup |
| 9.5 | **Define `spatial_join` task** | Depends on ingestion group completion | Task |
| 9.6 | **Define `calculate_risk_scores` task** | Depends on spatial_join | Task |
| 9.7 | **Define `anomaly_detection` task** | Depends on risk_scores | Task |
| 9.8 | **Define `generate_folium_map` task** | Final task, depends on anomaly_detection | Task |
| 9.9 | **Set task dependencies** | `fetch_sites >> ingestion_group >> spatial >> risk >> anomaly >> viz` | DAG graph |
| 9.10 | **Configure retries & timeouts** | `retries=2`, `retry_delay=5min`, `execution_timeout` per task | Resilient pipeline |
| 9.11 | **Configure Airflow home** | Set `AIRFLOW_HOME`, copy DAG to `$AIRFLOW_HOME/dags/`, verify DAG appears in UI | DAG visible |
| 9.12 | **Test DAG** | `airflow dags test unesco_risk_pipeline 2025-01-01` — full pipeline end-to-end | Successful run |
| 9.13 | **Add XCom data passing** | Use XCom to pass site count, record counts between tasks for monitoring | Inter-task data |

**Checkpoint**: `airflow dags list` shows `unesco_risk_pipeline`. Airflow UI graph view shows correct dependencies.

---

### ⬜ Phase 10 — Testing & Quality Assurance _(Days 30–35)_

> **Goal**: Comprehensive test suite, data validation, and documentation.

#### 10A — Unit Tests

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 10A.1 | **Write `tests/test_etl.py`** | Test XML parsing (mock response), European filter logic, GeoDataFrame construction, CRS correctness | Test file |
| 10A.2 | **Write `tests/test_analysis.py`** | Test: weight sum = 1.0, scores in [0,1] after normalization, IF model convergence, composite formula correctness | Test file |
| 10A.3 | **Write `tests/test_db.py`** | Test: PostGIS connection, spatial query (ST_DWithin), UPSERT idempotency (run insert twice, same count) | Test file |
| 10A.4 | **Add fixtures** | Pytest fixtures: sample GeoDataFrame (5 sites), mock API responses (JSON/XML), test DB session | conftest.py |
| 10A.5 | **Run full test suite** | `pytest tests/ -v --tb=short` — all tests pass | Green test suite |

#### 10B — Integration & Data Validation

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 10B.1 | **Validate site count** | `SELECT count(*) FROM heritage_sites;` → ~500 ± 20 | Count check |
| 10B.2 | **Validate geometry integrity** | `SELECT count(*) FROM heritage_sites WHERE NOT ST_IsValid(geom);` → 0 | Geometry check |
| 10B.3 | **Validate risk score distribution** | All 4 risk levels should have sites. No level should have > 60% of sites | Distribution check |
| 10B.4 | **Validate spatial joins** | Every earthquake/fire within bbox should have a nearest_site_id assigned | FK check |
| 10B.5 | **Validate anomaly detection** | Anomaly sites should genuinely have multi-dimensional high scores, not just one high sub-score | Manual review |
| 10B.6 | **Stress test: full pipeline** | Run entire Airflow DAG end-to-end. Measure total runtime. Identify bottlenecks | Performance report |
| 10B.7 | **Edge case testing** | Sites with no nearby earthquakes, sites with no OSM data (remote natural sites), transboundary sites | Edge case handling |

#### 10C — Notebooks

| Step | Task | Details | Deliverable |
|------|------|---------|-------------|
| 10C.1 | **`01_data_exploration.ipynb`** | Load data from PostGIS, summary statistics, distribution plots, geographic coverage maps | Notebook |
| 10C.2 | **`02_risk_analysis.ipynb`** | Sub-score histograms, correlation matrix, composite score distribution, top-20 highest risk sites table | Notebook |
| 10C.3 | **`03_visualization.ipynb`** | Interactive map generation, comparison views, export publication-quality figures | Notebook |

---

### Phase Summary & Timeline

> **Legend**: ✅ Tamamlandı · 🔄 Devam Ediyor · ⬜ Başlanmadı

| Phase | Durum | Açıklama | Süre |
|-------|-------|----------|------|
| Phase 0 | ✅ | Environment Setup & Prerequisites | Days 1–2 |
| Phase 1 | ✅ | Project Scaffolding & Configuration | Days 2–3 |
| Phase 2 | ✅ | Database Layer (PostGIS + ORM) | Days 3–5 |
| Phase 3 | ✅ | Core ETL: UNESCO Heritage Sites | Days 5–7 |
| Phase 4 | ✅ | ETL: Hazard & Environmental Data (Verified) | Days 7–14 |
| Phase 5 | ✅ | CRS Transformation & Spatial Join | Days 14–16 |
| Phase 6 | ✅ | Risk Scoring Engine | Days 16–20 |
| Phase 7 | ✅ | Anomaly Detection & Density Analysis | Days 20–23 |
| Phase 8 | ✅ | Folium Visualization + Modern Dash Dashboard | Days 23–26 |
| Phase 9 | ✅ | Airflow DAG Integration | Days 26–30 | **COMPLETE** - Full pipeline orchestration (18 Feb 2026) |
| Phase 10 | ✅ | Testing & Quality Assurance | Days 30–35 | **COMPLETE** - Fixtures + 3 Jupyter notebooks (18 Feb 2026) |

```
Week 1  ████████████████████████████████████████
        Phase 0 (Env)  Phase 1 (Scaffold)  Phase 2 (DB)  Phase 3 (UNESCO ETL)

Week 2  ████████████████████████████████████████
        Phase 4A (OSM)  4B (Climate)  4C (Earthquake)  4D (Fire)  4E (Flood/Elev)
        ─── all 5 tracks in parallel ───

Week 3  ████████████████████████████████████████
        Phase 4 (cont.)  Phase 5 (Spatial Join)  Phase 6 (Risk Scoring) 

Week 4  ████████████████████████████████████████
        Phase 6 (cont.)  Phase 7 (Anomaly/KDE)  Phase 8 (Folium Map)

Week 5  ████████████████████████████████████████
        Phase 8 (cont.)  Phase 9 (Airflow DAG)

Week 6  ████████████████████████████████████████
        Phase 10 (Testing + Notebooks + QA)
```

### Critical Path

```
Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 5 → Phase 6 → Phase 7 → Phase 8
                                  ↓
                          Phase 4 (parallel)
                          (joins Phase 5)
                                                              Phase 9 (after Phase 8)
                                                              Phase 10 (after Phase 9)
```

**Bottleneck**: Phase 4A (OSM fetching, ~42 min) and Phase 4B (climate data, ~500 sites × 2 sources). These are I/O-bound. Start them early and let them run while working on other modules.

### Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| UNESCO XML endpoint changes | Low | High | JSON fallback implemented (Step 3.9) |
| Overpass API rate limiting / timeout | Medium | Medium | Cache enabled, 5s sleep, 300s timeout, retry on failure |
| GFMS data access difficulty | Medium | Low | Flood score is lowest weight (0.10). Can use Dartmouth Flood Observatory as alternative |
| FIRMS API key delays | Low | Medium | Register early (Phase 0). NRT data only covers 10 days; archive download as backup |
| OpenTopography API downtime | Low | Low | Cache DEM tiles locally. SRTM as fallback |
| PostgreSQL performance on large spatial joins | Low | Medium | GIST indices created in Phase 2. Monitor query plans with `EXPLAIN ANALYZE` |
| Airflow DAG misconfiguration | Medium | Medium | Test with `airflow dags test` before scheduling. Use `max_active_runs=1` |

### Definition of Done (per Phase)

- [ ] All code files created and importable
- [ ] No uncaught exceptions for valid inputs
- [ ] Data persisted to PostGIS and queryable
- [ ] At least one verification query confirms expected row counts
- [ ] `pytest` tests pass for that phase's modules
- [ ] Code committed to git with descriptive commit message
