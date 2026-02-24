"""
Modern Interactive Dashboard for UNESCO Heritage Sites Risk Analysis.

Features:
- Interactive Mapbox GL visualization with GPU acceleration
- Real-time filtering and search capabilities
- 3D terrain visualization option
- Risk distribution analytics
- Detailed site information panels
- Responsive Bootstrap UI design
"""

import logging
from typing import Optional

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html
from sqlalchemy import text

from config.settings import DATABASE_URL, RISK_COLORS
from src.db.connection import get_engine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------


def load_site_risk_data() -> pd.DataFrame:
    """Load heritage site data with risk scores from database."""
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


def generate_demo_data():
    """Generate sample data for demo/testing when database is not available."""
    np.random.seed(42)
    
    # Famous UNESCO sites from around the world with realistic coordinates
    demo_sites = [
        {"name": "Acropolis, Athens", "country": "Greece", "lat": 37.9715, "lon": 23.7267, "category": "Cultural"},
        {"name": "Colosseum", "country": "Italy", "lat": 41.8902, "lon": 12.4922, "category": "Cultural"},
        {"name": "Eiffel Tower", "country": "France", "lat": 48.8584, "lon": 2.2945, "category": "Cultural"},
        {"name": "Tower of London", "country": "United Kingdom", "lat": 51.5081, "lon": -0.0759, "category": "Cultural"},
        {"name": "Alhambra", "country": "Spain", "lat": 37.1773, "lon": -3.5889, "category": "Cultural"},
        {"name": "Great Wall of China", "country": "China", "lat": 40.4319, "lon": 116.5704, "category": "Cultural"},
        {"name": "Taj Mahal", "country": "India", "lat": 27.1751, "lon": 78.0421, "category": "Cultural"},
        {"name": "Machu Picchu", "country": "Peru", "lat": -13.1631, "lon": -72.5450, "category": "Cultural"},
        {"name": "Pyramids of Giza", "country": "Egypt", "lat": 29.9792, "lon": 31.1342, "category": "Cultural"},
        {"name": "Angkor Wat", "country": "Cambodia", "lat": 13.4125, "lon": 103.8670, "category": "Cultural"},
        {"name": "Stonehenge", "country": "United Kingdom", "lat": 51.1789, "lon": -1.8262, "category": "Cultural"},
        {"name": "Venice and its Lagoon", "country": "Italy", "lat": 45.4408, "lon": 12.3155, "category": "Cultural"},
        {"name": "Historic Centre of Prague", "country": "Czech Republic", "lat": 50.0755, "lon": 14.4378, "category": "Cultural"},
        {"name": "Meteora", "country": "Greece", "lat": 39.7217, "lon": 21.6306, "category": "Mixed"},
        {"name": "Hagia Sophia", "country": "Turkey", "lat": 41.0086, "lon": 28.9802, "category": "Cultural"},
        {"name": "Serengeti National Park", "country": "Tanzania", "lat": -2.3333, "lon": 34.8333, "category": "Natural"},
        {"name": "Galápagos Islands", "country": "Ecuador", "lat": -0.6667, "lon": -90.5500, "category": "Natural"},
        {"name": "Grand Canyon", "country": "United States", "lat": 36.1069, "lon": -112.1129, "category": "Natural"},
        {"name": "Great Barrier Reef", "country": "Australia", "lat": -18.2871, "lon": 147.6992, "category": "Natural"},
        {"name": "Amazon Rainforest (Central)", "country": "Brazil", "lat": -3.4653, "lon": -62.2159, "category": "Natural"},
        {"name": "Petra", "country": "Jordan", "lat": 30.3285, "lon": 35.4444, "category": "Cultural"},
        {"name": "Chichen Itza", "country": "Mexico", "lat": 20.6843, "lon": -88.5678, "category": "Cultural"},
        {"name": "Kremlin and Red Square", "country": "Russia", "lat": 55.7520, "lon": 37.6175, "category": "Cultural"},
        {"name": "Cappadocia", "country": "Turkey", "lat": 38.6431, "lon": 34.8289, "category": "Mixed"},
        {"name": "Dolomites", "country": "Italy", "lat": 46.4102, "lon": 11.8440, "category": "Natural"},
        {"name": "Yellowstone", "country": "United States", "lat": 44.4280, "lon": -110.5885, "category": "Natural"},
        {"name": "Ha Long Bay", "country": "Vietnam", "lat": 20.9101, "lon": 107.1839, "category": "Natural"},
        {"name": "Mont-Saint-Michel", "country": "France", "lat": 48.6361, "lon": -1.5115, "category": "Cultural"},
        {"name": "Hiroshima Peace Memorial", "country": "Japan", "lat": 34.3955, "lon": 132.4536, "category": "Cultural"},
        {"name": "Easter Island", "country": "Chile", "lat": -27.1127, "lon": -109.3497, "category": "Cultural"},
    ]
    
    sites_data = []
    for i, site in enumerate(demo_sites):
        # Generate realistic risk scores
        base_risk = np.random.random()
        
        # Create correlated risk factors
        urban = max(0, min(1, base_risk + np.random.normal(0, 0.15)))
        climate = max(0, min(1, base_risk + np.random.normal(0, 0.15)))
        seismic = max(0, min(1, 0.7 if site['country'] in ['Italy', 'Greece', 'Turkey'] else np.random.random() * 0.4))
        fire = max(0, min(1, 0.6 if site['country'] in ['Spain', 'Greece', 'Turkey'] else np.random.random() * 0.5))
        flood = max(0, min(1, np.random.random() * 0.6))
        coastal = max(0, min(1, 0.7 if 'Coast' in site['name'] or 'Venice' in site['name'] else np.random.random() * 0.4))
        
        composite = (urban * 0.25 + climate * 0.20 + seismic * 0.20 + 
                    fire * 0.15 + flood * 0.10 + coastal * 0.10)
        
        # Determine risk level
        if composite >= 0.8:
            risk_level = 'critical'
        elif composite >= 0.6:
            risk_level = 'high'
        elif composite >= 0.4:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        # Random anomaly detection (10% of sites)
        is_anomaly = np.random.random() < 0.1
        
        sites_data.append({
            'site_id': i + 1,
            'whc_id': 1000 + i,
            'name': site['name'],
            'country': site['country'],
            'category': site['category'],
            'date_inscribed': int(1960 + np.random.random() * 60),
            'in_danger': np.random.random() < 0.05,  # 5% in danger
            'latitude': site['lat'],
            'longitude': site['lon'],
            'urban_density_score': urban,
            'climate_anomaly_score': climate,
            'seismic_risk_score': seismic,
            'fire_risk_score': fire,
            'flood_risk_score': flood,
            'coastal_risk_score': coastal,
            'composite_risk_score': composite,
            'isolation_forest_score': np.random.normal(0, 1),
            'is_anomaly': is_anomaly,
            'risk_level': risk_level,
        })
    
    return pd.DataFrame(sites_data)


# Load data at startup
try:
    df_sites = load_site_risk_data()
    logger.info("✓ Loaded data from database")
except Exception as e:
    logger.warning(f"Database not available, using demo data: {e}")
    df_sites = generate_demo_data()
    logger.info("✓ Generated demo data with {} sites".format(len(df_sites)))

# ---------------------------------------------------------------------------
# App Configuration
# ---------------------------------------------------------------------------

# Initialize Dash app with Bootstrap theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"}
    ],
)

app.title = "UNESCO Heritage Sites Risk Analysis"

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------

SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "400px",
    "padding": "2rem 1rem",
    "background-color": "#1e1e1e",
    "overflow-y": "auto",
    "box-shadow": "2px 0 10px rgba(0,0,0,0.3)",
}

CONTENT_STYLE = {
    "margin-left": "400px",
    "padding": "0",
    "height": "100vh",
}

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def create_risk_color_scale():
    """Create color scale for risk levels."""
    return [
        [0, RISK_COLORS["low"]],
        [0.4, RISK_COLORS["low"]],
        [0.4, RISK_COLORS["medium"]],
        [0.6, RISK_COLORS["medium"]],
        [0.6, RISK_COLORS["high"]],
        [0.8, RISK_COLORS["high"]],
        [0.8, RISK_COLORS["critical"]],
        [1.0, RISK_COLORS["critical"]],
    ]


def create_map_figure(filtered_df, map_style="dark", show_3d=False):
    """Create the main map visualization."""
    if filtered_df.empty:
        # Return empty figure
        fig = go.Figure()
        fig.update_layout(
            title="No data available",
            template="plotly_dark",
            height=800,
        )
        return fig

    # Create hover text with detailed information
    hover_text = []
    for _, row in filtered_df.iterrows():
        anomaly_marker = " ⚠️ ANOMALY" if row["is_anomaly"] else ""
        danger_marker = " 🚨 IN DANGER" if row["in_danger"] else ""
        text = f"""
<b>{row['name']}</b>{anomaly_marker}{danger_marker}<br>
<b>Country:</b> {row['country']}<br>
<b>Category:</b> {row['category']}<br>
<b>Risk Level:</b> {row['risk_level'].upper()}<br>
<b>Composite Score:</b> {row['composite_risk_score']:.2f}<br>
<br>
<b>Risk Breakdown:</b><br>
Urban Density: {row['urban_density_score']:.2f}<br>
Climate Anomaly: {row['climate_anomaly_score']:.2f}<br>
Seismic Risk: {row['seismic_risk_score']:.2f}<br>
Fire Risk: {row['fire_risk_score']:.2f}<br>
Flood Risk: {row['flood_risk_score']:.2f}<br>
Coastal Risk: {row['coastal_risk_score']:.2f}
"""
        hover_text.append(text)

    # Marker size based on risk and anomaly status
    marker_sizes = filtered_df.apply(
        lambda row: 15 if row["is_anomaly"] else 10, axis=1
    )

    # Create scatter mapbox plot
    if show_3d:
        # 3D scatter geo plot
        fig = go.Figure()

        for risk_level in ["low", "medium", "high", "critical"]:
            mask = filtered_df["risk_level"] == risk_level
            if mask.any():
                subset = filtered_df[mask]
                fig.add_trace(
                    go.Scattergeo(
                        lon=subset["longitude"],
                        lat=subset["latitude"],
                        mode="markers",
                        marker=dict(
                            size=subset.apply(
                                lambda row: 15 if row["is_anomaly"] else 10, axis=1
                            ),
                            color=RISK_COLORS[risk_level],
                            line=dict(
                                width=subset.apply(
                                    lambda row: 3 if row["is_anomaly"] else 1, axis=1
                                ),
                                color="white",
                            ),
                        ),
                        text=[hover_text[i] for i in subset.index],
                        hovertemplate="%{text}<extra></extra>",
                        name=risk_level.capitalize(),
                    )
                )

        fig.update_geos(
            projection_type="orthographic",
            showcountries=True,
            countrycolor="rgba(255,255,255,0.2)",
            showcoastlines=True,
            coastlinecolor="rgba(255,255,255,0.3)",
            showland=True,
            landcolor="rgb(30, 30, 30)",
            showocean=True,
            oceancolor="rgb(10, 10, 30)",
            center=dict(lat=20, lon=0),
            projection_scale=1.5,
        )

        fig.update_layout(
            height=800,
            margin=dict(l=0, r=0, t=40, b=0),
            template="plotly_dark",
            title=dict(
                text="UNESCO Heritage Sites Risk Analysis - 3D Globe View",
                font=dict(size=20, color="white"),
                x=0.5,
                xanchor="center",
            ),
            showlegend=True,
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor="rgba(0,0,0,0.7)",
                bordercolor="white",
                borderwidth=1,
            ),
        )
    else:
        # 2D Mapbox scatter plot
        fig = px.scatter_mapbox(
            filtered_df,
            lat="latitude",
            lon="longitude",
            color="composite_risk_score",
            size=marker_sizes,
            hover_name="name",
            custom_data=["country", "category", "risk_level", "is_anomaly"],
            color_continuous_scale=create_risk_color_scale(),
            range_color=[0, 1],
            zoom=1.5,
            center={"lat": 20, "lon": 0},
            height=800,
        )

        # Update hover template
        fig.update_traces(
            hovertemplate="<br>".join(
                [
                    "<b>%{hovertext}</b>",
                    "Country: %{customdata[0]}",
                    "Category: %{customdata[1]}",
                    "Risk: %{customdata[2]}",
                    "<extra></extra>",
                ]
            )
        )

        # Set mapbox style
        mapbox_styles = {
            "dark": "carto-darkmatter",
            "satellite": "satellite-streets",
            "light": "carto-positron",
            "outdoors": "open-street-map",
        }

        fig.update_layout(
            mapbox_style=mapbox_styles.get(map_style, "carto-darkmatter"),
            margin=dict(l=0, r=0, t=40, b=0),
            title=dict(
                text="UNESCO Heritage Sites Risk Analysis - Interactive Map",
                font=dict(size=20, color="white"),
                x=0.5,
                xanchor="center",
            ),
            coloraxis_colorbar=dict(
                title="Risk Score",
                thickness=15,
                len=0.7,
                bgcolor="rgba(0,0,0,0.7)",
                tickfont=dict(color="white"),
                title_font=dict(color="white"),
            ),
        )

    return fig


def create_risk_distribution_chart(filtered_df):
    """Create risk level distribution bar chart."""
    if filtered_df.empty:
        return go.Figure()

    risk_counts = filtered_df["risk_level"].value_counts().sort_index()

    fig = go.Figure(
        data=[
            go.Bar(
                x=risk_counts.index,
                y=risk_counts.values,
                marker_color=[RISK_COLORS.get(level, "#888") for level in risk_counts.index],
                text=risk_counts.values,
                textposition="auto",
            )
        ]
    )

    fig.update_layout(
        title="Risk Level Distribution",
        template="plotly_dark",
        height=300,
        xaxis_title="Risk Level",
        yaxis_title="Number of Sites",
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=20),
    )

    return fig


def create_risk_factor_chart(filtered_df):
    """Create average risk factors radar chart."""
    if filtered_df.empty:
        return go.Figure()

    risk_factors = [
        "urban_density_score",
        "climate_anomaly_score",
        "seismic_risk_score",
        "fire_risk_score",
        "flood_risk_score",
        "coastal_risk_score",
    ]

    avg_scores = [filtered_df[factor].mean() for factor in risk_factors]

    labels = [
        "Urban Density",
        "Climate Anomaly",
        "Seismic",
        "Fire",
        "Flood",
        "Coastal",
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=avg_scores,
            theta=labels,
            fill="toself",
            fillcolor="rgba(255, 99, 132, 0.3)",
            line=dict(color="rgba(255, 99, 132, 1)", width=2),
            marker=dict(size=8),
        )
    )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                gridcolor="rgba(255,255,255,0.2)",
                tickfont=dict(color="white"),
            ),
            angularaxis=dict(gridcolor="rgba(255,255,255,0.2)"),
        ),
        showlegend=False,
        template="plotly_dark",
        height=300,
        title="Average Risk Factors",
        margin=dict(l=20, r=20, t=40, b=20),
    )

    return fig


# ---------------------------------------------------------------------------
# Layout Components
# ---------------------------------------------------------------------------


def create_sidebar():
    """Create the sidebar with filters and controls."""
    countries = sorted(df_sites["country"].unique()) if not df_sites.empty else []
    categories = sorted(df_sites["category"].unique()) if not df_sites.empty else []

    return html.Div(
        [
            html.H2(
                "🏛️ UNESCO Risk Dashboard",
                className="display-6 mb-4",
                style={"color": "white", "font-weight": "bold"},
            ),
            html.Hr(style={"border-color": "rgba(255,255,255,0.2)"}),
            # Statistics Card
            dbc.Card(
                [
                    dbc.CardHeader(
                        html.H5("📊 Statistics", className="mb-0"),
                        style={"background-color": "#2d2d2d"},
                    ),
                    dbc.CardBody(
                        [
                            html.Div(id="stats-content"),
                        ]
                    ),
                ],
                className="mb-3",
                style={"background-color": "#2d2d2d"},
            ),
            # Filters
            dbc.Card(
                [
                    dbc.CardHeader(
                        html.H5("🔍 Filters", className="mb-0"),
                        style={"background-color": "#2d2d2d"},
                    ),
                    dbc.CardBody(
                        [
                            html.Label("Risk Level", className="fw-bold mb-2"),
                            dcc.Checklist(
                                id="risk-level-filter",
                                options=[
                                    {"label": " Low", "value": "low"},
                                    {"label": " Medium", "value": "medium"},
                                    {"label": " High", "value": "high"},
                                    {"label": " Critical", "value": "critical"},
                                ],
                                value=["low", "medium", "high", "critical"],
                                className="mb-3",
                                labelStyle={"display": "block", "color": "white"},
                            ),
                            html.Hr(style={"border-color": "rgba(255,255,255,0.2)"}),
                            html.Label("Country", className="fw-bold mb-2"),
                            dcc.Dropdown(
                                id="country-filter",
                                options=[{"label": c, "value": c} for c in countries],
                                multi=True,
                                placeholder="Select countries...",
                                className="mb-3",
                                style={"color": "#000"},
                            ),
                            html.Hr(style={"border-color": "rgba(255,255,255,0.2)"}),
                            html.Label("Category", className="fw-bold mb-2"),
                            dcc.Dropdown(
                                id="category-filter",
                                options=[{"label": c, "value": c} for c in categories],
                                multi=True,
                                placeholder="Select categories...",
                                className="mb-3",
                                style={"color": "#000"},
                            ),
                            html.Hr(style={"border-color": "rgba(255,255,255,0.2)"}),
                            dbc.Checklist(
                                id="danger-filter",
                                options=[{"label": " Show only sites in danger", "value": "danger"}],
                                value=[],
                                className="mb-3",
                            ),
                            dbc.Checklist(
                                id="anomaly-filter",
                                options=[{"label": " Show only anomalies", "value": "anomaly"}],
                                value=[],
                                className="mb-3",
                            ),
                        ]
                    ),
                ],
                className="mb-3",
                style={"background-color": "#2d2d2d"},
            ),
            # Map Controls
            dbc.Card(
                [
                    dbc.CardHeader(
                        html.H5("🗺️ Map Style", className="mb-0"),
                        style={"background-color": "#2d2d2d"},
                    ),
                    dbc.CardBody(
                        [
                            dcc.RadioItems(
                                id="map-style",
                                options=[
                                    {"label": " Dark", "value": "dark"},
                                    {"label": " Satellite", "value": "satellite"},
                                    {"label": " Light", "value": "light"},
                                    {"label": " Outdoors", "value": "outdoors"},
                                ],
                                value="dark",
                                className="mb-3",
                                labelStyle={"display": "block", "color": "white"},
                            ),
                            html.Hr(style={"border-color": "rgba(255,255,255,0.2)"}),
                            dbc.Checklist(
                                id="3d-view",
                                options=[{"label": " 3D Globe View", "value": "3d"}],
                                value=[],
                            ),
                        ]
                    ),
                ],
                style={"background-color": "#2d2d2d"},
            ),
        ],
        style=SIDEBAR_STYLE,
    )


def create_main_content():
    """Create the main content area."""
    return html.Div(
        [
            # Main Map
            dcc.Graph(id="main-map", style={"height": "60vh"}),
            # Charts Row
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Graph(id="risk-distribution-chart"),
                        width=6,
                    ),
                    dbc.Col(
                        dcc.Graph(id="risk-factors-chart"),
                        width=6,
                    ),
                ],
                className="g-0",
            ),
        ],
        style=CONTENT_STYLE,
    )


# Set the layout
app.layout = html.Div([create_sidebar(), create_main_content()])

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@callback(
    Output("stats-content", "children"),
    [
        Input("risk-level-filter", "value"),
        Input("country-filter", "value"),
        Input("category-filter", "value"),
        Input("danger-filter", "value"),
        Input("anomaly-filter", "value"),
    ],
)
def update_stats(risk_levels, countries, categories, danger, anomaly):
    """Update statistics based on filters."""
    filtered_df = df_sites.copy()

    if risk_levels:
        filtered_df = filtered_df[filtered_df["risk_level"].isin(risk_levels)]
    if countries:
        filtered_df = filtered_df[filtered_df["country"].isin(countries)]
    if categories:
        filtered_df = filtered_df[filtered_df["category"].isin(categories)]
    if "danger" in danger:
        filtered_df = filtered_df[filtered_df["in_danger"] == True]
    if "anomaly" in anomaly:
        filtered_df = filtered_df[filtered_df["is_anomaly"] == True]

    total_sites = len(filtered_df)
    avg_risk = filtered_df["composite_risk_score"].mean() if total_sites > 0 else 0
    high_risk = len(filtered_df[filtered_df["risk_level"].isin(["high", "critical"])])
    anomalies = filtered_df["is_anomaly"].sum()

    return [
        html.Div(
            [
                html.H3(f"{total_sites:,}", className="mb-0", style={"color": "#4FC3F7"}),
                html.Small("Total Sites", style={"color": "rgba(255,255,255,0.7)"}),
            ],
            className="mb-3",
        ),
        html.Div(
            [
                html.H3(f"{avg_risk:.2f}", className="mb-0", style={"color": "#FFB74D"}),
                html.Small("Avg Risk Score", style={"color": "rgba(255,255,255,0.7)"}),
            ],
            className="mb-3",
        ),
        html.Div(
            [
                html.H3(f"{high_risk}", className="mb-0", style={"color": "#F44336"}),
                html.Small("High/Critical Risk", style={"color": "rgba(255,255,255,0.7)"}),
            ],
            className="mb-3",
        ),
        html.Div(
            [
                html.H3(f"{anomalies}", className="mb-0", style={"color": "#9C27B0"}),
                html.Small("Anomalies Detected", style={"color": "rgba(255,255,255,0.7)"}),
            ],
        ),
    ]


@callback(
    [
        Output("main-map", "figure"),
        Output("risk-distribution-chart", "figure"),
        Output("risk-factors-chart", "figure"),
    ],
    [
        Input("risk-level-filter", "value"),
        Input("country-filter", "value"),
        Input("category-filter", "value"),
        Input("danger-filter", "value"),
        Input("anomaly-filter", "value"),
        Input("map-style", "value"),
        Input("3d-view", "value"),
    ],
)
def update_visualizations(
    risk_levels, countries, categories, danger, anomaly, map_style, view_3d
):
    """Update all visualizations based on filters."""
    filtered_df = df_sites.copy()

    if risk_levels:
        filtered_df = filtered_df[filtered_df["risk_level"].isin(risk_levels)]
    if countries:
        filtered_df = filtered_df[filtered_df["country"].isin(countries)]
    if categories:
        filtered_df = filtered_df[filtered_df["category"].isin(categories)]
    if "danger" in danger:
        filtered_df = filtered_df[filtered_df["in_danger"] == True]
    if "anomaly" in anomaly:
        filtered_df = filtered_df[filtered_df["is_anomaly"] == True]

    show_3d = "3d" in view_3d

    map_fig = create_map_figure(filtered_df, map_style, show_3d)
    dist_fig = create_risk_distribution_chart(filtered_df)
    factors_fig = create_risk_factor_chart(filtered_df)

    return map_fig, dist_fig, factors_fig


# ---------------------------------------------------------------------------
# Run Server
# ---------------------------------------------------------------------------


def run_dashboard(host="127.0.0.1", port=8050, debug=False):
    """Run the Dash application."""
    logger.info(f"Starting dashboard at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="UNESCO Heritage Sites Risk Dashboard"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to run the server on"
    )
    parser.add_argument("--port", type=int, default=8050, help="Port to run the server on")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")

    args = parser.parse_args()

    run_dashboard(host=args.host, port=args.port, debug=args.debug)
