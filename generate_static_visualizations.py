#!/usr/bin/env python3
"""
Generate static visualization examples from the dashboard.

This creates standalone HTML files with the map visualizations
that can be opened in any browser to see the interactive features.
"""

import os
import plotly.graph_objects as go
import plotly.express as px
from src.visualization.dash_app import (
    create_map_figure,
    create_risk_distribution_chart,
    create_risk_factor_chart,
    df_sites,
    RISK_COLORS,
)

# Create output directory
OUTPUT_DIR = "output/visualizations"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 70)
print("🎨 Generating Static Visualizations")
print("=" * 70)

# 1. Main interactive map
print("\n📍 Creating main interactive map...")
map_fig = create_map_figure(df_sites, map_style="dark", show_3d=False)
map_file = os.path.join(OUTPUT_DIR, "interactive_map.html")
map_fig.write_html(map_file)
print(f"   ✓ Saved to: {map_file}")

# 2. 3D Globe view
print("\n🌍 Creating 3D globe view...")
globe_fig = create_map_figure(df_sites, map_style="dark", show_3d=True)
globe_file = os.path.join(OUTPUT_DIR, "3d_globe_view.html")
globe_fig.write_html(globe_file)
print(f"   ✓ Saved to: {globe_file}")

# 3. Risk distribution chart
print("\n📊 Creating risk distribution chart...")
dist_fig = create_risk_distribution_chart(df_sites)
dist_file = os.path.join(OUTPUT_DIR, "risk_distribution.html")
dist_fig.write_html(dist_file)
print(f"   ✓ Saved to: {dist_file}")

# 4. Risk factors radar chart
print("\n🎯 Creating risk factors radar chart...")
factors_fig = create_risk_factor_chart(df_sites)
factors_file = os.path.join(OUTPUT_DIR, "risk_factors.html")
factors_fig.write_html(factors_file)
print(f"   ✓ Saved to: {factors_file}")

# 5. Combined dashboard view
print("\n🖼️  Creating combined dashboard view...")
from plotly.subplots import make_subplots

# Create figure with subplots
fig = make_subplots(
    rows=2,
    cols=2,
    specs=[
        [{"type": "mapbox", "colspan": 2}, None],
        [{"type": "bar"}, {"type": "polar"}],
    ],
    subplot_titles=(
        "UNESCO Heritage Sites Risk Map",
        None,
        "Risk Level Distribution",
        "Average Risk Factors",
    ),
    vertical_spacing=0.15,
    horizontal_spacing=0.1,
)

# Add map
main_map = create_map_figure(df_sites, map_style="dark", show_3d=False)
for trace in main_map.data:
    fig.add_trace(trace, row=1, col=1)

# Add distribution chart
dist_chart = create_risk_distribution_chart(df_sites)
for trace in dist_chart.data:
    fig.add_trace(trace, row=2, col=1)

# Add radar chart
radar_chart = create_risk_factor_chart(df_sites)
for trace in radar_chart.data:
    fig.add_trace(trace, row=2, col=2)

# Update layout
fig.update_layout(
    height=1200,
    template="plotly_dark",
    title_text="UNESCO Heritage Sites Risk Analysis Dashboard",
    title_font_size=24,
    title_x=0.5,
    showlegend=False,
    mapbox=dict(
        style="carto-darkmatter",
        center={"lat": 50, "lon": 10},
        zoom=3.5,
    ),
)

combined_file = os.path.join(OUTPUT_DIR, "dashboard_combined.html")
fig.write_html(combined_file)
print(f"   ✓ Saved to: {combined_file}")

# 6. Create a comparison view with different map styles
print("\n🗺️  Creating map style comparison...")
from plotly.subplots import make_subplots

comparison_fig = make_subplots(
    rows=2,
    cols=2,
    specs=[
        [{"type": "mapbox"}, {"type": "mapbox"}],
        [{"type": "mapbox"}, {"type": "mapbox"}],
    ],
    subplot_titles=("Dark Theme", "Satellite", "Light Theme", "Outdoors"),
    vertical_spacing=0.05,
    horizontal_spacing=0.05,
)

styles = {
    (1, 1): ("dark", "carto-darkmatter"),
    (1, 2): ("satellite", "satellite-streets"),
    (2, 1): ("light", "carto-positron"),
    (2, 2): ("outdoors", "open-street-map"),
}

for (row, col), (style_name, mapbox_style) in styles.items():
    # Create simplified markers for each style
    fig_temp = px.scatter_mapbox(
        df_sites,
        lat="latitude",
        lon="longitude",
        color="composite_risk_score",
        size=[10] * len(df_sites),
        color_continuous_scale=[
            [0, RISK_COLORS["low"]],
            [0.4, RISK_COLORS["medium"]],
            [0.6, RISK_COLORS["high"]],
            [1.0, RISK_COLORS["critical"]],
        ],
        range_color=[0, 1],
        hover_name="name",
    )
    
    for trace in fig_temp.data:
        fig_temp.data[0].showlegend = False
        comparison_fig.add_trace(trace, row=row, col=col)
    
    comparison_fig.update_mapboxes(
        style=mapbox_style,
        center={"lat": 50, "lon": 10},
        zoom=2.5,
        row=row,
        col=col,
    )

comparison_fig.update_layout(
    height=1000,
    template="plotly_dark",
    title_text="Map Style Comparison",
    title_font_size=20,
    showlegend=False,
)

comparison_file = os.path.join(OUTPUT_DIR, "map_styles_comparison.html")
comparison_fig.write_html(comparison_file)
print(f"   ✓ Saved to: {comparison_file}")

# Print summary
print("\n" + "=" * 70)
print("✅ All visualizations generated successfully!")
print("=" * 70)
print(f"\nTotal files created: 6")
print(f"Output directory: {os.path.abspath(OUTPUT_DIR)}")
print("\nYou can open these HTML files in any browser to see the interactive visualizations.")
print("\nGenerated files:")
print("  1. interactive_map.html - Main interactive map with full features")
print("  2. 3d_globe_view.html - 3D orthographic globe projection")
print("  3. risk_distribution.html - Bar chart of risk levels")
print("  4. risk_factors.html - Radar chart of risk factors")
print("  5. dashboard_combined.html - Combined dashboard view")
print("  6. map_styles_comparison.html - Comparison of different map styles")
print("=" * 70)
