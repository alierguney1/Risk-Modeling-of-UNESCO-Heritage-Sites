#!/usr/bin/env python3
"""
Launch script for UNESCO Heritage Sites Risk Dashboard.

This script provides a convenient way to start the interactive Dash application.
"""

import sys
import webbrowser
from threading import Timer

from src.visualization.dash_app import run_dashboard


def open_browser(url):
    """Open the dashboard in the default web browser after a short delay."""
    webbrowser.open_new(url)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Launch UNESCO Heritage Sites Risk Dashboard"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to run the server on (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Port to run the server on (default: 8050)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode with auto-reload",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't automatically open browser",
    )

    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"

    print("=" * 70)
    print("🏛️  UNESCO Heritage Sites Risk Dashboard")
    print("=" * 70)
    print(f"\n📍 Server starting at: {url}")
    print("\n✨ Features:")
    print("   • Interactive Mapbox visualization")
    print("   • Real-time filtering and search")
    print("   • 3D globe view option")
    print("   • Risk analytics and charts")
    print("   • Responsive design")
    print("\n⌨️  Press Ctrl+C to stop the server")
    print("=" * 70)
    print()

    # Open browser automatically after 1.5 seconds unless disabled
    if not args.no_browser:
        Timer(1.5, open_browser, [url]).start()

    try:
        run_dashboard(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard stopped. Goodbye!")
        sys.exit(0)
