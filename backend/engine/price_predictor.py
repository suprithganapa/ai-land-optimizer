"""
price_predictor.py
Multi-city land price prediction.
Auto-detects city from coordinates, falls back to built-in rate tables
when Kaggle CSV is not available.
"""
import os
import math
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score
import joblib

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH  = os.path.join(BASE_DIR, "data", "bengaluru_land_rates.csv")
MODEL_PATH = os.path.join(BASE_DIR, "data", "price_model.pkl")

ZONE_MULTIPLIERS = {
    "residential":       1.00,
    "commercial":        1.35,
    "industrial":        0.70,
    "retail":            1.25,
    "construction":      0.85,
    "meadow":            0.75,
    "grass":             0.72,
    "recreation_ground": 0.80,
    "default":           1.00,
}

# ── City bounding boxes (lat_min, lat_max, lng_min, lng_max) ─────────────
CITY_BOUNDS = {
    "Bengaluru": (12.78, 13.18, 77.45, 77.80),
    "Mumbai":    (18.85, 19.30, 72.75, 73.00),
    "Hyderabad": (17.20, 17.60, 78.30, 78.65),
    "Pune":      (18.40, 18.65, 73.75, 74.00),
    "Chennai":   (12.85, 13.25, 80.10, 80.35),
    "Delhi":     (28.40, 28.85, 76.85, 77.40),
    "Kolkata":   (22.40, 22.70, 88.25, 88.50),
    "Ahmedabad": (22.90, 23.20, 72.45, 72.70),
}

# ── Built-in rate tables (Rs/m² — mid-tier residential) ──────────────────
CITY_BASE_RATES = {
    "Bengaluru": {
        "Central (Indiranagar/Koramangala)": {"lat": 12.9716, "lng": 77.6412, "rate": 85000, "tier": "premium"},
        "North (Hebbal/Yelahanka)":           {"lat": 13.0358, "lng": 77.5970, "rate": 55000, "tier": "mid"},
        "South (JP Nagar/Bannerghatta)":      {"lat": 12.9041, "lng": 77.5962, "rate": 62000, "tier": "mid"},
        "East (Whitefield/Marathahalli)":     {"lat": 12.9716, "lng": 77.7480, "rate": 70000, "tier": "mid"},
        "West (Rajajinagar/Yeshwanthpur)":    {"lat": 13.0100, "lng": 77.5560, "rate": 58000, "tier": "mid"},
        "Outer North (Devanahalli)":          {"lat": 13.2500, "lng": 77.7100, "rate": 28000, "tier": "budget"},
        "Outer East (Electronic City)":       {"lat": 12.8450, "lng": 77.6641, "rate": 42000, "tier": "budget"},
    },
    "Mumbai": {
        "South Mumbai (Colaba/Nariman Point)": {"lat": 18.9220, "lng": 72.8347, "rate": 350000, "tier": "premium"},
        "Western Suburbs (Bandra/Andheri)":    {"lat": 19.0596, "lng": 72.8295, "rate": 160000, "tier": "premium"},
        "Central Suburbs (Kurla/Ghatkopar)":   {"lat": 19.0755, "lng": 72.8777, "rate": 90000,  "tier": "mid"},
        "Navi Mumbai (Vashi/Kharghar)":        {"lat": 19.0636, "lng": 73.0297, "rate": 65000,  "tier": "mid"},
        "Thane":                               {"lat": 19.2183, "lng": 72.9781, "rate": 55000,  "tier": "mid"},
        "Mira-Bhayandar":                      {"lat": 19.2952, "lng": 72.8544, "rate": 42000,  "tier": "budget"},
    },
    "Hyderabad": {
        "Central (Banjara Hills/Jubilee Hills)": {"lat": 17.4138, "lng": 78.4311, "rate": 95000,  "tier": "premium"},
        "IT Corridor (HITEC City/Gachibowli)":   {"lat": 17.4435, "lng": 78.3772, "rate": 75000,  "tier": "premium"},
        "East (LB Nagar/Uppal)":                 {"lat": 17.3740, "lng": 78.5490, "rate": 45000,  "tier": "mid"},
        "North (Kompally/Medchal)":              {"lat": 17.5500, "lng": 78.4880, "rate": 32000,  "tier": "budget"},
        "Old City (Charminar/Tolichowki)":       {"lat": 17.3616, "lng": 78.4747, "rate": 40000,  "tier": "mid"},
    },
    "Pune": {
        "Central (Koregaon Park/Kalyani Nagar)": {"lat": 18.5362, "lng": 73.8944, "rate": 90000,  "tier": "premium"},
        "West (Hinjewadi/Wakad)":                {"lat": 18.5912, "lng": 73.7369, "rate": 55000,  "tier": "mid"},
        "East (Kharadi/Viman Nagar)":            {"lat": 18.5590, "lng": 73.9337, "rate": 62000,  "tier": "mid"},
        "South (Hadapsar/Kondhwa)":              {"lat": 18.5018, "lng": 73.9259, "rate": 48000,  "tier": "budget"},
        "Pimpri-Chinchwad":                      {"lat": 18.6279, "lng": 73.8009, "rate": 40000,  "tier": "budget"},
    },
    "Chennai": {
        "Central (Adyar/Besant Nagar)":          {"lat": 13.0067, "lng": 80.2561, "rate": 95000,  "tier": "premium"},
        "North (Perambur/Kolathur)":             {"lat": 13.1143, "lng": 80.2329, "rate": 45000,  "tier": "mid"},
        "South (Sholinganallur/Perungudi)":      {"lat": 12.9010, "lng": 80.2279, "rate": 58000,  "tier": "mid"},
        "West (Porur/Poonamallee)":              {"lat": 13.0360, "lng": 80.1572, "rate": 42000,  "tier": "budget"},
        "OMR (IT Corridor)":                     {"lat": 12.8260, "lng": 80.2275, "rate": 62000,  "tier": "mid"},
    },
    "Delhi": {
        "South Delhi (Defence Colony/GK)":       {"lat": 28.5672, "lng": 77.2167, "rate": 180000, "tier": "premium"},
        "Central Delhi (Connaught Place)":       {"lat": 28.6315, "lng": 77.2167, "rate": 200000, "tier": "premium"},
        "Dwarka/Janakpuri":                      {"lat": 28.5921, "lng": 77.0460, "rate": 80000,  "tier": "mid"},
        "Rohini/Pitampura":                      {"lat": 28.7041, "lng": 77.1025, "rate": 65000,  "tier": "mid"},
        "Noida (UP)":                            {"lat": 28.5355, "lng": 77.3910, "rate": 55000,  "tier": "mid"},
    },
    "Kolkata": {
        "South Kolkata (Ballygunge/Alipore)":    {"lat": 22.5200, "lng": 88.3550, "rate": 75000,  "tier": "premium"},
        "Salt Lake/New Town":                    {"lat": 22.5780, "lng": 88.4298, "rate": 55000,  "tier": "mid"},
        "North Kolkata (Shyambazar)":            {"lat": 22.5937, "lng": 88.3682, "rate": 40000,  "tier": "mid"},
        "Howrah":                                {"lat": 22.5958, "lng": 88.2636, "rate": 32000,  "tier": "budget"},
    },
    "Ahmedabad": {
        "West (Bodakdev/SG Highway)":            {"lat": 23.0469, "lng": 72.5252, "rate": 52000,  "tier": "premium"},
        "Central (Navrangpura/CG Road)":         {"lat": 23.0358, "lng": 72.5664, "rate": 48000,  "tier": "mid"},
        "East (Maninagar/Naroda)":               {"lat": 22.9764, "lng": 72.6199, "rate": 28000,  "tier": "budget"},
        "Gandhinagar":                           {"lat": 23.2156, "lng": 72.6369, "rate": 35000,  "tier": "budget"},
    },
}


def haversine_km(lat1, lng1, lat2, lng2):
    R    = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a    = (math.sin(dlat / 2) ** 2 +
            math.cos(math.radians(lat1)) *
            math.cos(math.radians(lat2)) *
            math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def detect_city(lat: float, lng: float) -> str:
    """Detect which city the coordinates fall in."""
    for city, (lat_min, lat_max, lng_min, lng_max) in CITY_BOUNDS.items():
        if lat_min <= lat <= lat_max and lng_min <= lng <= lng_max:
            return city
    # Fall back to nearest city centroid
    city_centroids = {
        "Bengaluru": (12.9716, 77.5946),
        "Mumbai":    (19.0760, 72.8777),
        "Hyderabad": (17.3850, 78.4867),
        "Pune":      (18.5204, 73.8567),
        "Chennai":   (13.0827, 80.2707),
        "Delhi":     (28.6139, 77.2090),
        "Kolkata":   (22.5726, 88.3639),
        "Ahmedabad": (23.0225, 72.5714),
    }
    nearest = min(city_centroids.items(),
                  key=lambda kv: haversine_km(lat, lng, kv[1][0], kv[1][1]))
    return nearest[0]


def _predict_from_table(lat: float, lng: float, city: str,
                        zone_type: str, area_m2: float) -> dict:
    """Predict price using built-in rate table (no ML model needed)."""
    city_table = CITY_BASE_RATES.get(city, CITY_BASE_RATES["Bengaluru"])
    refs = []
    for name, info in city_table.items():
        dist = haversine_km(lat, lng, info["lat"], info["lng"])
        refs.append({**info, "area_name": name, "distance_km": round(dist, 2)})
    refs.sort(key=lambda r: r["distance_km"])
    near5 = refs[:5]

    # Weighted nearest-neighbor
    weights = [1.0 / (r["distance_km"] + 0.01) for r in near5]
    w_sum   = sum(weights)
    w_rate  = sum(r["rate"] * w for r, w in zip(near5, weights)) / w_sum

    mult       = ZONE_MULTIPLIERS.get(zone_type, 1.0)
    final_rate = round(w_rate * mult)

    row  = near5[0]
    dist = row["distance_km"]
    if   dist < 1: confidence, pct = "Very High", 95
    elif dist < 3: confidence, pct = "High",      85
    elif dist < 8: confidence, pct = "Medium",    72
    else:          confidence, pct = "Estimated",  55

    top_refs = [{
        "area_name":         r["area_name"],
        "avg_rate_per_m2":   r["rate"],
        "distance_km":       r["distance_km"],
        "tier":              r["tier"],
    } for r in near5[:5]]

    print(f"  💰 {city} — ₹{final_rate:,}/m² ref: {row['area_name']} ({dist:.1f}km)")

    return {
        "city":                   city,
        "predicted_rate_per_m2":  final_rate,
        "min_rate_per_m2":        round(final_rate * 0.80),
        "max_rate_per_m2":        round(final_rate * 1.25),
        "nearest_reference_area": row["area_name"],
        "distance_to_reference":  dist,
        "zone_multiplier":        mult,
        "zone_type_used":         zone_type,
        "confidence":             confidence,
        "confidence_pct":         pct,
        "tier":                   row["tier"],
        "weighted_rate":          round(w_rate),
        "rf_rate":                round(w_rate),
        "top_references":         top_refs,
        "data_source":            f"LandAI {city} Rate Table",
        "method":                 "Weighted Nearest Neighbor",
        "listing_count":          len(city_table),
    }


# ── Bengaluru Kaggle ML model ─────────────────────────────────────────────

def load_dataset():
    return pd.read_csv(DATA_PATH)


def train_model(df):
    print("🤖 Training Random Forest on Kaggle Bengaluru dataset...")
    df       = df.copy()
    le_zone  = LabelEncoder()
    le_tier  = LabelEncoder()
    df["ze"] = le_zone.fit_transform(df["zone_type"])
    df["te"] = le_tier.fit_transform(df["tier"])
    X        = df[["lat", "lng", "ze", "te", "min_rate", "max_rate"]].values
    y        = df["avg_rate_per_m2"].values
    model    = RandomForestRegressor(n_estimators=300, max_depth=10, random_state=42, n_jobs=-1)
    model.fit(X, y)
    try:
        scores = cross_val_score(model, X, y, cv=3, scoring="r2")
        print(f"  ✅ R² scores: {scores.round(3)} — Mean: {scores.mean():.3f}")
    except Exception as e:
        print(f"  ✅ Trained (CV skipped: {e})")
    joblib.dump({"model": model, "le_zone": le_zone, "le_tier": le_tier}, MODEL_PATH)
    return model, le_zone, le_tier


def load_or_train(df):
    if os.path.exists(MODEL_PATH):
        try:
            s = joblib.load(MODEL_PATH)
            return s["model"], s["le_zone"], s["le_tier"]
        except Exception:
            pass
    return train_model(df)


def _predict_bengaluru_ml(lat: float, lng: float, zone_type: str, area_m2: float) -> dict:
    """ML-based prediction for Bengaluru using Kaggle dataset."""
    df               = load_dataset()
    model, le_z, le_t = load_or_train(df)
    df               = df.copy()
    df["dist"]       = df.apply(
        lambda r: haversine_km(lat, lng, r["lat"], r["lng"]), axis=1
    )
    near5 = df.nsmallest(5, "dist").copy()
    near5["w"]  = 1.0 / (near5["dist"] + 0.01)
    near5["w"] /= near5["w"].sum()
    w_rate       = float((near5["avg_rate_per_m2"] * near5["w"]).sum())

    row = near5.iloc[0]
    try:   ze = le_z.transform([zone_type])[0]
    except ValueError: ze = le_z.transform(["residential"])[0]
    try:   te = le_t.transform([row["tier"]])[0]
    except ValueError: te = 0

    rf_rate  = float(model.predict(np.array([[
        lat, lng, ze, te, float(row["min_rate"]), float(row["max_rate"])
    ]]))[0])
    blended  = w_rate * 0.6 + rf_rate * 0.4
    mult     = ZONE_MULTIPLIERS.get(zone_type, 1.0)
    final    = round(blended * mult)

    dist = float(row["dist"])
    if   dist < 1: confidence, pct = "Very High", 95
    elif dist < 3: confidence, pct = "High",      85
    elif dist < 8: confidence, pct = "Medium",    72
    else:          confidence, pct = "Estimated",  55

    top_refs = near5[["area_name", "avg_rate_per_m2", "dist", "tier"]].rename(
        columns={"dist": "distance_km"}
    ).to_dict("records")

    print(f"  💰 Bengaluru ML — ₹{final:,}/m² ref: {row['area_name']} ({dist:.1f}km)")
    return {
        "city":                   "Bengaluru",
        "predicted_rate_per_m2":  final,
        "min_rate_per_m2":        round(float(near5["min_rate"].mean()) * mult),
        "max_rate_per_m2":        round(float(near5["max_rate"].mean()) * mult),
        "nearest_reference_area": row["area_name"],
        "distance_to_reference":  round(dist, 2),
        "zone_multiplier":        mult,
        "zone_type_used":         zone_type,
        "confidence":             confidence,
        "confidence_pct":         pct,
        "tier":                   row["tier"],
        "weighted_rate":          round(w_rate),
        "rf_rate":                round(rf_rate),
        "top_references":         top_refs,
        "data_source":            "Kaggle Bengaluru House Price Dataset (13,320 transactions)",
        "method":                 "Random Forest (40%) + Weighted Nearest Neighbor (60%)",
        "listing_count":          int(row.get("listing_count", 0)),
    }


def predict_land_price(
    centroid_lat: float,
    centroid_lng: float,
    zone_type:    str   = "residential",
    area_m2:      float = 1000,
) -> dict:
    """
    Main entry point.
    Auto-detects city; uses Kaggle ML for Bengaluru, rate tables for other cities.
    """
    try:
        city = detect_city(centroid_lat, centroid_lng)
        print(f"  🏙️  Detected city: {city}")

        # Try Kaggle ML model for Bengaluru
        if city == "Bengaluru" and os.path.exists(DATA_PATH):
            return _predict_bengaluru_ml(centroid_lat, centroid_lng, zone_type, area_m2)

        # Rate-table prediction for all cities
        return _predict_from_table(centroid_lat, centroid_lng, city, zone_type, area_m2)

    except Exception as e:
        print(f"❌ Price prediction error: {e}")
        import traceback; traceback.print_exc()
        return {
            "city":                   "Unknown",
            "predicted_rate_per_m2":  45000,
            "min_rate_per_m2":        35000,
            "max_rate_per_m2":        60000,
            "nearest_reference_area": "Fallback",
            "distance_to_reference":  0,
            "zone_multiplier":        1.0,
            "zone_type_used":         zone_type,
            "confidence":             "Low",
            "confidence_pct":         30,
            "tier":                   "mid",
            "weighted_rate":          45000,
            "rf_rate":                45000,
            "top_references":         [],
            "data_source":            "Default fallback",
            "method":                 "Fallback",
            "listing_count":          0,
        }
