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


def haversine_km(lat1, lng1, lat2, lng2):
    R    = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a    = (math.sin(dlat / 2) ** 2 +
            math.cos(math.radians(lat1)) *
            math.cos(math.radians(lat2)) *
            math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


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
    model    = RandomForestRegressor(
        n_estimators=300, max_depth=10,
        random_state=42, n_jobs=-1,
    )
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


def predict_land_price(
    centroid_lat: float,
    centroid_lng: float,
    zone_type:    str   = "residential",
    area_m2:      float = 1000,
) -> dict:
    try:
        df               = load_dataset()
        model, le_z, le_t = load_or_train(df)

        df          = df.copy()
        df["dist"]  = df.apply(
            lambda r: haversine_km(centroid_lat, centroid_lng, r["lat"], r["lng"]),
            axis=1,
        )
        near5 = df.nsmallest(5, "dist").copy()

        # Weighted nearest-neighbor
        near5["w"]   = 1.0 / (near5["dist"] + 0.01)
        near5["w"]  /= near5["w"].sum()
        w_rate        = float((near5["avg_rate_per_m2"] * near5["w"]).sum())

        # Random Forest
        row = near5.iloc[0]
        try:
            ze = le_z.transform([zone_type])[0]
        except ValueError:
            ze = le_z.transform(["residential"])[0]
        try:
            te = le_t.transform([row["tier"]])[0]
        except ValueError:
            te = 0

        rf_rate = float(model.predict(np.array([[
            centroid_lat, centroid_lng, ze, te,
            float(row["min_rate"]), float(row["max_rate"]),
        ]]))[0])

        blended    = w_rate * 0.6 + rf_rate * 0.4
        mult       = ZONE_MULTIPLIERS.get(zone_type, 1.0)
        final_rate = blended * mult

        dist = float(row["dist"])
        if   dist < 1: confidence, pct = "Very High", 95
        elif dist < 3: confidence, pct = "High",      85
        elif dist < 8: confidence, pct = "Medium",    72
        else:          confidence, pct = "Estimated",  55

        top_refs = near5[[
            "area_name", "avg_rate_per_m2", "dist", "tier"
        ]].rename(columns={"dist": "distance_km"}).to_dict("records")

        print(f"  💰 ₹{round(final_rate):,}/m² — ref: {row['area_name']} "
              f"({dist:.1f}km, {confidence})")

        return {
            "predicted_rate_per_m2":  round(final_rate),
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
    except Exception as e:
        print(f"❌ Price prediction error: {e}")
        import traceback; traceback.print_exc()
        return {
            "predicted_rate_per_m2":  45000,
            "min_rate_per_m2":        35000,
            "max_rate_per_m2":        60000,
            "nearest_reference_area": "Bengaluru (fallback)",
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