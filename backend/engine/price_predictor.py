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
    df = pd.read_csv(DATA_PATH)
    return df


def train_model(df):
    print("🤖 Training Random Forest on Kaggle dataset...")

    df = df.copy()
    le_zone = LabelEncoder()
    le_tier = LabelEncoder()
    df["zone_encoded"] = le_zone.fit_transform(df["zone_type"])
    df["tier_encoded"] = le_tier.fit_transform(df["tier"])

    X = df[["lat", "lng", "zone_encoded",
            "tier_encoded", "min_rate", "max_rate"]].values
    y = df["avg_rate_per_m2"].values

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=10,
        min_samples_split=2,
        min_samples_leaf=1,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X, y)

    try:
        scores = cross_val_score(model, X, y, cv=3, scoring="r2")
        print(f"✅ Model R² scores: {scores.round(3)} — Mean: {scores.mean():.3f}")
    except Exception as e:
        print(f"✅ Model trained (CV skipped: {e})")

    joblib.dump({
        "model":        model,
        "le_zone":      le_zone,
        "le_tier":      le_tier,
    }, MODEL_PATH)

    print(f"💾 Model saved to {MODEL_PATH}")
    return model, le_zone, le_tier


def load_or_train_model(df):
    if os.path.exists(MODEL_PATH):
        try:
            saved = joblib.load(MODEL_PATH)
            return saved["model"], saved["le_zone"], saved["le_tier"]
        except Exception as e:
            print(f"⚠️  Model load failed ({e}), retraining...")
    return train_model(df)


def predict_land_price(
    centroid_lat: float,
    centroid_lng: float,
    zone_type:    str   = "residential",
    area_m2:      float = 1000,
) -> dict:

    try:
        df              = load_dataset()
        model, le_zone, le_tier = load_or_train_model(df)

        # ── Find nearest reference areas ──────────────────
        df = df.copy()
        df["distance_km"] = df.apply(
            lambda r: haversine_km(centroid_lat, centroid_lng, r["lat"], r["lng"]),
            axis=1,
        )
        nearest5 = df.nsmallest(5, "distance_km").copy()

        # ── Method 1: Weighted nearest-neighbor ───────────
        nearest5["weight"] = 1.0 / (nearest5["distance_km"] + 0.01)
        nearest5["weight"] /= nearest5["weight"].sum()
        weighted_rate = float((nearest5["avg_rate_per_m2"] * nearest5["weight"]).sum())

        # ── Method 2: Random Forest ───────────────────────
        nearest_row = nearest5.iloc[0]

        try:
            zone_enc = le_zone.transform([zone_type])[0]
        except ValueError:
            zone_enc = le_zone.transform(["residential"])[0]

        try:
            tier_enc = le_tier.transform([nearest_row["tier"]])[0]
        except ValueError:
            tier_enc = 0

        X_pred  = np.array([[
            centroid_lat, centroid_lng,
            zone_enc, tier_enc,
            float(nearest_row["min_rate"]),
            float(nearest_row["max_rate"]),
        ]])
        rf_rate = float(model.predict(X_pred)[0])

        # ── Blend 60% weighted + 40% RF ───────────────────
        blended    = weighted_rate * 0.6 + rf_rate * 0.4
        zone_mult  = ZONE_MULTIPLIERS.get(zone_type, 1.0)
        final_rate = blended * zone_mult

        # ── Confidence based on distance ──────────────────
        dist = float(nearest_row["distance_km"])
        if dist < 1:
            confidence, conf_pct = "Very High", 95
        elif dist < 3:
            confidence, conf_pct = "High",      85
        elif dist < 8:
            confidence, conf_pct = "Medium",    72
        else:
            confidence, conf_pct = "Estimated", 55

        # ── Min/max range ─────────────────────────────────
        min_rate = float(nearest5["min_rate"].mean()) * zone_mult
        max_rate = float(nearest5["max_rate"].mean()) * zone_mult

        # ── Top references for display ────────────────────
        top_refs = nearest5[[
            "area_name", "avg_rate_per_m2", "distance_km", "tier"
        ]].to_dict("records")

        print(f"💰 Predicted ₹{round(final_rate):,}/m² "
              f"(ref: {nearest_row['area_name']}, "
              f"{dist:.1f}km, confidence: {confidence})")

        return {
            "predicted_rate_per_m2":  round(final_rate),
            "min_rate_per_m2":        round(min_rate),
            "max_rate_per_m2":        round(max_rate),
            "nearest_reference_area": nearest_row["area_name"],
            "distance_to_reference":  round(dist, 2),
            "zone_multiplier":        zone_mult,
            "zone_type_used":         zone_type,
            "confidence":             confidence,
            "confidence_pct":         conf_pct,
            "tier":                   nearest_row["tier"],
            "weighted_rate":          round(weighted_rate),
            "rf_rate":                round(rf_rate),
            "top_references":         top_refs,
            "data_source":            "Kaggle Bengaluru House Price Dataset (13,320 transactions)",
            "method":                 "Random Forest (40%) + Weighted Nearest Neighbor (60%)",
            "listing_count":          int(nearest_row.get("listing_count", 0)),
        }

    except Exception as e:
        print(f"❌ Price prediction error: {e}")
        import traceback
        traceback.print_exc()
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