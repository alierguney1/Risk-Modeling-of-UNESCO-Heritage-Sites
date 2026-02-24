#!/usr/bin/env python3
"""
Launch script for UNESCO Heritage Sites Risk Map.

Generates the interactive Folium risk map and opens it in the browser.
"""

import sys
import os
import webbrowser

from src.visualization.folium_map import generate_risk_map


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate UNESCO Heritage Sites Risk Map"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output HTML file path",
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
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't automatically open browser",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("🏛️  UNESCO Heritage Sites Risk Map")
    print("=" * 70)

    try:
        output_path = generate_risk_map(
            output_path=args.output,
            include_heatmap=not args.no_heatmap,
            include_clusters=not args.no_clusters,
        )

        print(f"\n✓ Risk map generated: {output_path}")

        if not args.no_browser:
            webbrowser.open(f"file://{os.path.abspath(output_path)}")

    except KeyboardInterrupt:
        print("\n\n👋 Cancelled. Goodbye!")
        sys.exit(0)
