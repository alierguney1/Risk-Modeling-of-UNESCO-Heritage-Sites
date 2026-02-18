#!/usr/bin/env python3
"""
Generate static PNG screenshots of the visualizations using kaleido.
"""

import os
from src.visualization.dash_app import (
    create_map_figure,
    create_risk_distribution_chart,
    create_risk_factor_chart,
    df_sites,
)

# Create output directory
OUTPUT_DIR = "output/screenshots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 70)
print("📸 Generating Screenshots")
print("=" * 70)

# 1. Main interactive map
print("\n📍 Creating main map screenshot...")
map_fig = create_map_figure(df_sites, map_style="dark", show_3d=False)
map_file = os.path.join(OUTPUT_DIR, "interactive_map.png")
map_fig.write_image(map_file, width=1920, height=1080, scale=2)
print(f"   ✓ Saved to: {map_file}")

# 2. 3D Globe view
print("\n🌍 Creating 3D globe screenshot...")
globe_fig = create_map_figure(df_sites, map_style="dark", show_3d=True)
globe_file = os.path.join(OUTPUT_DIR, "3d_globe_view.png")
globe_fig.write_image(globe_file, width=1920, height=1080, scale=2)
print(f"   ✓ Saved to: {globe_file}")

# 3. Risk distribution chart
print("\n📊 Creating risk distribution screenshot...")
dist_fig = create_risk_distribution_chart(df_sites)
dist_file = os.path.join(OUTPUT_DIR, "risk_distribution.png")
dist_fig.write_image(dist_file, width=1200, height=600, scale=2)
print(f"   ✓ Saved to: {dist_file}")

# 4. Risk factors radar chart
print("\n🎯 Creating risk factors screenshot...")
factors_fig = create_risk_factor_chart(df_sites)
factors_file = os.path.join(OUTPUT_DIR, "risk_factors.png")
factors_fig.write_image(factors_file, width=1200, height=600, scale=2)
print(f"   ✓ Saved to: {factors_file}")

print("\n" + "=" * 70)
print("✅ All screenshots generated successfully!")
print("=" * 70)
print(f"\nOutput directory: {os.path.abspath(OUTPUT_DIR)}")
print("\nGenerated files:")
for i, filename in enumerate([
    "interactive_map.png",
    "3d_globe_view.png", 
    "risk_distribution.png",
    "risk_factors.png",
], 1):
    print(f"  {i}. {filename}")
print("=" * 70)
