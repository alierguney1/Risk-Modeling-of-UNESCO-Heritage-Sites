# Legacy vs Modern Visualization Comparison

## Overview

This document compares the **legacy Folium implementation** with the **new modern Plotly Dash dashboard**.

---

## Side-by-Side Comparison

### Architecture

| Aspect | Legacy (Folium) | Modern (Dash) |
|--------|----------------|---------------|
| **Framework** | Folium 0.15+ | Plotly Dash 4.0+ |
| **Map Engine** | Leaflet.js | Mapbox GL |
| **Rendering** | CPU-based | GPU-accelerated |
| **Output** | Static HTML file | Live web application |
| **Updates** | Regenerate entire file | Real-time callbacks |
| **Dependencies** | Minimal | Rich ecosystem |

### Features

| Feature | Legacy | Modern |
|---------|--------|--------|
| **Interactive Map** | ✅ | ✅ |
| **Hover Tooltips** | ❌ | ✅ |
| **Click Popups** | ✅ | ✅ |
| **Marker Clustering** | ✅ | ✅ |
| **Heat Map** | ✅ | ❌ (not needed) |
| **3D Globe View** | ❌ | ✅ |
| **Multiple Map Styles** | 1 | 4 |
| **Real-time Filtering** | ❌ | ✅ |
| **Country Filter** | ❌ | ✅ |
| **Risk Level Filter** | ❌ | ✅ |
| **Category Filter** | ❌ | ✅ |
| **Live Statistics** | ❌ | ✅ |
| **Analytics Charts** | ❌ | ✅ |
| **Responsive UI** | ⚠️ Basic | ✅ Advanced |
| **Dark Theme** | ❌ | ✅ |
| **Professional UI** | ⚠️ Basic | ✅ Bootstrap |

### User Experience

| Aspect | Legacy | Modern |
|--------|--------|--------|
| **Initial Load** | Fast | Fast |
| **Interactions** | Limited | Rich |
| **Exploration** | Basic | Advanced |
| **Data Discovery** | Manual | Guided |
| **Visual Appeal** | Good | Excellent |
| **Wow Factor** | Moderate | High |
| **Presentation Ready** | Yes | Yes++ |

### Performance

| Metric | Legacy | Modern |
|--------|--------|--------|
| **File Size** | ~2-5 MB | N/A (web app) |
| **Load Time** | 2-3 sec | 1-2 sec |
| **Render Speed** | Good | Excellent |
| **Large Datasets** | Slow | Fast |
| **Zoom Performance** | Good | Excellent |
| **Animation** | Basic | Smooth 60fps |

### Use Cases

| Use Case | Legacy | Modern | Winner |
|----------|--------|--------|--------|
| **Quick Static Map** | ✅ Best | ⚠️ Overkill | Legacy |
| **Presentations** | ✅ Good | ✅ Excellent | Modern |
| **Data Exploration** | ⚠️ Limited | ✅ Ideal | Modern |
| **Executive Demos** | ⚠️ OK | ✅ Perfect | Modern |
| **Research Analysis** | ⚠️ Basic | ✅ Comprehensive | Modern |
| **Public Website** | ✅ Easy | ⚠️ Needs server | Legacy |
| **Internal Tool** | ⚠️ Limited | ✅ Ideal | Modern |
| **Offline Viewing** | ✅ Perfect | ❌ Needs server | Legacy |

### Code Examples

#### Legacy: Generating a Map

```python
from src.visualization import generate_risk_map

# Simple one-liner
output = generate_risk_map(
    output_path="output/maps/risk_map.html",
    include_heatmap=True,
    include_clusters=True
)

# Opens in browser
import webbrowser
webbrowser.open(output)
```

**Pros:**
- Simple API
- Single function call
- Self-contained HTML file

**Cons:**
- No interactivity after generation
- Can't filter or explore
- Must regenerate for changes

#### Modern: Running Dashboard

```python
from src.visualization import run_dashboard

# Launch interactive dashboard
run_dashboard(
    host="127.0.0.1",
    port=8050,
    debug=False
)

# Or use the convenience script
# python run_dashboard.py
```

**Pros:**
- Full interactivity
- Real-time filtering
- Live analytics
- Professional UI

**Cons:**
- Requires running server
- Not a static file

### Migration Path

Both implementations coexist. You can use either depending on your needs:

```python
# Legacy: For static maps
from src.visualization.folium_map_legacy import generate_risk_map
map_path = generate_risk_map()

# Modern: For interactive dashboard
from src.visualization.dash_app import run_dashboard
run_dashboard()
```

---

## When to Use Each

### Use Legacy Folium When:

- ✅ You need a **static HTML file** to share
- ✅ You want **offline viewing** capability
- ✅ You prefer **simple, quick** map generation
- ✅ You're embedding in a **simple website**
- ✅ You need **basic interactivity** only

### Use Modern Dashboard When:

- ✅ You need **advanced filtering** and exploration
- ✅ You're doing **presentations** or demos
- ✅ You want **analytics** alongside the map
- ✅ You need **multiple views** (2D, 3D, charts)
- ✅ You want a **professional UI**
- ✅ You're building an **internal tool**
- ✅ You need **real-time updates**

---

## Transition Guide

### For Existing Users

If you're used to the legacy Folium map:

1. **Try the new dashboard** - Just run `python run_dashboard.py`
2. **Explore features** - Click filters, try 3D view, change map styles
3. **Compare workflows** - See which fits your needs
4. **Keep both** - Use legacy for static maps, modern for analysis

### For New Users

Start with the **modern dashboard** for the best experience:

1. Install dependencies: `pip install -r requirements.txt`
2. Launch: `python run_dashboard.py`
3. Explore the interface
4. Read the guide: `docs/DASHBOARD_GUIDE.md`

---

## Technical Details

### File Locations

```
src/visualization/
├── folium_map_legacy.py  # Legacy implementation
├── dash_app.py            # Modern dashboard
└── __init__.py            # Exports both
```

### Import Paths

```python
# Legacy
from src.visualization.folium_map_legacy import generate_risk_map

# Modern
from src.visualization.dash_app import run_dashboard

# Or use the unified interface
from src.visualization import generate_risk_map, run_dashboard
```

### Configuration

Both use the same configuration from `config/settings.py`:

- `RISK_COLORS` - Color scheme for risk levels
- `MAP_CENTER` - Default map center
- Database connection settings
- Risk thresholds and weights

---

## Recommendation

**For most users**: Start with the **modern dashboard** for the best experience.

**For special cases**: Use **legacy** when you specifically need static HTML files.

**Best practice**: Keep both available and choose based on the specific use case.

---

## Questions?

**Q: Will the legacy be removed?**  
A: No, it's preserved as `folium_map_legacy.py` for compatibility.

**Q: Can I use both in the same project?**  
A: Yes! They're independent and can coexist.

**Q: Which is better for my thesis presentation?**  
A: The modern dashboard will impress your committee!

**Q: Which is better for a paper figure?**  
A: Use modern dashboard, export the view you want.

**Q: Do they show the same data?**  
A: Yes, both connect to the same database.

**Q: Can I customize the modern dashboard?**  
A: Absolutely! See `docs/DASHBOARD_GUIDE.md` for details.

---

*Last Updated: February 2026*  
*Comparison Version: 1.0*
