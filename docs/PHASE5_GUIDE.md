# Phase 5 Guide: CRS Transformation & Spatial Join

## Overview

Phase 5 implements the spatial transformation and joining operations that link hazard and urban data to heritage sites. This phase is crucial for calculating accurate metric distances and establishing spatial relationships between UNESCO sites and various risk factors.

## Goals

1. Transform coordinates between CRS systems accurately (WGS84 ↔ ETRS89/LAEA)
2. Create concentric buffer zones around heritage sites (5km, 10km, 25km, 50km)
3. Join urban features to nearby sites within 5km buffer
4. Link hazard events (earthquakes, fires, floods) to nearest heritage sites
5. Populate `nearest_site_id` and `distance_to_site_m/km` columns in all tables

## Module: `src/etl/spatial_join.py`

### Key Functions

#### 1. `create_buffers(sites_gdf, distances_m)`
Creates concentric buffer zones around heritage sites.

**Parameters:**
- `sites_gdf`: GeoDataFrame of heritage sites in EPSG:4326
- `distances_m`: List of buffer distances in meters (default: [5000, 10000, 25000, 50000])

**Returns:**
- Dictionary mapping distance → buffered GeoDataFrame

**Example:**
```python
import geopandas as gpd
from src.etl.spatial_join import create_buffers

# Load heritage sites
sites = gpd.read_postgis("SELECT * FROM heritage_sites", engine)

# Create buffers
buffers = create_buffers(sites, [5000, 10000, 25000])
buffer_5km = buffers[5000]
```

#### 2. `join_urban_to_sites(urban_gdf, sites_gdf, buffer_m=5000)`
Spatial join for urban features within buffer zones.

**Parameters:**
- `urban_gdf`: GeoDataFrame of OSM urban features in EPSG:4326
- `sites_gdf`: GeoDataFrame of heritage sites in EPSG:4326
- `buffer_m`: Buffer distance in meters (default: 5000)

**Returns:**
- GeoDataFrame with joined urban features including `nearest_site_id` and `distance_to_site_m`

**Example:**
```python
from src.etl.spatial_join import join_urban_to_sites

# Load data
urban = gpd.read_postgis("SELECT * FROM urban_features", engine)
sites = gpd.read_postgis("SELECT * FROM heritage_sites", engine)

# Join within 5km buffer
joined = join_urban_to_sites(urban, sites, buffer_m=5000)
```

#### 3. `join_hazards_to_sites(hazard_gdf, sites_gdf, max_distance_m, hazard_type)`
Nearest-neighbor spatial join for point hazards.

**Parameters:**
- `hazard_gdf`: GeoDataFrame of hazard events in EPSG:4326
- `sites_gdf`: GeoDataFrame of heritage sites in EPSG:4326
- `max_distance_m`: Maximum distance for search (meters)
- `hazard_type`: Type of hazard for logging (e.g., 'earthquake', 'fire')

**Returns:**
- GeoDataFrame with joined hazards including `nearest_site_id`, `distance_to_site_m`, and `distance_to_site_km`

**Example:**
```python
from src.etl.spatial_join import join_hazards_to_sites

# Load data
earthquakes = gpd.read_postgis("SELECT * FROM earthquake_events", engine)
sites = gpd.read_postgis("SELECT * FROM heritage_sites", engine)

# Join earthquakes within 50km
joined = join_hazards_to_sites(
    earthquakes, 
    sites, 
    max_distance_m=50000,
    hazard_type='earthquake'
)
```

#### 4. `validate_crs_transformation(sites_gdf)`
Validates CRS transformation accuracy by checking known distances.

**Tests:**
- Paris to London: ~340-350 km
- Rome to Athens: ~1050-1150 km

**Returns:**
- `True` if validation passes, `False` otherwise

**Example:**
```python
from src.etl.spatial_join import validate_crs_transformation

if validate_crs_transformation(sites):
    print("✓ CRS transformations are accurate")
```

#### 5. `run_full_spatial_join(verbose=True, dry_run=False)`
Main entry point - runs complete spatial join pipeline.

**Parameters:**
- `verbose`: Print detailed progress (default: True)
- `dry_run`: Validate only, don't update database (default: False)

**Steps:**
1. Validate CRS transformations
2. Update urban features with nearest sites
3. Update earthquake events with nearest sites
4. Update fire events with nearest sites
5. Update flood zones with nearest sites

**Example:**
```python
from src.etl.spatial_join import run_full_spatial_join

# Run full pipeline
run_full_spatial_join(verbose=True, dry_run=False)
```

## CRS Strategy

| CRS | EPSG | Purpose |
|-----|------|---------|
| **WGS84** | 4326 | Storage, data exchange, API communication |
| **ETRS89/LAEA Europe** | 3035 | Distance/area calculations (metric, accurate for Europe) |
| **Web Mercator** | 3857 | ⚠️ NOT used — area distortion at high latitudes |

**Rule:** All data is stored in EPSG:4326. We project to EPSG:3035 only for metric computations, then transform back to EPSG:4326 for storage.

## Buffer Distances

Default buffer distances for different data types:

```python
BUFFER_DISTANCES = {
    'urban': 5000,        # 5 km for urban features
    'fire': 25000,        # 25 km for fire events  
    'earthquake': 50000,  # 50 km for earthquakes
    'flood': 50000,       # 50 km for flood zones
    'max_distance': 100000  # 100 km maximum for nearest neighbor search
}
```

## CLI Usage

### Help
```bash
python -m src.etl.spatial_join --help
```

### Dry Run (Validation Only)
```bash
# Validate CRS transformations without updating database
python -m src.etl.spatial_join --dry-run
```

### Run Full Pipeline
```bash
# Run spatial join and update database
python -m src.etl.spatial_join
```

### Quiet Mode
```bash
# Minimal output
python -m src.etl.spatial_join --quiet
```

### Verbose Mode
```bash
# Debug-level logging
python -m src.etl.spatial_join --verbose
```

## Prerequisites

Before running Phase 5, ensure:

1. **Phase 0-4 Complete**: Database and all ETL modules set up
2. **Data Populated**: Heritage sites and hazard/urban data loaded
3. **Database Connection**: PostgreSQL with PostGIS running
4. **Environment Variables**: `.env` file configured

## Database Requirements

The following tables must exist and contain data:

- `unesco_risk.heritage_sites` — UNESCO sites (~500+ records)
- `unesco_risk.urban_features` — OSM urban data
- `unesco_risk.earthquake_events` — USGS earthquake data
- `unesco_risk.fire_events` — NASA FIRMS fire data
- `unesco_risk.flood_zones` — GFMS flood data

Each hazard/urban table has these columns that will be populated:
- `nearest_site_id` — Foreign key to `heritage_sites.id`
- `distance_to_site_m` or `distance_to_site_km` — Distance to nearest site

## Testing

### Run Unit Tests
```bash
# Run all spatial join tests
python -m unittest tests.test_spatial_join -v
```

### Test Coverage

The test suite includes 16 tests covering:
- ✅ CRS transformation accuracy
- ✅ Buffer zone creation
- ✅ Urban feature spatial joins
- ✅ Hazard event nearest-neighbor joins
- ✅ Distance calculation consistency
- ✅ Empty input handling
- ✅ Buffer distance filtering

All tests pass without requiring a live database connection.

## Verification Queries

After running the spatial join, verify results with these SQL queries:

### Count Records with Spatial Joins
```sql
-- Urban features with nearest sites
SELECT COUNT(*) 
FROM unesco_risk.urban_features 
WHERE nearest_site_id IS NOT NULL;

-- Earthquake events with nearest sites
SELECT COUNT(*) 
FROM unesco_risk.earthquake_events 
WHERE nearest_site_id IS NOT NULL;

-- Fire events with nearest sites
SELECT COUNT(*) 
FROM unesco_risk.fire_events 
WHERE nearest_site_id IS NOT NULL;

-- Flood zones with nearest sites
SELECT COUNT(*) 
FROM unesco_risk.flood_zones 
WHERE nearest_site_id IS NOT NULL;
```

### Average Distances
```sql
-- Average distance to sites for each hazard type
SELECT AVG(distance_to_site_km) 
FROM unesco_risk.earthquake_events 
WHERE distance_to_site_km IS NOT NULL;

SELECT AVG(distance_to_site_km) 
FROM unesco_risk.fire_events 
WHERE distance_to_site_km IS NOT NULL;

SELECT AVG(distance_to_site_km) 
FROM unesco_risk.flood_zones 
WHERE distance_to_site_km IS NOT NULL;
```

### Top Sites by Hazard Count
```sql
-- Sites with most nearby earthquakes (within 50km)
SELECT 
    hs.name,
    hs.country,
    COUNT(ee.id) as earthquake_count
FROM unesco_risk.heritage_sites hs
LEFT JOIN unesco_risk.earthquake_events ee 
    ON ee.nearest_site_id = hs.id
GROUP BY hs.id, hs.name, hs.country
ORDER BY earthquake_count DESC
LIMIT 10;

-- Sites with most nearby fires (within 25km)
SELECT 
    hs.name,
    hs.country,
    COUNT(fe.id) as fire_count
FROM unesco_risk.heritage_sites hs
LEFT JOIN unesco_risk.fire_events fe 
    ON fe.nearest_site_id = hs.id
GROUP BY hs.id, hs.name, hs.country
ORDER BY fire_count DESC
LIMIT 10;
```

## Performance Considerations

### Expected Runtime
- **Urban features**: Depends on data volume (batch processing every 1000 features)
- **Earthquake events**: ~1-5 minutes for 10,000+ events
- **Fire events**: ~1-5 minutes for 10,000+ events
- **Flood zones**: <1 minute (typically fewer records)

### Optimization Tips

1. **Batch Processing**: Large datasets processed in batches to avoid memory issues
2. **Spatial Indices**: Ensure PostGIS spatial indices exist (created in Phase 2)
3. **Projection Overhead**: Minimize CRS transformations by doing all calculations in EPSG:3035
4. **Parallel Processing**: For large datasets, consider splitting by country/region

### Memory Usage

- **Typical**: 500-1000 MB RAM for ~500 sites with moderate hazard data
- **Large datasets**: Consider batch size reduction if memory issues occur

## Troubleshooting

### Issue: Database Connection Error
```
psycopg2.OperationalError: connection to server at "localhost" ... failed
```

**Solution:**
1. Ensure PostgreSQL is running: `sudo systemctl status postgresql`
2. Check `.env` file has correct credentials
3. Test connection: `psql -U postgres -d unesco_risk -c "SELECT 1"`

### Issue: No Data Found in Tables
```
WARNING: No urban features found in database
```

**Solution:**
1. Run Phase 3-4 ETL modules first to populate data
2. Verify tables: `SELECT COUNT(*) FROM unesco_risk.heritage_sites`

### Issue: CRS Validation Failed
```
ERROR: CRS transformation validation FAILED
```

**Solution:**
1. Check GeoPandas and pyproj installation
2. Verify EPSG:3035 projection is available
3. Re-run validation independently

### Issue: Slow Performance
```
Takes > 30 minutes to complete
```

**Solution:**
1. Reduce batch size in update functions
2. Check spatial indices exist: `\di unesco_risk.*`
3. Consider running hazard types in parallel (separate processes)

## Next Steps

After Phase 5 completion:

1. **Verify Results**: Run verification queries to ensure spatial joins worked
2. **Check Data Quality**: Spot-check distances for known sites
3. **Proceed to Phase 6**: Risk scoring engine can now use spatial relationships
4. **Update Documentation**: Mark Phase 5 complete in STATUS.md and PLAN.MD

## Expected Outcomes

Upon successful completion:

- ✅ All urban features linked to nearest heritage sites (within 5km)
- ✅ All earthquake events linked to nearest sites (within 50km)
- ✅ All fire events linked to nearest sites (within 25km)
- ✅ All flood zones linked to nearest sites (within 50km)
- ✅ Distance columns populated with accurate metric values
- ✅ CRS transformations validated for accuracy
- ✅ Database ready for Phase 6 (Risk Scoring)

## References

- [PLAN.MD Section 5](../PLAN.MD#5-crs-transformation--spatial-join) — Detailed technical specifications
- [GeoPandas Documentation](https://geopandas.org/) — Spatial operations
- [PostGIS Manual](https://postgis.net/docs/) — Spatial database functions
- [EPSG:3035 Specification](https://epsg.io/3035) — ETRS89/LAEA Europe CRS

---

**Last Updated:** February 17, 2026  
**Status:** ✅ Module Complete, Testing Complete  
**Next Phase:** Phase 6 - Risk Scoring Engine
