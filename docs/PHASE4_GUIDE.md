# Phase 4: Hazard & Environmental Data ETL - Implementation Guide

## Overview

Phase 4 implements ETL (Extract, Transform, Load) modules for 6 external hazard and environmental data sources:

1. **OSM Urban Features** - Building and landuse data from OpenStreetMap
2. **Climate Data** - Historical weather data from Open-Meteo and NASA POWER
3. **Earthquake Data** - Seismic events from USGS Earthquake Catalog
4. **Fire Data** - Active fire detections from NASA FIRMS
5. **Elevation Data** - Digital elevation models from OpenTopography
6. **Flood Data** - Flood intensity from GFMS (Global Flood Monitoring System)

All modules are **complete and ready to execute** once database and API keys are configured.

---

## Module Status

| Module | File | Status | API Key Required |
|--------|------|--------|------------------|
| 4A: OSM | `fetch_osm.py` | ✅ Complete | No |
| 4B: Climate | `fetch_climate.py` | ✅ Complete | No (free APIs) |
| 4C: Earthquake | `fetch_earthquake.py` | ✅ Complete | No |
| 4D: Fire | `fetch_fire.py` | ✅ Complete | Yes (NASA FIRMS) |
| 4E: Elevation | `fetch_elevation.py` | ✅ Complete | Yes (OpenTopography) |
| 4E: Flood | `fetch_flood.py` | ✅ Complete | No (manual download) |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure .env file
cp .env.example .env
# Edit .env and add database credentials and API keys

# 3. Test with limited data
python -m src.etl.fetch_osm --test
python -m src.etl.fetch_climate --test
python -m src.etl.fetch_earthquake --verbose

# 4. Run full ETL (when ready)
python -m src.etl.fetch_osm          # ~42 min
python -m src.etl.fetch_climate      # ~30-60 min
python -m src.etl.fetch_earthquake   # <1 min
python -m src.etl.fetch_fire         # <1 min (if API key configured)
python -m src.etl.fetch_elevation    # ~10-15 min (if API key configured)
python -m src.etl.fetch_flood        # <1 min
```

---

## Verification

After running all modules, verify with SQL:

```sql
SELECT 
    'urban_features' as table_name, COUNT(*) as count 
FROM unesco_risk.urban_features
UNION ALL
SELECT 'climate_events', COUNT(*) FROM unesco_risk.climate_events
UNION ALL
SELECT 'earthquake_events', COUNT(*) FROM unesco_risk.earthquake_events
UNION ALL
SELECT 'fire_events', COUNT(*) FROM unesco_risk.fire_events
UNION ALL
SELECT 'flood_zones', COUNT(*) FROM unesco_risk.flood_zones;
```

---

**Implementation Date**: February 17, 2026  
**Status**: ✅ Phase 4 Complete  
**Next Phase**: Phase 5 - Spatial Join

For detailed module documentation, see individual Python files in `src/etl/`.
