# Phase 6 & 7: Risk Scoring and Anomaly Detection

## Overview

This guide documents the implementation of Phase 6 (Risk Scoring Engine) and Phase 7 (Anomaly Detection & Density Analysis) for the UNESCO Heritage Sites Risk Modeling project.

## Phase 6: Risk Scoring Engine

### Features

The risk scoring engine computes 6 sub-scores for each heritage site:

1. **Urban Density Score** — Based on building count and footprint area within 5km
2. **Climate Anomaly Score** — Z-score analysis of extreme temperature and precipitation events
3. **Seismic Risk Score** — Gutenberg-Richter energy formula for earthquakes within 50km
4. **Fire Risk Score** — Fire radiative power weighted by confidence and distance (25km)
5. **Flood Risk Score** — GFMS pixel values and historical flood frequency (50km)
6. **Coastal Risk Score** — Elevation-based risk for coastal sites (< 50km from coast)

All scores are normalized to [0, 1] using Min-Max scaling and combined into a composite risk score using weighted averaging.

### Risk Levels

- **Low**: 0.00 - 0.25
- **Medium**: 0.25 - 0.50
- **High**: 0.50 - 0.75
- **Critical**: 0.75 - 1.00

### Default Risk Weights

```python
RISK_WEIGHTS = {
    "urban_density": 0.25,    # 25%
    "climate_anomaly": 0.20,  # 20%
    "seismic_risk": 0.20,     # 20%
    "fire_risk": 0.15,        # 15%
    "flood_risk": 0.10,       # 10%
    "coastal_risk": 0.10,     # 10%
}
# Total = 100%
```

### Usage

#### Basic Usage

```bash
# Calculate all risk scores and save to database
python -m src.analysis.risk_scoring

# Dry-run mode (calculate without saving)
python -m src.analysis.risk_scoring --dry-run

# Verbose logging
python -m src.analysis.risk_scoring --verbose
```

#### Programmatic Usage

```python
from src.analysis.risk_scoring import calculate_all_risk_scores

# Calculate all risk scores
scores_df = calculate_all_risk_scores()

# View results
print(scores_df[['site_id', 'composite_risk_score', 'risk_level']].head(10))
```

### Database Queries

```sql
-- Check total number of scored sites
SELECT COUNT(*) FROM unesco_risk.risk_scores;

-- Risk level distribution
SELECT risk_level, COUNT(*) 
FROM unesco_risk.risk_scores 
GROUP BY risk_level 
ORDER BY risk_level;

-- Top 10 highest risk sites
SELECT 
    hs.name, 
    hs.country,
    rs.composite_risk_score,
    rs.risk_level,
    rs.urban_density_score,
    rs.seismic_risk_score,
    rs.fire_risk_score
FROM unesco_risk.heritage_sites hs
JOIN unesco_risk.risk_scores rs ON hs.id = rs.site_id
ORDER BY rs.composite_risk_score DESC
LIMIT 10;

-- Sites by specific risk component (e.g., high seismic risk)
SELECT 
    hs.name,
    hs.country,
    rs.seismic_risk_score
FROM unesco_risk.heritage_sites hs
JOIN unesco_risk.risk_scores rs ON hs.id = rs.site_id
WHERE rs.seismic_risk_score > 0.7
ORDER BY rs.seismic_risk_score DESC;
```

## Phase 7: Anomaly Detection & Density Analysis

### 7A: Anomaly Detection (Isolation Forest)

#### Features

- **Multi-dimensional outlier detection** using Isolation Forest algorithm
- **Automatic risk level override** for anomalies → "critical"
- **Configurable contamination rate** (default: 10%)
- **Reproducible results** with fixed random state

#### Algorithm Parameters

```python
n_estimators = 200        # Number of trees in the forest
contamination = 0.1       # Expected proportion of anomalies (10%)
random_state = 42         # For reproducibility
n_jobs = -1              # Use all CPU cores
```

#### Usage

```bash
# Run anomaly detection
python -m src.analysis.anomaly_detection

# Dry-run mode
python -m src.analysis.anomaly_detection --dry-run

# Custom contamination rate
python -m src.analysis.anomaly_detection --contamination 0.15

# Verbose logging
python -m src.analysis.anomaly_detection --verbose
```

#### Programmatic Usage

```python
from src.analysis.anomaly_detection import run_anomaly_detection

# Run anomaly detection pipeline
scores_df = run_anomaly_detection()

# View anomalies
anomalies = scores_df[scores_df['is_anomaly']]
print(f"Detected {len(anomalies)} anomalous sites")
```

#### Database Queries

```sql
-- Count anomalies
SELECT COUNT(*) 
FROM unesco_risk.risk_scores 
WHERE is_anomaly = TRUE;

-- List all anomalous sites
SELECT 
    hs.name,
    hs.country,
    rs.isolation_forest_score,
    rs.composite_risk_score,
    rs.risk_level
FROM unesco_risk.heritage_sites hs
JOIN unesco_risk.risk_scores rs ON hs.id = rs.site_id
WHERE rs.is_anomaly = TRUE
ORDER BY rs.isolation_forest_score ASC
LIMIT 20;

-- Anomalies by country
SELECT 
    hs.country,
    COUNT(*) as anomaly_count
FROM unesco_risk.heritage_sites hs
JOIN unesco_risk.risk_scores rs ON hs.id = rs.site_id
WHERE rs.is_anomaly = TRUE
GROUP BY hs.country
ORDER BY anomaly_count DESC;
```

### 7B: Urban Density Analysis (KDE)

#### Features

- **Kernel Density Estimation** for urban feature clustering
- **Gaussian kernel** with 1000m bandwidth
- **EPSG:3035 projection** for accurate metric distances
- **Site-level density summaries** (avg, max, stddev)

#### KDE Parameters

```python
bandwidth = 1000.0    # meters in EPSG:3035
kernel = 'gaussian'   # Gaussian kernel
```

#### Usage

```bash
# Run urban density analysis
python -m src.analysis.density_analysis

# Dry-run mode
python -m src.analysis.density_analysis --dry-run

# Custom bandwidth
python -m src.analysis.density_analysis --bandwidth 500

# Verbose logging
python -m src.analysis.density_analysis --verbose
```

#### Programmatic Usage

```python
from src.analysis.density_analysis import run_density_analysis

# Run density analysis pipeline
urban_df, site_summary_df = run_density_analysis()

# View top density sites
print(site_summary_df.nlargest(10, 'avg_density'))
```

#### Database Queries

```sql
-- Check density score coverage
SELECT COUNT(*) 
FROM unesco_risk.urban_features 
WHERE density_score IS NOT NULL;

-- Top urban features by density
SELECT 
    id,
    feature_type,
    density_score,
    nearest_site_id
FROM unesco_risk.urban_features
WHERE density_score IS NOT NULL
ORDER BY density_score DESC
LIMIT 20;

-- Site-level density summary
SELECT 
    hs.id,
    hs.name,
    COUNT(uf.id) as feature_count,
    AVG(uf.density_score) as avg_density,
    MAX(uf.density_score) as max_density
FROM unesco_risk.heritage_sites hs
LEFT JOIN unesco_risk.urban_features uf 
    ON uf.nearest_site_id = hs.id 
    AND uf.density_score IS NOT NULL
GROUP BY hs.id, hs.name
HAVING COUNT(uf.id) > 0
ORDER BY avg_density DESC
LIMIT 10;
```

## Testing

### Unit Tests

All modules have comprehensive unit test coverage:

```bash
# Test risk scoring
python -m unittest tests.test_risk_scoring -v
# Result: 8/8 tests passed

# Test anomaly detection
python -m unittest tests.test_anomaly_detection -v
# Result: 8/8 tests passed

# Run all tests
python -m unittest discover tests -v
```

### Test Coverage

- **Risk Scoring**: 
  - Weight validation
  - Composite score calculation
  - Risk level assignment
  - NaN handling
  - Edge cases (all 0s, all 1s)

- **Anomaly Detection**:
  - Feature matrix preparation
  - Isolation Forest training
  - Anomaly score properties
  - Reproducibility
  - Contamination parameter

## Integration Workflow

### Complete Pipeline (Phases 0-7)

```bash
# 1. Setup database (Phase 0-2)
createdb -U postgres unesco_risk
psql -U postgres -d unesco_risk -c "CREATE EXTENSION postgis;"
psql -U postgres -d unesco_risk -f sql/01_create_schema.sql
psql -U postgres -d unesco_risk -f sql/02_create_tables.sql
psql -U postgres -d unesco_risk -f sql/03_create_indices.sql

# 2. Fetch UNESCO sites (Phase 3)
python -m src.etl.fetch_unesco

# 3. Fetch hazard data (Phase 4)
python -m src.etl.fetch_osm          # Urban features
python -m src.etl.fetch_climate      # Climate data
python -m src.etl.fetch_earthquake   # Seismic data
python -m src.etl.fetch_fire         # Fire events
python -m src.etl.fetch_elevation    # Elevation data

# 4. Spatial join (Phase 5)
python -m src.etl.spatial_join

# 5. Calculate risk scores (Phase 6)
python -m src.analysis.risk_scoring

# 6. Detect anomalies (Phase 7A)
python -m src.analysis.anomaly_detection

# 7. Compute urban density (Phase 7B)
python -m src.analysis.density_analysis
```

## Configuration

All parameters can be customized in `config/settings.py`:

```python
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
```

## Performance Considerations

- **Risk Scoring**: Processes ~500 sites in < 10 seconds
- **Anomaly Detection**: Trains model in ~1-2 seconds (200 estimators)
- **Density Analysis**: Computes KDE for ~50k urban features in ~5 seconds
- **Memory Usage**: < 500 MB for typical dataset

## Common Issues & Solutions

### Issue: "No risk scores found"
**Solution**: Run risk_scoring.py before anomaly_detection.py

### Issue: "Missing feature columns"
**Solution**: Ensure all ETL phases (0-5) completed successfully

### Issue: "All scores are 0"
**Solution**: Verify spatial join completed and hazard data exists

### Issue: "Database connection error"
**Solution**: Check .env file and database credentials

## Next Steps

After completing Phase 6 & 7, proceed to:

- **Phase 8**: Folium Visualization — Create interactive risk maps
- **Phase 9**: Airflow DAG Integration — Automate the entire pipeline
- **Phase 10**: Testing & Quality Assurance — Comprehensive testing

## References

- Isolation Forest: Liu, F.T., Ting, K.M. and Zhou, Z.H., 2008. "Isolation forest." In ICDM.
- Kernel Density Estimation: Silverman, B.W., 1986. "Density estimation for statistics and data analysis."
- Risk Scoring: Multi-criteria decision analysis (MCDA) weighted sum method

## Support

For issues or questions:
1. Check STATUS.md for implementation details
2. Review test cases in tests/test_risk_scoring.py and tests/test_anomaly_detection.py
3. Consult PLAN.MD for technical specifications
4. Open a GitHub issue with detailed error messages

---

**Last Updated**: February 17, 2026  
**Status**: Phase 6 & 7 Complete ✅  
**Next Phase**: Phase 8 — Folium Visualization
