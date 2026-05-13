from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from engine.preprocessor import convert_to_meters, calculate_slope_risk
from engine.zoning_checker import check_zoning, get_elevation, check_buildings_on_land

router = APIRouter()


class PolygonRequest(BaseModel):
    type:        str
    coordinates: List[List[List[float]]]


@router.post("/check-zoning")
async def check_zoning_endpoint(polygon: PolygonRequest):
    try:
        geojson = {"type": polygon.type, "coordinates": polygon.coordinates}

        print("📐 [1/4] Converting coordinates to UTM...")
        geo = convert_to_meters(geojson)

        print("🌍 [2/4] Querying OSM zoning data...")
        zoning = check_zoning(geo["centroid_lat"], geo["centroid_lng"])

        print("⛰️  [3/4] Fetching elevation data...")
        elevation = get_elevation(geo["centroid_lat"], geo["centroid_lng"])
        slope     = calculate_slope_risk([
            elevation["elevation_m"],
            elevation["elevation_m"] + 3,
        ])

        print("🏗️  [4/4] Checking for existing structures...")
        radius    = max(30, min(150, geo["area_m2"] ** 0.5))
        buildings = check_buildings_on_land(
            geo["centroid_lat"], geo["centroid_lng"], radius
        )

        rejection_reasons = []
        if not zoning["is_buildable"]:
            rejection_reasons.append(f"Zone restricted — {zoning['zone_label']}")
        if slope["slope_risk"] == "high":
            rejection_reasons.append("Terrain slope exceeds safe construction limits")
        if buildings["has_buildings"]:
            names = [b["name"] or b["label"] for b in buildings["buildings"]]
            rejection_reasons.append(
                f"{buildings['count']} existing structure(s): {', '.join(names[:3])}"
            )

        is_legal = len(rejection_reasons) == 0
        verdict  = (
            "Legal to Build — Proceed with AI layout generation"
            if is_legal else
            " | ".join(rejection_reasons)
        )
        print(f"{'✅' if is_legal else '❌'} {verdict}")

        return {
            "status":             "success",
            "is_legal":           is_legal,
            "verdict":            verdict,
            "rejection_reasons":  rejection_reasons,
            "area_m2":            geo["area_m2"],
            "setback_area_m2":    geo["setback_area_m2"],
            "perimeter_m":        geo["perimeter_m"],
            "centroid_lat":       geo["centroid_lat"],
            "centroid_lng":       geo["centroid_lng"],
            "zone_type":          zoning["zone_type"],
            "zone_label":         zoning["zone_label"],
            "is_buildable":       zoning["is_buildable"],
            "zone_color":         zoning["zone_color"],
            "zone_source":        zoning["source"],
            "elevation_m":        elevation["elevation_m"],
            "max_slope_degrees":  slope["max_slope_degrees"],
            "slope_risk":         slope["slope_risk"],
            "has_buildings":      buildings["has_buildings"],
            "building_count":     buildings["count"],
            "buildings_found":    buildings["buildings"],
            "constraints": {
                "min_setback_m":     3,
                "min_road_width_m":  7.5,
                "min_park_area_m2":  max(400, geo["area_m2"] * 0.08),
                "max_slope_degrees": slope["max_slope_degrees"],
                "zone_type":         zoning["zone_type"],
            },
        }

    except Exception as e:
        print(f"❌ Zoning error: {e}")
        raise HTTPException(status_code=500, detail=str(e))