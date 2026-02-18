"""Visualization modules for UNESCO Heritage Sites Risk Modeling."""

# Legacy Folium visualization
from src.visualization.folium_map_legacy import generate_risk_map

# Modern Dash interactive dashboard
from src.visualization.dash_app import run_dashboard

__all__ = ["generate_risk_map", "run_dashboard"]
