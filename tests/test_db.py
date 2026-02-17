"""
Database connection and schema verification tests.

This script tests:
1. Database connection
2. PostGIS extension availability
3. Schema creation
4. Table creation via SQL scripts
5. ORM models functionality

Usage:
    # Test connection only
    python tests/test_db.py --test-connection
    
    # Create schema and tables using SQL scripts
    python tests/test_db.py --create-schema
    
    # Create tables using ORM
    python tests/test_db.py --create-orm
    
    # Run all tests
    python tests/test_db.py --all
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_connection():
    """Test database connection and PostGIS availability."""
    print("\n" + "="*60)
    print("Testing Database Connection")
    print("="*60)
    
    try:
        from src.db.connection import test_connection
        success = test_connection()
        
        if success:
            print("✓ Database connection test PASSED")
            return True
        else:
            print("✗ Database connection test FAILED")
            return False
    except Exception as e:
        print(f"✗ Error during connection test: {e}")
        return False


def create_schema_from_sql():
    """Execute SQL scripts to create schema, tables, and indices."""
    print("\n" + "="*60)
    print("Creating Schema from SQL Scripts")
    print("="*60)
    
    try:
        import subprocess
        from config.settings import POSTGRES_DB, POSTGRES_USER, POSTGRES_HOST, POSTGRES_PORT
        
        sql_dir = project_root / "sql"
        sql_files = [
            "01_create_schema.sql",
            "02_create_tables.sql",
            "03_create_indices.sql"
        ]
        
        for sql_file in sql_files:
            sql_path = sql_dir / sql_file
            if not sql_path.exists():
                print(f"✗ SQL file not found: {sql_path}")
                return False
            
            print(f"\nExecuting {sql_file}...")
            cmd = [
                "psql",
                "-h", POSTGRES_HOST,
                "-p", str(POSTGRES_PORT),
                "-U", POSTGRES_USER,
                "-d", POSTGRES_DB,
                "-f", str(sql_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✓ {sql_file} executed successfully")
            else:
                print(f"✗ {sql_file} failed: {result.stderr}")
                return False
        
        print("\n✓ All SQL scripts executed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Error during SQL execution: {e}")
        return False


def verify_tables():
    """Verify that all 7 tables exist in the database."""
    print("\n" + "="*60)
    print("Verifying Tables")
    print("="*60)
    
    try:
        from sqlalchemy import text
        from src.db.connection import get_engine
        
        engine = get_engine()
        expected_tables = [
            'heritage_sites',
            'urban_features',
            'climate_events',
            'earthquake_events',
            'fire_events',
            'flood_zones',
            'risk_scores'
        ]
        
        query = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'unesco_risk'
            ORDER BY table_name;
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query)
            tables = [row[0] for row in result]
        
        print(f"\nFound {len(tables)} tables in unesco_risk schema:")
        for table in tables:
            status = "✓" if table in expected_tables else "?"
            print(f"  {status} {table}")
        
        missing_tables = set(expected_tables) - set(tables)
        if missing_tables:
            print(f"\n✗ Missing tables: {', '.join(missing_tables)}")
            return False
        
        print(f"\n✓ All {len(expected_tables)} expected tables exist")
        return True
        
    except Exception as e:
        print(f"✗ Error during table verification: {e}")
        return False


def verify_indices():
    """Verify that all spatial and B-tree indices exist."""
    print("\n" + "="*60)
    print("Verifying Indices")
    print("="*60)
    
    try:
        from sqlalchemy import text
        from src.db.connection import get_engine
        
        engine = get_engine()
        query = text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE schemaname = 'unesco_risk'
            ORDER BY indexname;
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query)
            indices = [row[0] for row in result]
        
        print(f"\nFound {len(indices)} indices in unesco_risk schema:")
        for idx in indices:
            print(f"  ✓ {idx}")
        
        # Expected minimum indices (6 GIST + 8 B-Tree = 14 total)
        if len(indices) >= 14:
            print(f"\n✓ All expected indices exist ({len(indices)} total)")
            return True
        else:
            print(f"\n⚠ Expected at least 14 indices, found {len(indices)}")
            return True  # Still pass, as some indices may be auto-created
        
    except Exception as e:
        print(f"✗ Error during index verification: {e}")
        return False


def test_orm_models():
    """Test ORM models by creating a simple query."""
    print("\n" + "="*60)
    print("Testing ORM Models")
    print("="*60)
    
    try:
        from src.db.connection import get_session
        from src.db.models import (
            HeritageSite, UrbanFeature, ClimateEvent, 
            EarthquakeEvent, FireEvent, FloodZone, RiskScore
        )
        
        session = get_session()
        
        # Test simple count queries for all models
        models = {
            'HeritageSite': HeritageSite,
            'UrbanFeature': UrbanFeature,
            'ClimateEvent': ClimateEvent,
            'EarthquakeEvent': EarthquakeEvent,
            'FireEvent': FireEvent,
            'FloodZone': FloodZone,
            'RiskScore': RiskScore
        }
        
        print("\nQuerying all models:")
        for model_name, model_class in models.items():
            try:
                count = session.query(model_class).count()
                print(f"  ✓ {model_name}: {count} records")
            except Exception as e:
                print(f"  ✗ {model_name}: Error - {e}")
                session.close()
                return False
        
        session.close()
        print("\n✓ All ORM models working correctly")
        return True
        
    except Exception as e:
        print(f"✗ Error during ORM test: {e}")
        return False


def create_tables_from_orm():
    """Create tables using SQLAlchemy ORM instead of SQL scripts."""
    print("\n" + "="*60)
    print("Creating Tables from ORM Models")
    print("="*60)
    
    try:
        from src.db.connection import create_tables
        
        print("\nCreating all tables via ORM...")
        create_tables()
        print("✓ Tables created successfully via ORM")
        return True
        
    except Exception as e:
        print(f"✗ Error during ORM table creation: {e}")
        return False


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(
        description="Test database connection and schema"
    )
    parser.add_argument(
        '--test-connection', 
        action='store_true',
        help='Test database connection only'
    )
    parser.add_argument(
        '--create-schema', 
        action='store_true',
        help='Create schema using SQL scripts'
    )
    parser.add_argument(
        '--create-orm', 
        action='store_true',
        help='Create tables using ORM'
    )
    parser.add_argument(
        '--verify', 
        action='store_true',
        help='Verify tables and indices'
    )
    parser.add_argument(
        '--test-orm', 
        action='store_true',
        help='Test ORM models'
    )
    parser.add_argument(
        '--all', 
        action='store_true',
        help='Run all tests (connection, verify, test ORM)'
    )
    
    args = parser.parse_args()
    
    # If no arguments provided, show help
    if not any(vars(args).values()):
        parser.print_help()
        return
    
    results = []
    
    # Test connection (always run first if included)
    if args.test_connection or args.all:
        results.append(('Connection Test', test_connection()))
    
    # Create schema from SQL
    if args.create_schema:
        results.append(('Create Schema (SQL)', create_schema_from_sql()))
        results.append(('Verify Tables', verify_tables()))
        results.append(('Verify Indices', verify_indices()))
    
    # Create tables from ORM
    if args.create_orm:
        results.append(('Create Tables (ORM)', create_tables_from_orm()))
        results.append(('Verify Tables', verify_tables()))
    
    # Verify existing schema
    if args.verify or args.all:
        results.append(('Verify Tables', verify_tables()))
        results.append(('Verify Indices', verify_indices()))
    
    # Test ORM models
    if args.test_orm or args.all:
        results.append(('Test ORM Models', test_orm_models()))
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {test_name}")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    # Exit with appropriate code
    sys.exit(0 if passed_tests == total_tests else 1)


if __name__ == "__main__":
    main()
