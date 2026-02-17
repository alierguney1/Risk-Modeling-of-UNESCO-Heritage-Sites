-- Create all tables for UNESCO Heritage Sites Risk Modeling
-- Execute after 01_create_schema.sql

SET search_path TO unesco_risk, public;

-- Table 1: heritage_sites — UNESCO Heritage Sites (Point)
CREATE TABLE IF NOT EXISTS heritage_sites (
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

-- Table 2: urban_features — OSM Urban Features (Polygon/Geometry)
CREATE TABLE IF NOT EXISTS urban_features (
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

-- Table 3: climate_events — Climate Time-Series (Open-Meteo + NASA POWER)
CREATE TABLE IF NOT EXISTS climate_events (
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

-- Table 4: earthquake_events — USGS Earthquake Data (Point)
CREATE TABLE IF NOT EXISTS earthquake_events (
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

-- Table 5: fire_events — NASA FIRMS Fire Data (Point)
CREATE TABLE IF NOT EXISTS fire_events (
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

-- Table 6: flood_zones — GFMS Flood Data
CREATE TABLE IF NOT EXISTS flood_zones (
    id                  SERIAL PRIMARY KEY,
    event_date          DATE,
    flood_intensity     FLOAT,
    nearest_site_id     INTEGER REFERENCES heritage_sites(id),
    distance_to_site_km FLOAT,
    geom                GEOMETRY(Point, 4326),
    created_at          TIMESTAMP DEFAULT NOW()
);

-- Table 7: risk_scores — Computed Risk Scores (Analysis Output)
CREATE TABLE IF NOT EXISTS risk_scores (
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
