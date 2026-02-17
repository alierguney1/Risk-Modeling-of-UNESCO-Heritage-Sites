-- Create spatial and B-Tree indices for optimized query performance
-- Execute after 02_create_tables.sql

SET search_path TO unesco_risk, public;

-- GIST spatial indices for geometry columns
CREATE INDEX IF NOT EXISTS idx_heritage_sites_geom       ON heritage_sites       USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_urban_features_geom       ON urban_features       USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_climate_events_geom       ON climate_events       USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_earthquake_events_geom    ON earthquake_events    USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_fire_events_geom          ON fire_events          USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_flood_zones_geom          ON flood_zones          USING GIST (geom);

-- B-Tree indices for frequent lookups and foreign key relationships
CREATE INDEX IF NOT EXISTS idx_climate_events_site_date  ON climate_events       (site_id, event_date);
CREATE INDEX IF NOT EXISTS idx_earthquake_site           ON earthquake_events    (nearest_site_id);
CREATE INDEX IF NOT EXISTS idx_fire_site                 ON fire_events          (nearest_site_id);
CREATE INDEX IF NOT EXISTS idx_flood_site                ON flood_zones          (nearest_site_id);
CREATE INDEX IF NOT EXISTS idx_urban_site                ON urban_features       (nearest_site_id);
CREATE INDEX IF NOT EXISTS idx_risk_scores_site          ON risk_scores          (site_id);
CREATE INDEX IF NOT EXISTS idx_risk_scores_level         ON risk_scores          (risk_level);
CREATE INDEX IF NOT EXISTS idx_risk_scores_anomaly       ON risk_scores          (is_anomaly) WHERE is_anomaly = TRUE;
