"""
Phase 8: Folium Visualization Module.

Generates an interactive risk map of UNESCO Heritage Sites in Europe
using Folium with:
- Risk-colored CircleMarkers (critical=red, high=orange, medium=yellow, low=green)
- Popup HTML with site details, sub-scores, and anomaly flags
- HeatMap layer weighted by composite risk score
- MarkerCluster for dense regions
- Custom HTML legend
- LayerControl to toggle layers
"""

import logging
import os
from typing import Optional

import folium
import folium.plugins as plugins
import numpy as np
import pandas as pd
from sqlalchemy import text

from config.settings import (
    DEFAULT_MAP_FILE,
    OUTPUT_MAP_DIR,
    RISK_COLORS,
)
from src.db.connection import get_engine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAP_CENTER = [50, 10]  # Center of Europe
MAP_ZOOM = 4
MAP_TILES = "CartoDB positron"

MARKER_RADIUS_NORMAL = 5
MARKER_RADIUS_ANOMALY = 8
MARKER_WEIGHT_NORMAL = 1
MARKER_WEIGHT_ANOMALY = 3

HEATMAP_RADIUS = 25
HEATMAP_BLUR = 15
HEATMAP_MAX_ZOOM = 10


def load_site_risk_data() -> pd.DataFrame:
    """
    Load heritage site data joined with risk scores from database.

    Returns:
        DataFrame with site metadata, coordinates, risk scores, and anomaly info.
    """
    engine = get_engine()

    query = text("""
        SELECT
            hs.id AS site_id,
            hs.whc_id,
            hs.name,
            hs.country,
            hs.category,
            hs.date_inscribed,
            hs.in_danger,
            ST_Y(hs.geom) AS latitude,
            ST_X(hs.geom) AS longitude,
            COALESCE(rs.urban_density_score, 0)   AS urban_density_score,
            COALESCE(rs.climate_anomaly_score, 0)  AS climate_anomaly_score,
            COALESCE(rs.seismic_risk_score, 0)     AS seismic_risk_score,
            COALESCE(rs.fire_risk_score, 0)        AS fire_risk_score,
            COALESCE(rs.flood_risk_score, 0)       AS flood_risk_score,
            COALESCE(rs.coastal_risk_score, 0)     AS coastal_risk_score,
            COALESCE(rs.composite_risk_score, 0)   AS composite_risk_score,
            COALESCE(rs.isolation_forest_score, 0) AS isolation_forest_score,
            COALESCE(rs.is_anomaly, FALSE)         AS is_anomaly,
            COALESCE(rs.risk_level, 'low')         AS risk_level
        FROM unesco_risk.heritage_sites hs
        LEFT JOIN unesco_risk.risk_scores rs ON hs.id = rs.site_id
        ORDER BY hs.id;
    """)

    df = pd.read_sql(query, engine)
    logger.info(f"Loaded {len(df)} sites with risk scores")
    return df


# ---------------------------------------------------------------------------
# Popup builder
# ---------------------------------------------------------------------------
def _build_popup_html(row: pd.Series) -> str:
    """Build styled popup HTML for a single site."""
    risk_level = str(row["risk_level"]).capitalize()
    risk_color = RISK_COLORS.get(str(row["risk_level"]), "#888")
    anomaly_flag = " ⚠️ ANOMALY" if row["is_anomaly"] else ""

    html = f"""
    <div style="font-family: Arial, sans-serif; width: 280px;">
      <h4 style="margin:0 0 6px 0; color:#333;">
        {row['name']}{anomaly_flag}
      </h4>
      <p style="margin:2px 0; font-size:12px; color:#666;">
        {row['country']} &middot; {row['category']}
        {' &middot; Inscribed ' + str(int(row['date_inscribed'])) if pd.notna(row['date_inscribed']) else ''}
        {' &middot; <b style=\"color:red;\">IN DANGER</b>' if row['in_danger'] else ''}
      </p>
      <hr style="margin:6px 0; border:none; border-top:1px solid #ddd;">
      <table style="font-size:11px; width:100%; border-collapse:collapse;">
        <tr><td style="padding:2px 4px;">Urban Density</td>
            <td style="padding:2px 4px; text-align:right;"><b>{row['urban_density_score']:.2f}</b></td></tr>
        <tr><td style="padding:2px 4px;">Climate Anomaly</td>
            <td style="padding:2px 4px; text-align:right;"><b>{row['climate_anomaly_score']:.2f}</b></td></tr>
        <tr><td style="padding:2px 4px;">Seismic Risk</td>
            <td style="padding:2px 4px; text-align:right;"><b>{row['seismic_risk_score']:.2f}</b></td></tr>
        <tr><td style="padding:2px 4px;">Fire Risk</td>
            <td style="padding:2px 4px; text-align:right;"><b>{row['fire_risk_score']:.2f}</b></td></tr>
        <tr><td style="padding:2px 4px;">Flood Risk</td>
            <td style="padding:2px 4px; text-align:right;"><b>{row['flood_risk_score']:.2f}</b></td></tr>
        <tr><td style="padding:2px 4px;">Coastal Risk</td>
            <td style="padding:2px 4px; text-align:right;"><b>{row['coastal_risk_score']:.2f}</b></td></tr>
      </table>
      <hr style="margin:6px 0; border:none; border-top:1px solid #ddd;">
      <p style="margin:2px 0; font-size:13px;">
        <b>Composite Score: {row['composite_risk_score']:.2f}</b>
        &nbsp;
        <span style="background:{risk_color}; color:white; padding:1px 6px;
              border-radius:4px; font-size:11px;">{risk_level}</span>
      </p>
    </div>
    """
    return html


# ---------------------------------------------------------------------------
# Legend builder
# ---------------------------------------------------------------------------
def _build_legend_html() -> str:
    """Build a custom HTML legend for the map."""
    return """
    <div style="
        position: fixed;
        bottom: 30px; left: 30px;
        background: white;
        padding: 12px 16px;
        border: 2px solid #ccc;
        border-radius: 6px;
        z-index: 1000;
        font-family: Arial, sans-serif;
        font-size: 12px;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.2);
    ">
      <b style="font-size:13px;">Risk Level</b><br>
      <i style="background:#d32f2f; width:12px; height:12px;
         display:inline-block; border-radius:50%; margin:3px 4px 0 0;"></i> Critical<br>
      <i style="background:#f57c00; width:12px; height:12px;
         display:inline-block; border-radius:50%; margin:3px 4px 0 0;"></i> High<br>
      <i style="background:#fbc02d; width:12px; height:12px;
         display:inline-block; border-radius:50%; margin:3px 4px 0 0;"></i> Medium<br>
      <i style="background:#388e3c; width:12px; height:12px;
         display:inline-block; border-radius:50%; margin:3px 4px 0 0;"></i> Low<br>
      <hr style="margin:6px 0; border:none; border-top:1px solid #ddd;">
      <i style="background:white; width:12px; height:12px;
         display:inline-block; border-radius:50%; margin:3px 4px 0 0;
         border:3px solid #d32f2f;"></i> Anomaly ⚠️<br>
    </div>
    """


# ---------------------------------------------------------------------------
# Map generator
# ---------------------------------------------------------------------------
def generate_risk_map(
    output_path: Optional[str] = None,
    include_heatmap: bool = True,
    include_clusters: bool = True,
) -> str:
    """
    Generate an interactive Folium risk map.

    Args:
        output_path: Output HTML file path. Defaults to DEFAULT_MAP_FILE.
        include_heatmap: Whether to add a HeatMap layer.
        include_clusters: Whether to use MarkerCluster for dense areas.

    Returns:
        Absolute path of the saved HTML file.
    """
    if output_path is None:
        output_path = DEFAULT_MAP_FILE

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    logger.info("Loading site risk data from database...")
    df = load_site_risk_data()

    if df.empty:
        logger.warning("No data found — generating empty map")

    logger.info(f"Building map with {len(df)} sites...")

    # --- Base map ---
    m = folium.Map(
        location=MAP_CENTER,
        zoom_start=MAP_ZOOM,
        tiles=MAP_TILES,
        control_scale=True,
    )

    # --- Heritage Sites layer ---
    if include_clusters:
        site_layer = plugins.MarkerCluster(name="Heritage Sites")
    else:
        site_layer = folium.FeatureGroup(name="Heritage Sites")

    for _, row in df.iterrows():
        risk_level = str(row["risk_level"])
        color = RISK_COLORS.get(risk_level, "#888")
        is_anomaly = bool(row["is_anomaly"])

        radius = MARKER_RADIUS_ANOMALY if is_anomaly else MARKER_RADIUS_NORMAL
        weight = MARKER_WEIGHT_ANOMALY if is_anomaly else MARKER_WEIGHT_NORMAL
        fill_opacity = 0.9 if is_anomaly else 0.7

        popup_html = _build_popup_html(row)
        popup = folium.Popup(popup_html, max_width=320)

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=radius,
            color=color if not is_anomaly else "#d32f2f",
            fill=True,
            fill_color=color,
            fill_opacity=fill_opacity,
            weight=weight,
            popup=popup,
            tooltip=row["name"],
        ).add_to(site_layer)

    site_layer.add_to(m)

    # --- HeatMap layer ---
    if include_heatmap and not df.empty:
        heat_data = df[["latitude", "longitude", "composite_risk_score"]].values.tolist()
        heat_layer = plugins.HeatMap(
            heat_data,
            name="Risk Heatmap",
            radius=HEATMAP_RADIUS,
            blur=HEATMAP_BLUR,
            max_zoom=HEATMAP_MAX_ZOOM,
            min_opacity=0.3,
        )
        heat_layer.add_to(m)

    # --- Layer control ---
    folium.LayerControl(collapsed=False).add_to(m)

    # --- Legend ---
    legend_html = _build_legend_html()
    m.get_root().html.add_child(folium.Element(legend_html))

    # --- Save ---
    m.save(output_path)
    abs_path = os.path.abspath(output_path)
    logger.info(f"✓ Map saved to {abs_path}")
    logger.info(f"  Sites plotted: {len(df)}")
    logger.info(f"  Risk distribution: {df['risk_level'].value_counts().to_dict()}")

    return abs_path


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Folium risk map for UNESCO Heritage Sites"
    )
    parser.add_argument(
        "-o", "--output",
        default=DEFAULT_MAP_FILE,
        help=f"Output HTML file path (default: {DEFAULT_MAP_FILE})",
    )
    parser.add_argument(
        "--no-heatmap",
        action="store_true",
        help="Disable HeatMap layer",
    )
    parser.add_argument(
        "--no-clusters",
        action="store_true",
        help="Disable MarkerCluster",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    output = generate_risk_map(
        output_path=args.output,
        include_heatmap=not args.no_heatmap,
        include_clusters=not args.no_clusters,
    )
    print(f"\n✓ Risk map generated: {output}")


if __name__ == "__main__":
    main()
