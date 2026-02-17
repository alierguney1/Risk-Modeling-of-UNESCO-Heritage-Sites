# Risk Modeling of UNESCO Heritage Sites

> **Multi-Source Spatial Data Analysis for European UNESCO World Heritage Sites**

A comprehensive risk assessment system that integrates climate data, seismic activity, urban sprawl, and environmental hazards to evaluate and visualize risks to UNESCO World Heritage Sites across Europe.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-blue.svg)](https://www.postgresql.org/)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.0+-green.svg)](https://postgis.net/)

## 📋 Project Overview

This project analyzes ~500+ UNESCO World Heritage Sites in Europe by combining multiple data sources:

- **UNESCO Sites**: Official World Heritage Centre data
- **Climate Data**: Open-Meteo & NASA POWER historical and forecast data
- **Seismic Activity**: USGS earthquake data
- **Fire Events**: NASA FIRMS fire detection
- **Urban Sprawl**: OpenStreetMap building and landuse data
- **Flood Risk**: GFMS flood monitoring
- **Elevation Data**: OpenTopography DEM

### Key Features

✅ **Automated ETL Pipeline** - Fetch and process data from 6+ external sources  
✅ **Spatial Analysis** - PostGIS-powered geographic computations  
✅ **Risk Scoring** - Multi-variate risk model with weighted factors  
✅ **Anomaly Detection** - Isolation Forest ML model for outlier identification  
✅ **Interactive Visualization** - Folium-based risk maps  
✅ **Workflow Orchestration** - Apache Airflow DAG for scheduling

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 14+ with PostGIS extension
- (Optional) Apache Airflow 2.8+ for scheduling

### Installation

```bash
# Clone the repository
git clone https://github.com/alierguney1/Risk-Modeling-of-UNESCO-Heritage-Sites.git
cd Risk-Modeling-of-UNESCO-Heritage-Sites

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database credentials
```

### Database Setup

```bash
# Create database
createdb -U postgres unesco_risk

# Enable PostGIS
psql -U postgres -d unesco_risk -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Run SQL schema files
psql -U postgres -d unesco_risk -f sql/01_create_schema.sql
psql -U postgres -d unesco_risk -f sql/02_create_tables.sql
psql -U postgres -d unesco_risk -f sql/03_create_indices.sql

# Test database connection
python -c "from src.db.connection import test_connection; test_connection()"
```

### Running the ETL Pipeline

```bash
# Fetch UNESCO heritage sites (Phase 3 - COMPLETED)
python -m src.etl.fetch_unesco --verbose

# Check results
psql -U postgres -d unesco_risk -c "SELECT COUNT(*) FROM unesco_risk.heritage_sites;"
```

## 📊 Current Status

**Phase 3 COMPLETED** ✅ - UNESCO Heritage Sites ETL

See [STATUS.md](./STATUS.md) for detailed progress tracking and testing instructions.

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ | Environment Setup |
| Phase 1 | ✅ | Project Scaffolding |
| Phase 2 | ✅ | Database Layer (PostGIS + ORM) |
| **Phase 3** | ✅ | **Core ETL: UNESCO Sites** |
| Phase 4 | ⬜ | ETL: Hazard & Environmental Data |
| Phase 5 | ⬜ | CRS Transformation & Spatial Join |
| Phase 6 | ⬜ | Risk Scoring Engine |
| Phase 7 | ⬜ | Anomaly Detection |
| Phase 8 | ⬜ | Folium Visualization |
| Phase 9 | ⬜ | Airflow DAG Integration |
| Phase 10 | ⬜ | Testing & QA |

## 📁 Project Structure

```
Risk-Modeling-of-UNESCO-Heritage-Sites/
├── config/              # Configuration files
│   └── settings.py      # Central configuration
├── sql/                 # Database schema files
│   ├── 01_create_schema.sql
│   ├── 02_create_tables.sql
│   └── 03_create_indices.sql
├── src/
│   ├── db/              # Database models and connection
│   │   ├── connection.py
│   │   └── models.py
│   ├── etl/             # Data extraction modules
│   │   └── fetch_unesco.py  ✅ Phase 3
│   ├── analysis/        # Risk scoring and analytics
│   └── visualization/   # Map generation
├── tests/               # Unit tests
│   ├── test_db.py
│   └── test_unesco_etl.py  ✅ Phase 3
├── STATUS.md           # Detailed status tracking
├── PLAN.MD             # Technical architecture plan
└── README.md           # This file
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_unesco_etl.py -v

# Run with coverage
pytest --cov=src tests/
```

## 📖 Documentation

- **[STATUS.md](./STATUS.md)** - Application status tracking with test commands (Turkish/English)
- **[PLAN.MD](./PLAN.MD)** - Detailed technical architecture and implementation plan
- **[.env.example](./.env.example)** - Environment variables template

## 🛠 Technology Stack

- **Backend**: Python 3.10+, SQLAlchemy, GeoAlchemy2
- **Database**: PostgreSQL 14+, PostGIS 3.0+
- **Geospatial**: GeoPandas, Shapely, PyProj, OSMnx
- **Visualization**: Folium
- **ML**: Scikit-learn (Isolation Forest)
- **Orchestration**: Apache Airflow
- **Testing**: pytest

## 🔐 Security

- No hardcoded credentials (uses .env)
- SQL injection prevention via ORM
- CodeQL security scanning: ✅ No vulnerabilities

## 📝 License

This project is open source. See LICENSE file for details.

## 👥 Contributing

Contributions are welcome! Please see [STATUS.md](./STATUS.md) for current development priorities.

## 📧 Contact

For questions or issues, please open a GitHub issue.

---

**Last Updated**: February 17, 2026  
**Current Phase**: Phase 3 Complete - UNESCO Heritage Sites ETL
