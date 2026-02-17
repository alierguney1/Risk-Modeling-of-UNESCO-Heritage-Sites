"""
SQLAlchemy ORM models for UNESCO Heritage Sites Risk Modeling.

All models mirror the PostGIS database schema with GeoAlchemy2 for spatial columns.
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, Time,
    ForeignKey, CheckConstraint, UniqueConstraint, text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry

from src.db.connection import Base


class HeritageSite(Base):
    """UNESCO Heritage Sites table - stores all European heritage sites."""
    
    __tablename__ = 'heritage_sites'
    __table_args__ = {'schema': 'unesco_risk'}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    whc_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(500), nullable=False)
    category = Column(String(20), CheckConstraint("category IN ('Cultural', 'Natural', 'Mixed')"))
    date_inscribed = Column(Integer)
    country = Column(String(200))
    iso_code = Column(String(20))
    region = Column(String(100))
    criteria = Column(String(100))
    in_danger = Column(Boolean, default=False)
    area_hectares = Column(Float)
    description = Column(String)
    geom = Column(Geometry('POINT', srid=4326), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    climate_events = relationship("ClimateEvent", back_populates="site")
    risk_score = relationship("RiskScore", back_populates="site", uselist=False)
    
    def __repr__(self):
        return f"<HeritageSite(whc_id={self.whc_id}, name='{self.name}')>"


class UrbanFeature(Base):
    """OSM Urban Features table - stores building and landuse data near heritage sites."""
    
    __tablename__ = 'urban_features'
    __table_args__ = {'schema': 'unesco_risk'}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    osm_id = Column(Integer)
    osm_type = Column(String(10))
    feature_type = Column(String(50), nullable=False)
    feature_value = Column(String(100))
    name = Column(String(500))
    nearest_site_id = Column(Integer, ForeignKey('unesco_risk.heritage_sites.id'))
    distance_to_site_m = Column(Float)
    geom = Column(Geometry('GEOMETRY', srid=4326), nullable=False)
    fetched_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<UrbanFeature(id={self.id}, type='{self.feature_type}', value='{self.feature_value}')>"


class ClimateEvent(Base):
    """Climate Events table - stores climate time-series data from Open-Meteo and NASA POWER."""
    
    __tablename__ = 'climate_events'
    __table_args__ = (
        UniqueConstraint('site_id', 'event_date', 'source', name='uq_climate_site_date_source'),
        {'schema': 'unesco_risk'}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(Integer, ForeignKey('unesco_risk.heritage_sites.id'), nullable=False)
    event_date = Column(Date, nullable=False)
    source = Column(String(20), CheckConstraint("source IN ('open_meteo', 'nasa_power')"))
    temp_max_c = Column(Float)
    temp_min_c = Column(Float)
    temp_mean_c = Column(Float)
    precipitation_mm = Column(Float)
    wind_max_ms = Column(Float)
    wind_gust_ms = Column(Float)
    solar_radiation_kwh = Column(Float)
    humidity_pct = Column(Float)
    geom = Column(Geometry('POINT', srid=4326))
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    site = relationship("HeritageSite", back_populates="climate_events")
    
    def __repr__(self):
        return f"<ClimateEvent(site_id={self.site_id}, date={self.event_date}, source='{self.source}')>"


class EarthquakeEvent(Base):
    """Earthquake Events table - stores USGS earthquake data."""
    
    __tablename__ = 'earthquake_events'
    __table_args__ = {'schema': 'unesco_risk'}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usgs_id = Column(String(50), unique=True, nullable=False)
    magnitude = Column(Float, nullable=False)
    mag_type = Column(String(10))
    depth_km = Column(Float)
    place_desc = Column(String(300))
    event_time = Column(DateTime, nullable=False)
    significance = Column(Integer)
    mmi = Column(Float)
    alert_level = Column(String(10))
    tsunami = Column(Boolean, default=False)
    nearest_site_id = Column(Integer, ForeignKey('unesco_risk.heritage_sites.id'))
    distance_to_site_km = Column(Float)
    geom = Column(Geometry('POINT', srid=4326), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<EarthquakeEvent(usgs_id='{self.usgs_id}', magnitude={self.magnitude})>"


class FireEvent(Base):
    """Fire Events table - stores NASA FIRMS fire detection data."""
    
    __tablename__ = 'fire_events'
    __table_args__ = {'schema': 'unesco_risk'}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    satellite = Column(String(20))
    brightness = Column(Float)
    confidence = Column(Integer)
    frp = Column(Float)
    acq_date = Column(Date, nullable=False)
    acq_time = Column(Time)
    day_night = Column(String(1))
    nearest_site_id = Column(Integer, ForeignKey('unesco_risk.heritage_sites.id'))
    distance_to_site_km = Column(Float)
    geom = Column(Geometry('POINT', srid=4326), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<FireEvent(id={self.id}, date={self.acq_date}, brightness={self.brightness})>"


class FloodZone(Base):
    """Flood Zones table - stores GFMS flood data."""
    
    __tablename__ = 'flood_zones'
    __table_args__ = {'schema': 'unesco_risk'}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_date = Column(Date)
    flood_intensity = Column(Float)
    nearest_site_id = Column(Integer, ForeignKey('unesco_risk.heritage_sites.id'))
    distance_to_site_km = Column(Float)
    geom = Column(Geometry('POINT', srid=4326))
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<FloodZone(id={self.id}, date={self.event_date}, intensity={self.flood_intensity})>"


class RiskScore(Base):
    """Risk Scores table - stores computed multi-variate risk scores for each heritage site."""
    
    __tablename__ = 'risk_scores'
    __table_args__ = {'schema': 'unesco_risk'}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(Integer, ForeignKey('unesco_risk.heritage_sites.id'), unique=True, nullable=False)
    urban_density_score = Column(Float, CheckConstraint("urban_density_score BETWEEN 0 AND 1"))
    climate_anomaly_score = Column(Float, CheckConstraint("climate_anomaly_score BETWEEN 0 AND 1"))
    seismic_risk_score = Column(Float, CheckConstraint("seismic_risk_score BETWEEN 0 AND 1"))
    fire_risk_score = Column(Float, CheckConstraint("fire_risk_score BETWEEN 0 AND 1"))
    flood_risk_score = Column(Float, CheckConstraint("flood_risk_score BETWEEN 0 AND 1"))
    coastal_risk_score = Column(Float, CheckConstraint("coastal_risk_score BETWEEN 0 AND 1"))
    composite_risk_score = Column(Float, CheckConstraint("composite_risk_score BETWEEN 0 AND 1"))
    isolation_forest_score = Column(Float)
    is_anomaly = Column(Boolean, default=False)
    risk_level = Column(String(20), CheckConstraint("risk_level IN ('critical', 'high', 'medium', 'low')"))
    calculated_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    site = relationship("HeritageSite", back_populates="risk_score")
    
    def __repr__(self):
        return f"<RiskScore(site_id={self.site_id}, level='{self.risk_level}', composite={self.composite_risk_score})>"
