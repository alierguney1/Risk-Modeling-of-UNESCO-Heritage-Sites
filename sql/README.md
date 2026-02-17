# Database Setup Guide - Phase 2

This guide covers the Phase 2 database layer setup for the UNESCO Heritage Sites Risk Modeling project.

## Overview

Phase 2 establishes the complete PostGIS database infrastructure:
- 7 tables for heritage sites, hazard data, and risk analysis
- Spatial (GIST) and B-Tree indices for optimized queries
- SQLAlchemy/GeoAlchemy2 ORM models
- Connection pooling and session management

## Prerequisites

Before running Phase 2 setup, ensure you have:

1. **PostgreSQL 16+ with PostGIS extension installed**
   ```bash
   sudo apt install postgresql-16 postgresql-16-postgis-3
   ```

2. **PostgreSQL service running**
   ```bash
   sudo systemctl start postgresql
   sudo systemctl status postgresql
   ```

3. **Database and user created**
   ```bash
   # Connect as postgres user
   sudo -u postgres psql
   
   # Create database and user
   CREATE DATABASE unesco_risk;
   CREATE USER postgres_user WITH PASSWORD 'changeme';
   GRANT ALL PRIVILEGES ON DATABASE unesco_risk TO postgres_user;
   ```

4. **Environment variables configured**
   
   Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env`:
   ```
   POSTGRES_HOST=127.0.0.1
   POSTGRES_PORT=5432
   POSTGRES_DB=unesco_risk
   POSTGRES_USER=postgres_user
   POSTGRES_PASSWORD=changeme
   ```

## Database Schema

The schema includes 7 tables in the `unesco_risk` schema:

1. **heritage_sites** - UNESCO heritage sites (Point geometry)
2. **urban_features** - OSM building/landuse data (Polygon/MultiPolygon)
3. **climate_events** - Daily climate time-series from Open-Meteo and NASA POWER
4. **earthquake_events** - USGS earthquake data (Point)
5. **fire_events** - NASA FIRMS fire detections (Point)
6. **flood_zones** - GFMS flood data (Point)
7. **risk_scores** - Computed multi-variate risk scores

## Setup Methods

### Method 1: SQL Scripts (Recommended)

Execute the SQL scripts in order:

```bash
# 1. Create schema and enable PostGIS
psql -h 127.0.0.1 -U postgres_user -d unesco_risk -f sql/01_create_schema.sql

# 2. Create all 7 tables
psql -h 127.0.0.1 -U postgres_user -d unesco_risk -f sql/02_create_tables.sql

# 3. Create spatial and B-Tree indices
psql -h 127.0.0.1 -U postgres_user -d unesco_risk -f sql/03_create_indices.sql
```

### Method 2: SQLAlchemy ORM

Use the Python ORM to create tables:

```python
from src.db.connection import create_tables

# Create all tables
create_tables()
```

## Verification

### Test Database Connection

```bash
python tests/test_db.py --test-connection
```

Expected output:
```
✓ Database connection successful!
✓ PostGIS version: 3.4 USE_GEOS=1 USE_PROJ=1 USE_STATS=1
```

### Verify Schema

```bash
python tests/test_db.py --verify
```

This will check:
- All 7 tables exist
- All indices are created (14+ indices expected)

### Test ORM Models

```bash
python tests/test_db.py --test-orm
```

### Run All Tests

```bash
python tests/test_db.py --all
```

## Database Connection Usage

### Basic Connection

```python
from src.db.connection import get_engine, get_session

# Get engine
engine = get_engine()

# Get session
session = get_session()

try:
    # Your database operations
    result = session.query(HeritageSite).all()
    session.commit()
except Exception as e:
    session.rollback()
    raise
finally:
    session.close()
```

### Using ORM Models

```python
from src.db.models import HeritageSite, ClimateEvent, RiskScore
from src.db.connection import get_session
from shapely.geometry import Point
from geoalchemy2.shape import from_shape

# Create a new heritage site
session = get_session()

new_site = HeritageSite(
    whc_id=1234,
    name="Example Site",
    category="Cultural",
    country="Italy",
    iso_code="IT",
    geom=from_shape(Point(12.4964, 41.9028), srid=4326)  # Rome coordinates
)

session.add(new_site)
session.commit()
session.close()
```

### Spatial Queries

```python
from src.db.connection import get_session
from src.db.models import HeritageSite, EarthquakeEvent
from geoalchemy2.functions import ST_Distance, ST_Transform
from sqlalchemy import func

session = get_session()

# Find heritage sites within 50km of earthquakes (using projected CRS for meters)
query = session.query(
    HeritageSite.name,
    EarthquakeEvent.magnitude,
    func.ST_Distance(
        ST_Transform(HeritageSite.geom, 3035),
        ST_Transform(EarthquakeEvent.geom, 3035)
    ).label('distance_m')
).filter(
    func.ST_DWithin(
        ST_Transform(HeritageSite.geom, 3035),
        ST_Transform(EarthquakeEvent.geom, 3035),
        50000  # 50km in meters
    )
)

results = query.all()
session.close()
```

## Table Statistics

After populating data, you can check table statistics:

```sql
-- Row counts
SELECT 
    schemaname, 
    relname AS table_name, 
    n_live_tup AS row_count
FROM pg_stat_user_tables
WHERE schemaname = 'unesco_risk'
ORDER BY n_live_tup DESC;

-- Table sizes
SELECT 
    schemaname,
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname)) AS total_size
FROM pg_stat_user_tables
WHERE schemaname = 'unesco_risk'
ORDER BY pg_total_relation_size(schemaname||'.'||relname) DESC;
```

## Expected Data Volumes

After Phase 3+ ETL:

| Table | Expected Rows | Notes |
|-------|--------------|-------|
| heritage_sites | ~500 | European UNESCO sites |
| urban_features | ~100K-500K | Depends on OSM density |
| climate_events | ~2M | 500 sites × ~2000 days × 2 sources |
| earthquake_events | ~10K-50K | 2015-2025, magnitude ≥ 3.0 |
| fire_events | ~10K-100K | Last 10 days rolling |
| flood_zones | Variable | Depends on GFMS data availability |
| risk_scores | ~500 | One per heritage site |

## Troubleshooting

### Connection Error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution**: Check PostgreSQL is running and accepting connections:
```bash
sudo systemctl status postgresql
sudo systemctl start postgresql
pg_isready
```

### PostGIS Not Found

```
ERROR: could not open extension control file
```

**Solution**: Install PostGIS extension:
```bash
sudo apt install postgresql-16-postgis-3
```

### Permission Denied

```
ERROR: permission denied for schema public
```

**Solution**: Grant schema permissions:
```sql
GRANT ALL ON SCHEMA unesco_risk TO postgres_user;
GRANT ALL ON ALL TABLES IN SCHEMA unesco_risk TO postgres_user;
```

### Tables Already Exist

If tables already exist and you need to recreate:

```sql
-- Drop schema and all tables (WARNING: deletes all data!)
DROP SCHEMA unesco_risk CASCADE;
```

Then re-run the SQL scripts.

## Next Steps

After completing Phase 2:

1. **Phase 3**: Implement UNESCO data fetcher (`src/etl/fetch_unesco.py`)
2. **Phase 4**: Implement hazard data fetchers (OSM, climate, earthquake, fire, flood)
3. **Phase 5**: Implement risk analysis algorithms
4. **Phase 6**: Create visualization layer

## References

- [PostGIS Documentation](https://postgis.net/documentation/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [GeoAlchemy2 Documentation](https://geoalchemy-2.readthedocs.io/)
