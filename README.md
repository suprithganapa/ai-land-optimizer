# LandAI Optimizer

> **AI-powered residential colony layout generator** — converts a raw land polygon into a complete, regulation-compliant colony plan with roads, plots, parks, utilities, and Vastu-scored plots, rendered on a live satellite map.

---

## Features

### AI & Optimization
| Feature | Description |
|---|---|
| **NSGA-III Multi-Objective Optimization** | pymoo-based genetic algorithm produces 5 Pareto-optimal layout variants (Max Plots, Balanced, Max Green, Min Cost, Max Density) |
| **OR-Tools Road Network** | Spine + branch road hierarchy with NBC road width enforcement |
| **NetworkX Connectivity Validation** | Graph-based road network validation; reports connectivity %, isolated plots, utility route lengths |
| **ML Price Prediction** | Scikit-learn model predicts land rate (₹/m²) for 6 cities: Bengaluru, Hyderabad, Chennai, Mumbai, Pune, Delhi |
| **OSM Amenity Scoring** | Queries OpenStreetMap within 2 km for schools, hospitals, transit, markets |
| **Stormwater Drainage** | Slope-based channel routing with flood risk classification |

### Regulatory Compliance
| Standard | Implementation |
|---|---|
| **NBC 2016** | Enforces minimum 10% park area, road width standards, plot size minimums |
| **Vastu Shastra** | Every plot scored (E=95, N=90, NE=85, NW=78…SW=68) using shortest-edge frontage direction detection. Average layout score >80% |
| **RERA** | Auto-generated RERA checklist PDF |

### Infrastructure Generation
Full utility network auto-generated and overlaid on satellite map:
- Streetlights (every 20 m along roads)
- Sewage pipe network + collector mains + STP
- Water supply mains + branch pipes + elevated tank
- HV/LV electrical cables + transformer + distribution boards

### Visualization & Export
- MapLibre GL JS satellite map with full infrastructure layer toggle panel
- 2D / 3D tilt toggle
- Development phase overlay (Phase 1/2/3)
- Stormwater drainage overlay
- Before/After satellite comparison toggle
- Collaborative plot annotation mode
- Plot click popups (area, Vastu score, phase)
- DXF/CAD export (AutoCAD-compatible)
- PDF report + RERA checklist PDF

---

## Architecture

```
┌─────────────────────────────────────────┐
│        React 18 + Vite Frontend          │
│  MapLibre GL JS · Zustand · Custom UI    │
└──────────────────┬──────────────────────┘
                   │ HTTP
┌──────────────────▼──────────────────────┐
│           FastAPI Backend (Python)        │
│                                          │
│  [1] Preprocessor      pyproj UTM        │
│  [2] Road Network      OR-Tools          │
│  [3] NSGA-III          pymoo             │
│  [3b] Phase Assignment                   │
│  [4] Connectivity      NetworkX          │
│  [5] Infrastructure    geometry          │
│  [5b] Vastu Scoring                      │
│  [5c] UTM → WGS84      pyproj            │
│  [6] Price Prediction  scikit-learn      │
│  [7] Amenity Scoring   OSM Overpass      │
│  [8] Drainage Analysis                   │
└──────────────────────────────────────────┘
```

---

## Tech Stack

**Frontend:** React 18, Vite, Zustand, MapLibre GL JS

**Backend:** FastAPI, pymoo (NSGA-III), Google OR-Tools, NetworkX, Shapely, pyproj, scikit-learn, ezdxf, reportlab

---

## Getting Started

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## How It Works

1. **Draw** a land boundary polygon on the satellite map
2. **Set constraints** — zone type, plot size range, road width
3. **Generate** — 9-stage AI pipeline runs in ~5–10 seconds
4. **Explore** — switch between 5 Pareto-optimal layouts, toggle infrastructure layers, click plots for Vastu details
5. **Export** — DXF for AutoCAD, PDF report, or RERA checklist

---

## Project Status

| Module | Status |
|---|---|
| Land polygon input & UTM conversion | ✅ Complete |
| OR-Tools road network generation | ✅ Complete |
| NSGA-III plot optimization (5 Pareto variants) | ✅ Complete |
| NBC 2016 compliance enforcement | ✅ Complete |
| Vastu Shastra scoring engine | ✅ Complete |
| Phase-wise development assignment | ✅ Complete |
| NetworkX road connectivity validation | ✅ Complete |
| Infrastructure network generation (water/sewage/electrical) | ✅ Complete |
| UTM → WGS84 coordinate pipeline | ✅ Complete |
| ML land price prediction (6 cities) | ✅ Complete |
| OSM social amenity scoring | ✅ Complete |
| Stormwater drainage analysis | ✅ Complete |
| Satellite map with all layer toggles | ✅ Complete |
| DXF/CAD export | ✅ Complete |
| PDF report & RERA checklist export | ✅ Complete |
| Collaborative plot annotation | ✅ Complete |
| Before/After satellite overlay | ✅ Complete |
| 3D map tilt view | ✅ Complete |

---

## Research

Built as part of a 6th semester Engineering Lab research project on **AI-driven urban land subdivision optimization**.

Key contributions:
- NSGA-III applied to residential plot layout generation with cultural (Vastu) constraints
- Automated NBC 2016 regulatory compliance in generative layout systems
- End-to-end pipeline from raw land polygon to RERA-ready documentation

---

## Author

**Suprith G B** · RVCE Bengaluru · [suprithgb.cs23@rvce.edu.in](mailto:suprithgb.cs23@rvce.edu.in)
**Adhya S Niranjan** · RVCE Bengaluru · [adhyasniranjan.cs23@rvce.edu.in](mailto:adhyasniranjan.cs23@rvce.edu.in)
**Rayala Yuvaraj Vaishnav** · RVCE Bengaluru · [rayalayuvarajv.ai23@rvce.edu.in](mailto:rayalayuvarajv.ai23@rvce.edu.in)
**Vineet Raj** · RVCE Bengaluru · [vineetraj.ai23@rvce.edu.in](mailto:vineetraj.ai23@rvce.edu.in)
