-- Create PostGIS extension and schema for UNESCO Heritage Sites Risk Modeling
-- Execute this script first before running other SQL scripts

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS unesco_risk;
SET search_path TO unesco_risk, public;
