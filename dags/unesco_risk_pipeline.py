"""
UNESCO Heritage Sites Risk Modeling - Airflow DAG Pipeline
Phase 9: Complete ETL and Analysis Pipeline Orchestration

This DAG orchestrates the entire risk modeling pipeline:
1. Fetch UNESCO sites
2. Data ingestion (OSM, climate, earthquake, fire, flood/elevation) - parallel
3. Spatial joins
4. Risk score calculation
5. Anomaly detection
6. Map visualization generation

Schedule: Weekly on Sundays at 2 AM UTC
Estimated runtime: ~3 hours (OSM is the bottleneck at ~42 min for 500 sites)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# CALLABLE WRAPPER FUNCTIONS (Phase 9.1)
# ============================================================================

def fetch_unesco_callable(**context):
    """Wrapper for UNESCO sites ETL."""
    from src.etl.fetch_unesco import fetch_unesco_sites
    
    print("=" * 60)
    print("TASK: Fetch UNESCO Heritage Sites")
    print("=" * 60)
    
    try:
        gdf = fetch_unesco_sites(
            europe_only=True,  # Only European sites
            dry_run=False,
            use_json=False
        )
        
        if gdf is not None:
            site_count = len(gdf)
            print(f"✓ Successfully fetched and stored {site_count} UNESCO sites")
            # Push site count to XCom for monitoring
            context['ti'].xcom_push(key='site_count', value=site_count)
            return site_count
        else:
            raise Exception("UNESCO fetch returned None")
            
    except Exception as e:
        print(f"✗ Error fetching UNESCO sites: {e}")
        raise


def fetch_osm_callable(**context):
    """Wrapper for OSM urban features ETL."""
    from src.db.connection import get_session
    from src.etl.fetch_osm import fetch_all_osm
    
    print("=" * 60)
    print("TASK: Fetch OSM Urban Features")
    print("=" * 60)
    
    session = get_session()
    
    try:
        stats = fetch_all_osm(
            session=session,
            test_mode=False,  # Full run, not test mode
            limit=None,
            verbose=True
        )
        
        print(f"✓ OSM ETL completed: {stats['total_features']} features collected")
        context['ti'].xcom_push(key='osm_features', value=stats['total_features'])
        return stats['total_features']
        
    except Exception as e:
        print(f"✗ Error fetching OSM data: {e}")
        raise
    finally:
        session.close()


def fetch_climate_callable(**context):
    """Wrapper for climate data ETL."""
    from src.db.connection import get_session
    from src.etl.fetch_climate import fetch_all_climate_data
    
    print("=" * 60)
    print("TASK: Fetch Climate Data")
    print("=" * 60)
    
    session = get_session()
    
    try:
        count = fetch_all_climate_data(
            session=session,
            source='both',  # Open-Meteo + NASA POWER
            test_mode=False,
            verbose=True
        )
        
        print(f"✓ Climate ETL completed: {count} climate records")
        context['ti'].xcom_push(key='climate_records', value=count)
        return count
        
    except Exception as e:
        print(f"✗ Error fetching climate data: {e}")
        raise
    finally:
        session.close()


def fetch_earthquake_callable(**context):
    """Wrapper for earthquake data ETL."""
    from src.db.connection import get_session
    from src.etl.fetch_earthquake import fetch_all_earthquakes
    
    print("=" * 60)
    print("TASK: Fetch Earthquake Data")
    print("=" * 60)
    
    session = get_session()
    
    try:
        count = fetch_all_earthquakes(
            session=session,
            min_magnitude=3.0,
            start_date='2015-01-01',
            end_date=datetime.now().strftime('%Y-%m-%d'),
            verbose=True
        )
        
        print(f"✓ Earthquake ETL completed: {count} earthquake events")
        context['ti'].xcom_push(key='earthquake_events', value=count)
        return count
        
    except Exception as e:
        print(f"✗ Error fetching earthquake data: {e}")
        raise
    finally:
        session.close()


def fetch_fire_callable(**context):
    """Wrapper for fire data ETL."""
    from src.db.connection import get_session
    from src.etl.fetch_fire import fetch_fire_data
    
    print("=" * 60)
    print("TASK: Fetch Fire Data")
    print("=" * 60)
    
    session = get_session()
    
    try:
        count = fetch_fire_data(
            session=session,
            days=5,  # Last 5 days (FIRMS API limit)
            source='VIIRS_SNPP_NRT',
            verbose=True
        )
        
        print(f"✓ Fire ETL completed: {count} fire detections")
        context['ti'].xcom_push(key='fire_detections', value=count)
        return count
        
    except Exception as e:
        print(f"✗ Error fetching fire data: {e}")
        raise
    finally:
        session.close()


def fetch_flood_elevation_callable(**context):
    """Wrapper for flood and elevation data ETL."""
    from src.db.connection import get_session
    from src.etl.fetch_elevation import fetch_all_elevations
    from src.etl.fetch_flood import fetch_flood_data
    
    print("=" * 60)
    print("TASK: Fetch Flood and Elevation Data")
    print("=" * 60)
    
    session = get_session()
    
    try:
        # Elevation data first
        elev_count = fetch_all_elevations(
            session=session,
            test_mode=False,
            verbose=True
        )
        print(f"✓ Elevation data: {elev_count} sites updated")
        
        # Flood data (may use placeholder mode if GFMS unavailable)
        flood_count = fetch_flood_data(
            session=session,
            use_placeholder=True,  # GFMS requires manual download
            verbose=True
        )
        print(f"✓ Flood data: {flood_count} records")
        
        total = elev_count + flood_count
        context['ti'].xcom_push(key='flood_elevation_records', value=total)
        return total
        
    except Exception as e:
        print(f"✗ Error fetching flood/elevation data: {e}")
        raise
    finally:
        session.close()


def spatial_join_callable(**context):
    """Wrapper for spatial join operations."""
    from src.etl.spatial_join import run_full_spatial_join
    
    print("=" * 60)
    print("TASK: Spatial Join")
    print("=" * 60)
    
    try:
        run_full_spatial_join(
            verbose=True,
            dry_run=False
        )
        
        print("✓ Spatial join completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Error in spatial join: {e}")
        raise


def calculate_risk_scores_callable(**context):
    """Wrapper for risk score calculation."""
    from src.analysis.risk_scoring import calculate_all_risk_scores
    
    print("=" * 60)
    print("TASK: Calculate Risk Scores")
    print("=" * 60)
    
    try:
        scores_df = calculate_all_risk_scores()
        
        site_count = len(scores_df)
        risk_distribution = scores_df['risk_level'].value_counts().to_dict()
        
        print(f"✓ Risk scores calculated for {site_count} sites")
        print(f"  Risk distribution: {risk_distribution}")
        
        context['ti'].xcom_push(key='risk_scores_count', value=site_count)
        context['ti'].xcom_push(key='risk_distribution', value=risk_distribution)
        
        return site_count
        
    except Exception as e:
        print(f"✗ Error calculating risk scores: {e}")
        raise


def anomaly_detection_callable(**context):
    """Wrapper for anomaly detection."""
    from src.analysis.anomaly_detection import detect_risk_anomalies
    
    print("=" * 60)
    print("TASK: Anomaly Detection")
    print("=" * 60)
    
    try:
        result = detect_risk_anomalies(
            contamination=0.1,
            dry_run=False,
            verbose=True
        )
        
        anomaly_count = result['anomaly_count']
        total_sites = result['total_sites']
        
        print(f"✓ Anomaly detection completed")
        print(f"  Detected {anomaly_count}/{total_sites} anomalous sites ({anomaly_count/total_sites*100:.1f}%)")
        
        context['ti'].xcom_push(key='anomaly_count', value=anomaly_count)
        
        return anomaly_count
        
    except Exception as e:
        print(f"✗ Error in anomaly detection: {e}")
        raise


def generate_map_callable(**context):
    """Wrapper for Folium map generation."""
    from src.visualization.folium_map_legacy import generate_risk_map
    
    print("=" * 60)
    print("TASK: Generate Risk Map")
    print("=" * 60)
    
    try:
        output_path = generate_risk_map(
            output_path='output/maps/europe_risk_map.html'
        )
        
        print(f"✓ Interactive map generated: {output_path}")
        
        return output_path
        
    except Exception as e:
        print(f"✗ Error generating map: {e}")
        raise


# ============================================================================
# DAG DEFINITION (Phase 9.2)
# ============================================================================

# Default arguments for all tasks
default_args = {
    'owner': 'unesco-risk-team',
    'depends_on_past': False,
    'start_date': datetime(2026, 2, 17),
    'email': ['alerts@example.com'],
    'email_on_failure': False,  # Set to True if SMTP configured
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=4),  # Overall DAG timeout
}

# Create DAG
dag = DAG(
    'unesco_risk_pipeline',
    default_args=default_args,
    description='UNESCO Heritage Sites Risk Modeling Pipeline',
    schedule_interval='0 2 * * 0',  # Weekly on Sundays at 2 AM UTC
    catchup=False,
    max_active_runs=1,  # Only one run at a time
    tags=['unesco', 'risk-modeling', 'etl', 'geospatial'],
)


# ============================================================================
# TASK DEFINITIONS
# ============================================================================

# Phase 9.3: Fetch UNESCO Sites (Foundation task)
fetch_sites = PythonOperator(
    task_id='fetch_unesco_sites',
    python_callable=fetch_unesco_callable,
    execution_timeout=timedelta(minutes=15),
    dag=dag,
)

# Phase 9.4: Data Ingestion TaskGroup (5 parallel tasks)
with TaskGroup('data_ingestion', tooltip='Parallel data ingestion from 5 sources', dag=dag) as data_ingestion:
    
    # 4A: OSM Urban Features (longest runtime ~42 min)
    fetch_osm = PythonOperator(
        task_id='fetch_osm_urban_features',
        python_callable=fetch_osm_callable,
        execution_timeout=timedelta(hours=2),  # Extended timeout for OSM
    )
    
    # 4B: Climate Data
    fetch_climate = PythonOperator(
        task_id='fetch_climate_data',
        python_callable=fetch_climate_callable,
        execution_timeout=timedelta(minutes=60),
    )
    
    # 4C: Earthquake Data
    fetch_earthquake = PythonOperator(
        task_id='fetch_earthquake_data',
        python_callable=fetch_earthquake_callable,
        execution_timeout=timedelta(minutes=30),
    )
    
    # 4D: Fire Data
    fetch_fire = PythonOperator(
        task_id='fetch_fire_data',
        python_callable=fetch_fire_callable,
        execution_timeout=timedelta(minutes=20),
    )
    
    # 4E: Flood & Elevation Data
    fetch_flood_elevation = PythonOperator(
        task_id='fetch_flood_elevation_data',
        python_callable=fetch_flood_elevation_callable,
        execution_timeout=timedelta(minutes=45),
    )

# Phase 9.5: Spatial Join
spatial_join = PythonOperator(
    task_id='spatial_join',
    python_callable=spatial_join_callable,
    execution_timeout=timedelta(minutes=30),
    dag=dag,
)

# Phase 9.6: Calculate Risk Scores
calculate_risk_scores = PythonOperator(
    task_id='calculate_risk_scores',
    python_callable=calculate_risk_scores_callable,
    execution_timeout=timedelta(minutes=20),
    dag=dag,
)

# Phase 9.7: Anomaly Detection
anomaly_detection = PythonOperator(
    task_id='anomaly_detection',
    python_callable=anomaly_detection_callable,
    execution_timeout=timedelta(minutes=10),
    dag=dag,
)

# Phase 9.8: Generate Folium Map
generate_map = PythonOperator(
    task_id='generate_folium_map',
    python_callable=generate_map_callable,
    execution_timeout=timedelta(minutes=10),
    dag=dag,
)


# ============================================================================
# TASK DEPENDENCIES (Phase 9.9)
# ============================================================================

# Pipeline flow:
# fetch_sites → data_ingestion (parallel group) → spatial_join → 
# calculate_risk_scores → anomaly_detection → generate_map

fetch_sites >> data_ingestion >> spatial_join >> calculate_risk_scores >> anomaly_detection >> generate_map

# Critical path:
# fetch_sites → fetch_osm (longest) → spatial_join → risk_scores → anomaly → viz
# Total estimated: 15min + 120min + 30min + 20min + 10min + 10min = ~205 min (~3.4 hours)
