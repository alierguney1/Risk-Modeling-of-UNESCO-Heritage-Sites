# Modern Interactive Dashboard for UNESCO Heritage Sites

## 🎨 Overview

This document describes the new **modern, interactive visualization system** for the UNESCO Heritage Sites Risk Modeling project. The system provides a stunning, professional UI that showcases risk analysis data through cutting-edge web technologies.

## ✨ Key Features

### **Interactive Map Visualization**
- **GPU-accelerated Mapbox GL rendering** for smooth, fast interactions
- **Multiple map styles**: Dark, Satellite, Light, and Outdoors themes
- **3D Globe view** with orthographic projection
- **Risk-colored markers** based on composite risk scores
- **Hover tooltips** with detailed site information
- **Click interactions** for deeper exploration

### **Advanced Filtering & Search**
- **Real-time filters** for:
  - Risk levels (Low, Medium, High, Critical)
  - Countries
  - Categories (Cultural, Natural, Mixed)
  - In-danger status
  - Anomaly detection
- **Instant updates** across all visualizations

### **Analytics Dashboard**
- **Live statistics panel** showing:
  - Total sites
  - Average risk score
  - High/critical risk count
  - Detected anomalies
- **Risk distribution chart** (bar chart)
- **Risk factors radar chart** (polar chart)

### **Professional UI Design**
- **Dark theme** with Bootstrap styling
- **Responsive layout** that works on all screen sizes
- **Sidebar navigation** with organized controls
- **Smooth animations** and transitions

## 🚀 Quick Start

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt
```

### Running the Dashboard

```bash
# Launch the interactive dashboard
python run_dashboard.py

# Or with custom settings
python run_dashboard.py --host 0.0.0.0 --port 8080 --debug
```

The dashboard will automatically open in your default web browser at `http://127.0.0.1:8050`

### Command-Line Options

```bash
python run_dashboard.py --help

Options:
  --host HOST       Host to run the server on (default: 127.0.0.1)
  --port PORT       Port to run the server on (default: 8050)
  --debug           Run in debug mode with auto-reload
  --no-browser      Don't automatically open browser
```

## 📊 Features in Detail

### 1. Main Interactive Map

The centerpiece of the dashboard is a fully interactive map powered by Plotly and Mapbox GL:

**Features:**
- **Color-coded markers** showing risk levels:
  - 🟢 Green: Low risk (0.0-0.4)
  - 🟡 Yellow: Medium risk (0.4-0.6)
  - 🟠 Orange: High risk (0.6-0.8)
  - 🔴 Red: Critical risk (0.8-1.0)
- **Size variation** based on anomaly status
- **Hover tooltips** showing:
  - Site name
  - Country and category
  - All risk factor scores
  - Composite risk score
  - Anomaly and in-danger flags
- **Pan and zoom** with smooth animations
- **Layer toggles** for different data views

### 2. 3D Globe View

Transform the map into a stunning 3D globe:

**Features:**
- **Orthographic projection** for realistic globe appearance
- **Interactive rotation** by dragging
- **Terrain visualization** with country borders and coastlines
- **Zoom controls** for closer inspection
- **Maintains all marker colors and data**

### 3. Risk Analytics

Real-time charts that update based on filters:

**Risk Distribution Chart:**
- Bar chart showing count of sites in each risk category
- Color-coded bars matching risk levels
- Interactive tooltips

**Risk Factors Radar Chart:**
- Polar chart showing average scores for:
  - Urban Density
  - Climate Anomaly
  - Seismic Risk
  - Fire Risk
  - Flood Risk
  - Coastal Risk
- Visual comparison of risk factors

### 4. Dynamic Filtering

Powerful filtering system that updates all visualizations in real-time:

**Filter Types:**
- **Risk Level**: Show/hide specific risk categories
- **Country**: Filter by one or multiple countries
- **Category**: Filter by Cultural, Natural, or Mixed sites
- **In Danger**: Show only UNESCO sites marked as "in danger"
- **Anomalies**: Show only statistically anomalous sites

**How it works:**
1. Select filters in the sidebar
2. All visualizations update instantly
3. Statistics recalculate automatically
4. No page refresh needed

### 5. Map Styles

Choose from 4 different map styles:

1. **Dark** (Default): Dark theme perfect for presentations
2. **Satellite**: Satellite imagery with street overlays
3. **Light**: Clean, light background for printing
4. **Outdoors**: Terrain-focused with topographic details

## 🏗️ Architecture

### Technology Stack

- **Frontend Framework**: Dash (Python web framework)
- **Visualization**: Plotly
- **Maps**: Mapbox GL (via Plotly)
- **UI Components**: Dash Bootstrap Components
- **Styling**: Bootstrap 5 (Dark theme)

### Code Structure

```
src/visualization/
├── dash_app.py           # Main dashboard application
├── folium_map_legacy.py  # Legacy Folium implementation
└── __init__.py           # Module exports

run_dashboard.py          # Launch script
generate_static_visualizations.py  # Export HTML files
```

### Data Flow

```
Database → load_site_risk_data() → df_sites → Dash Callbacks → Visualizations
           (or generate_demo_data())
```

## 🎯 Use Cases

### 1. Risk Assessment Presentations
- Use **3D globe view** for impressive visual impact
- Switch to **satellite view** to show real locations
- Filter to **critical sites** for focused discussion

### 2. Country-Specific Analysis
- Filter by **single country**
- Compare **risk distribution**
- Identify **anomalies** specific to that region

### 3. Hazard-Specific Studies
- View **risk factor radar** to compare hazard types
- Filter to **high seismic risk** sites
- Analyze **coastal vulnerability**

### 4. Monitoring & Alerts
- Filter **in-danger sites**
- Identify **anomalies** requiring investigation
- Track **high-risk sites** over time

## 📝 Customization

### Adding New Filters

Edit `src/visualization/dash_app.py`:

```python
# Add new filter component in create_sidebar()
dcc.Dropdown(
    id="your-filter",
    options=[...],
    ...
)

# Update callback inputs
@callback(
    ...,
    Input("your-filter", "value"),
    ...
)
def update_visualizations(..., your_filter_value):
    # Apply filter logic
    if your_filter_value:
        filtered_df = filtered_df[filtered_df['column'] == your_filter_value]
    ...
```

### Changing Color Scheme

Edit `config/settings.py`:

```python
RISK_COLORS = {
    "critical": "#your_color",
    "high": "#your_color",
    "medium": "#your_color",
    "low": "#your_color",
}
```

### Adding New Charts

Add to `src/visualization/dash_app.py`:

```python
def create_your_chart(filtered_df):
    """Create your custom chart."""
    fig = go.Figure(...)
    return fig

# Add to layout
dcc.Graph(id="your-chart")

# Add to callback
@callback(
    Output("your-chart", "figure"),
    ...
)
```

## 🔧 Troubleshooting

### Database Connection Issues

If the database is not available, the dashboard automatically switches to **demo mode** with synthetic data:

```
Database not available, using demo data
✓ Generated demo data with 30 sites
```

This allows you to test the dashboard features without a running database.

### Performance Issues

For large datasets (1000+ sites):

1. **Disable 3D view** (computationally expensive)
2. **Use filters** to reduce visible points
3. **Lower map quality** in settings
4. **Consider data aggregation** for dense regions

### Port Already in Use

```bash
# Use a different port
python run_dashboard.py --port 8051
```

## 📚 Comparison: Legacy vs Modern

| Feature | Legacy (Folium) | Modern (Dash) |
|---------|----------------|---------------|
| **Technology** | Folium + Leaflet.js | Plotly + Mapbox GL |
| **Rendering** | Static HTML | Live web application |
| **Interactivity** | Click popups only | Full dashboard |
| **Filtering** | None | Real-time filters |
| **Analytics** | None | Charts + statistics |
| **3D View** | No | Yes |
| **Map Styles** | 1 style | 4 styles |
| **UI Design** | Basic | Professional |
| **Performance** | Good | Excellent |
| **Updates** | Regenerate file | Real-time |

## 🌟 Best Practices

1. **Use filters** to focus on specific subsets
2. **Switch map styles** based on context
3. **Enable 3D view** for presentations
4. **Export static HTML** for sharing
5. **Keep database updated** for accurate data

## 📄 License & Credits

Part of the UNESCO Heritage Sites Risk Modeling project.

**Technologies:**
- Plotly (MIT License)
- Dash (MIT License)
- Mapbox GL (BSD License)
- Bootstrap (MIT License)

---

**Last Updated**: February 2026  
**Version**: 1.0.0  
**Status**: Production Ready ✅
