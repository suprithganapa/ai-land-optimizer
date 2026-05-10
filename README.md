# 🏙️ LandAI Optimizer
### AI-Powered Residential Land Layout Generator

> An end-to-end decision-support system that takes a raw GPS land boundary and generates an optimized, legally compliant, financially analyzed residential colony layout — powered by NSGA-III, OR-Tools, NetworkX, and Claude AI.

---

## 🎯 Project Overview

Traditional land planning wastes 10–15% of land, takes weeks, has no legal compliance checks, and provides no real-time financial analysis. LandAI Optimizer solves all of this in under 30 seconds.

**SDG Alignment:** SDG 9 — Industry, Innovation and Infrastructure

---

## 🏗️ System Architecture

```
User draws boundary on satellite map
        ↓
[Stage 1] Coordinate Preprocessing (pyproj + Shapely)
        ↓
[Stage 2] Legal Zoning Check (OSM Overpass API)
        ↓
[Stage 3] Building Detection (OSM Overpass API)
        ↓
[Stage 4] Bayesian Warm Start (scikit-optimize)
        ↓
[Stage 5] OR-Tools Road Network Generation (Google OR-Tools)
        ↓
[Stage 6] NSGA-III Multi-Objective Optimization (pymoo)
          → Objective 1: Maximize saleable plot area
          → Objective 2: Minimize road construction cost
          → Objective 3: Maximize green space coverage
          → Output: Pareto front of 5 optimal layouts
        ↓
[Stage 7] NetworkX Graph Validation + Dijkstra utility routing
        ↓
[Stage 8] Random Forest Price Prediction (Kaggle dataset, 13,320 transactions)
        ↓
[Stage 9] Results rendered on zoomed satellite map
          → Orange plots, dark roads, green parks
          → Finance tab with ML-predicted market rates
          → Validation tab with graph metrics
```

---

## 🛠️ Tech Stack

### Frontend
| Tool | Purpose |
|---|---|
| React 18 + Vite | UI framework + fast build |
| MapLibre GL JS | Free satellite map rendering |
| Zustand | Global state management |
| TanStack Query | API call management |
| Tailwind CSS | Dark theme styling |

### Backend
| Tool | Purpose |
|---|---|
| Python 3.12 + FastAPI | Async REST API |
| Shapely 2.0 | Computational geometry |
| pyproj | GPS to UTM coordinate conversion |
| Polars | Fast data processing |

### AI / Optimization
| Tool | Purpose |
|---|---|
| pymoo (NSGA-III) | Multi-objective evolutionary optimization |
| Google OR-Tools | Constraint-based road network generation |
| scikit-optimize | Bayesian warm start |
| NetworkX | Graph validation + Dijkstra shortest path |
| scikit-learn Random Forest | Land price prediction |

### External APIs
| API | Purpose | Cost |
|---|---|---|
| OSM Overpass API | Zoning + building detection | Free |
| Open-Elevation API | Terrain slope data | Free |
| MapLibre Tiles | Satellite imagery | Free |
| Maptiler Geocoding | Location search | Free tier |

### Dataset
- **Kaggle Bengaluru House Price Data** — 13,320 real property transactions
- Source: https://www.kaggle.com/datasets/amitabhajoy/bengaluru-house-price-data
- Processed into 125 Bengaluru area rate benchmarks
- Used to train Random Forest price prediction model (R² = 0.91)

---

## 📁 Project Structure

```
ai-land-optimizer/
│
├── frontend/                          # React 18 + Vite
│   ├── src/
│   │   ├── views/
│   │   │   ├── MapView.jsx            # Page 1: Draw boundary
│   │   │   └── ResultsView.jsx        # Page 2: Layout results
│   │   ├── components/
│   │   │   ├── Map.jsx                # MapLibre satellite map + drawing
│   │   │   └── Sidebar.jsx            # Pipeline status sidebar
│   │   ├── hooks/
│   │   │   └── useLayout.js           # API call hooks
│   │   ├── store/
│   │   │   └── useStore.js            # Zustand global state
│   │   ├── App.jsx                    # Page router
│   │   └── main.jsx                   # Entry point
│   ├── index.html
│   └── vite.config.js
│
├── backend/                           # Python FastAPI
│   ├── main.py                        # API entry point + CORS
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── zoning.py                  # /api/check-zoning endpoint
│   │   └── layout.py                  # /api/generate-layout endpoint
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── preprocessor.py            # Coordinate conversion UTM and WGS84
│   │   ├── zoning_checker.py          # OSM zoning + building detection
│   │   ├── road_solver.py             # OR-Tools road network generation
│   │   ├── plot_optimizer.py          # NSGA-III multi-objective optimization
│   │   ├── networkx_validator.py      # Graph validation + Dijkstra routing
│   │   └── price_predictor.py         # Random Forest price prediction
│   ├── data/
│   │   ├── Bengaluru_House_Data.csv   # Raw Kaggle dataset (download separately)
│   │   ├── process_kaggle_data.py     # Data processing script
│   │   ├── bengaluru_land_rates.csv   # Processed 125-area dataset (auto-generated)
│   │   └── price_model.pkl            # Trained RF model (auto-generated)
│   └── requirements.txt
│
├── .gitignore
└── README.md
```

---

## 🚀 Setup and Installation

### Prerequisites
- Python 3.10 or higher
- Node.js 20 LTS or higher
- Git

### Step 1 — Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/ai-land-optimizer.git
cd ai-land-optimizer
```

### Step 2 — Backend Setup
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Step 3 — Process Dataset (first time only)
```bash
# 1. Download Bengaluru_House_Data.csv from:
#    https://www.kaggle.com/datasets/amitabhajoy/bengaluru-house-price-data
# 2. Place it inside backend/data/
# 3. Then run:

cd data
python process_kaggle_data.py
cd ..
```

### Step 4 — Start Backend
```bash
uvicorn main:app --reload --port 8000
```
API docs available at: http://localhost:8000/docs

### Step 5 — Frontend Setup
```bash
cd frontend
npm install
```

### Step 6 — Add your Maptiler API Key
Get a free key at https://www.maptiler.com then replace in two files:

In `frontend/src/components/Map.jsx` line 6:
```js
const MAPTILER_KEY = 'your_maptiler_key_here'
```

In `frontend/src/views/ResultsView.jsx` line 6:
```js
const MAPTILER_KEY = 'your_maptiler_key_here'
```

### Step 7 — Start Frontend
```bash
npm run dev
```
Open: http://localhost:5173

---

## 🔌 API Endpoints

### POST /api/check-zoning
**Input:** GeoJSON polygon
```json
{
  "type": "Polygon",
  "coordinates": [[[77.59, 12.97], [77.60, 12.97], [77.60, 12.98], [77.59, 12.97]]]
}
```
**Output:** Zone type, legal status, elevation, slope risk, existing building detection, NBC 2016 constraints

### POST /api/generate-layout
**Input:** GeoJSON polygon + constraints dict
**Output:** Optimized plots, roads, parks in lat/lng GeoJSON + Pareto front + financial analysis + ML price prediction

---

## ✅ What is Working (85% Complete)

- [x] Interactive satellite map with polygon drawing tool
- [x] Location search bar with geocoding (Maptiler)
- [x] Lat/lng coordinate paste support (type 12.97, 77.59 and press Enter)
- [x] OSM zoning verification (residential / forest / commercial / industrial)
- [x] Building and structure detection on selected land parcel
- [x] NBC 2016 setback application (3m inward Shapely buffer)
- [x] OR-Tools constraint-based road network generation
- [x] NSGA-III multi-objective layout optimization (100 layouts, 50 generations)
- [x] Pareto front output — 5 optimized layout options (L1 to L5)
- [x] NetworkX graph validation — 100% plot connectivity check
- [x] Dijkstra shortest path utility routing (water pipes + electrical lines)
- [x] UTM to WGS84 coordinate conversion pipeline
- [x] Random Forest price prediction trained on real Kaggle data (R² = 0.91)
- [x] Finance tab — gross revenue, costs, net profit, ROI
- [x] Confidence scoring for price predictions with reference area display
- [x] Two-page navigation (Map View → Results View)
- [x] Dark professional UI across all components
- [x] 3D view toggle (pitch 52 degrees + bearing)
- [x] Pareto layout selector (L1 to L5)
- [x] NBC 2016 compliance checklist in results sidebar

---

## ⏳ What is Remaining (15%)

- [ ] **Plot rendering fix** — Orange plots, roads, and parks not yet visible on results satellite map. Root cause: UTM to lat/lng conversion produces coordinates that need viewport debugging. Fix: verify first_plot_coords in browser console matches centroid lat/lng.
- [ ] **Claude LLM audit** — Mid-pipeline compliance checker that injects corrective constraints back into NSGA-III if layout fails NBC 2016 checks. Needs Anthropic API key.
- [ ] **PDF export** — Playwright headless screenshot of 3D map assembled into ReportLab PDF brochure with financial tables and audit report.
- [ ] **Finance tab ML display** — Reference area comparison cards and confidence progress bar in Results UI.
- [ ] **Pareto layout switching** — Click L1 to L5 to re-render different optimized layouts on the map dynamically.

---

## 🐛 Known Issues

**Issue 1: Results map renders black (no plots visible)**
- Status: Under investigation
- Cause: Coordinate conversion pipeline produces valid lat/lng but map viewport may not be fitting correctly to the converted geometry
- Debug step: Open browser F12 Console after generating layout and check `first_plot_coords` vs `centroid` values
- Fix in progress: Will verify coordinate ranges and adjust fitBounds padding

**Issue 2: Large land areas slow render**
- Status: Known limitation
- Cause: Very large polygons above 50,000 m² generate hundreds of plots causing slow GeoJSON layer rendering
- Workaround: Use land parcels between 1,000 and 30,000 m² for best results

---

## 📊 Dataset Citation

```
Kaggle, "Bengaluru House Price Data," 2019.
Available: https://www.kaggle.com/datasets/amitabhajoy/bengaluru-house-price-data
Accessed: May 2026

Source: Indian real estate listings aggregated from 99acres.com,
MagicBricks.com, and CommonFloor.com covering 13,320 residential
property transactions in Bengaluru Urban District (2015 to 2019).

Processing: Median price per m² computed per locality after outlier
removal (15th to 85th percentile), minimum 5 listings required per area.
125 locations with verified GPS coordinates used for model training.
```

---

## 📚 Academic References

1. Blank, J., & Deb, K. (2020). Pymoo: Multi-objective optimization in Python. *IEEE Access*, 8, 89497–89509.
2. Deb, K., Pratap, A., Agarwal, S., & Meyarivan, T. (2002). A fast and elitist multiobjective genetic algorithm: NSGA-II. *IEEE Transactions on Evolutionary Computation*, 6(2), 182–197.
3. Deb, K., & Jain, H. (2014). An evolutionary many-objective optimization algorithm using reference-point-based nondominated sorting approach. *IEEE Transactions on Evolutionary Computation*, 18(4), 577–601.
4. Google OR-Tools Documentation. https://developers.google.com/optimization
5. Hagberg, A., Schult, D., & Swart, P. (2008). Exploring network structure using NetworkX. *SciPy 2008 Proceedings*.
6. Breiman, L. (2001). Random forests. *Machine Learning*, 45(1), 5–32.
7. Karnataka Stamp and Registration Department. Guidance Value 2024. https://kaverionline.karnataka.gov.in
8. Bureau of Indian Standards. (2016). *National Building Code of India 2016*. BIS, New Delhi.

---

## 👥 Team

- **Project:** LandAI Optimizer — AI-Powered Land Layout Generator
- **Institution:** RV College of Engineering, Bengaluru
- **Semester:** 6th Semester, 2025–26
- **Domain:** Artificial Intelligence + Urban Planning + SDG 9

---

## 📄 License

MIT License — For academic and research use only.

