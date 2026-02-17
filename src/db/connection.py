"""
Database connection module for UNESCO Heritage Sites Risk Modeling.

Provides SQLAlchemy engine and session management with connection pooling.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from config.settings import DATABASE_URL

# SQLAlchemy declarative base
Base = declarative_base()

# Global engine instance (singleton pattern)
_engine = None
_SessionLocal = None


def get_engine():
    """
    Get or create the SQLAlchemy engine with connection pooling.
    
    Returns:
        sqlalchemy.engine.Engine: Database engine instance
    """
    global _engine
    
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,   # Recycle connections after 1 hour
            echo=False,          # Set to True for SQL debugging
        )
    
    return _engine


def get_session():
    """
    Get a new database session.
    
    Returns:
        sqlalchemy.orm.Session: Database session
        
    Usage:
        session = get_session()
        try:
            # Your database operations here
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    """
    global _SessionLocal
    
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    
    return _SessionLocal()


def create_tables():
    """
    Create all tables defined in the ORM models.
    This is an alternative to running SQL scripts manually.
    """
    from src.db import models  # Import here to avoid circular imports
    engine = get_engine()
    Base.metadata.create_all(engine)


def drop_tables():
    """
    Drop all tables defined in the ORM models.
    WARNING: This will delete all data!
    """
    from src.db import models  # Import here to avoid circular imports
    engine = get_engine()
    Base.metadata.drop_all(engine)


def test_connection():
    """
    Test the database connection by executing a simple query.
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute("SELECT PostGIS_Version();")
            version = result.scalar()
            print(f"✓ Database connection successful!")
            print(f"✓ PostGIS version: {version}")
            return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False
