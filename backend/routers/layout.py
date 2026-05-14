from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

from engine.preprocessor import convert_to_meters, convert_layout_to_latlng, get_inverse_transformer, utm_to_lnglat
from engine.road_solver import generate_road_network, generate_infrastructure
from engine.plot_optimizer import optimize_plots
from engine.networkx_validator import validate_connectivity
from engine.price_predictor import predict_land_price

router = APIRouter()


class LayoutRequest(BaseModel):
    polygon:     Dict[str, Any]
    constraints: Dict[str, Any]


def _convert_point(pt, transformer):
    """Convert a single [x, y] UTM point to [lng, lat]."""
    if pt and len(pt) >= 2:
        return utm_to_lnglat(pt[0], pt[1], transformer)
    return pt


def _convert_line(line, transformer):
    """Convert list of [x, y] UTM points to [[lng, lat], ...]."""
    return [utm_to_lnglat(c[0], c[1], transformer) for c in line if len(c) >= 2]


def _convert_infrastructure(infra: dict, transformer) -> dict:
    """Convert all infrastructure UTM coordinates to WGS84."""
    out = {}

    # Points
    out["streetlights"]           = [_convert_point(p, transformer)
                                      for p in infra.get("streetlights", [])]
    out["sewage_treatment_plant"] = _convert_point(
        infra.get("sewage_treatment_plant"), transformer)
    out["water_tank"]             = _convert_point(
        infra.get("water_tank"), transformer)
    out["main_transformer"]       = _convert_point(
        infra.get("main_transformer"), transformer)
    out["distribution_boards"]    = [_convert_point(list(p), transformer)
                                     for p in infra.get("distribution_boards", [])]

    # Lines (list of polylines)
    out["sewage_pipe_lines"]   = [_convert_line(l, transformer)
                                  for l in infra.get("sewage_pipe_lines", [])]
    out["collector_pipes"]     = [_convert_line(l, transformer)
                                  for l in infra.get("collector_pipes", [])]
    out["water_main_lines"]    = [_convert_line(l, transformer)
                                  for l in infra.get("water_main_lines", [])]
    out["water_branch_pipes"]  = [_convert_line(l, transformer)
                                  for l in infra.get("water_branch_pipes", [])]
    out["hv_cables"]           = [_convert_line(l, transformer)
                                  for l in infra.get("hv_cables", [])]
    out["lv_cables"]           = [_convert_line(l, transformer)
                                  for l in infra.get("lv_cables", [])]

    return out


def _convert_amenities(amenities, transformer):
    out = []
    for a in amenities:
        coords = a.get("coordinates", [[]])
        ring   = coords[0] if coords else []
        converted = _convert_line(ring, transformer)
        if len(converted) >= 3:
            out.append({**a, "coordinates": [converted]})
    return out


@router.post("/generate-layout")
async def generate_layout(request: LayoutRequest):
    try:
        print("\n===== Layout Pipeline =====")

        # Stage 1
        print("  [1/6] Preprocessing coordinates...")
        geo          = convert_to_meters(request.polygon)
        setback      = geo["setback_polygon"]
        constraints  = request.constraints
        centroid_lat = geo["centroid_lat"]
        centroid_lng = geo["centroid_lng"]
        transformer  = get_inverse_transformer(centroid_lat, centroid_lng)

        if setback.is_empty or setback.area < 100:
            raise HTTPException(400, "Land area too small after setback")

        # Stage 2
        print("  [2/6] Generating road network...")
        road_result = generate_road_network(setback, constraints)
        road_union  = road_result["road_union"]

        # Stage 3
        print("  [3/6] NSGA-III optimization...")
        opt_result = optimize_plots(setback, road_union, constraints)
        best       = opt_result["best_layout"]

        # Stage 4
        print("  [4/6] NetworkX validation...")
        validation = validate_connectivity(
            best["plots"], road_result["roads"], road_result["entrance"]
        )

        # Stage 5 — Infrastructure generation (UTM)
        print("  [5/6] Generating infrastructure...")
        plot_centroids = [p["centroid"] for p in best["plots"] if "centroid" in p]
        infra_utm      = generate_infrastructure(road_result, setback, plot_centroids)

        # Stage 5b — Convert everything to WGS84
        print("  [5b] Converting UTM to WGS84...")
        raw = {
            "plots":              best["plots"],
            "parks":              best["parks"],
            "roads":              road_result["roads"],
            "entrance":           road_result["entrance"],
            "total_road_area_m2": road_result["total_road_area_m2"],
            "road_length_m":      road_result["road_length_m"],
        }
        converted      = convert_layout_to_latlng(raw, centroid_lat, centroid_lng)
        infra_wgs84    = _convert_infrastructure(infra_utm, transformer)
        amenities_wgs84 = _convert_amenities(best.get("amenities", []), transformer)

        # Convert plot centroids to WGS84 (for frontend popup)
        for plot in converted["plots"]:
            if "centroid" in plot:
                plot["centroid_lnglat"] = _convert_point(plot["centroid"], transformer)

        # Convert Pareto layouts
        converted_pareto = []
        for i, pl in enumerate(opt_result["pareto_layouts"]):
            cp = convert_layout_to_latlng(
                {"plots": pl["plots"], "parks": pl["parks"],
                 "roads": road_result["roads"], "entrance": road_result["entrance"]},
                centroid_lat, centroid_lng,
            )
            # Add sqft to Pareto plots too
            for plot in cp["plots"]:
                if "centroid" in plot:
                    plot["centroid_lnglat"] = _convert_point(plot["centroid"], transformer)
            am = _convert_amenities(pl.get("amenities", []), transformer)
            converted_pareto.append({
                **pl,
                "plots":     cp["plots"],
                "parks":     cp["parks"],
                "roads":     cp["roads"],
                "amenities": am,
            })

        # Stage 6
        print("  [6/6] ML price prediction...")
        zone_type  = constraints.get("zone_type", "residential")
        price_data = predict_land_price(
            centroid_lat=centroid_lat,
            centroid_lng=centroid_lng,
            zone_type=zone_type,
            area_m2=geo["area_m2"],
        )

        print(f"  Pipeline complete: {best['num_plots']} plots, "
              f"{validation['connectivity_pct']}% connected, "
              f"Rs {price_data['predicted_rate_per_m2']:,}/m2")

        return {
            "status":   "success",

            # Geometry (WGS84)
            "plots":    converted["plots"],
            "parks":    converted["parks"],
            "roads":    converted["roads"],
            "entrance": converted["entrance"],
            "amenities": amenities_wgs84,

            # Infrastructure (WGS84)
            "infrastructure": infra_wgs84,

            # Metrics
            "num_plots":               best["num_plots"],
            "num_parks":               best["num_parks"],
            "total_plot_area_m2":      best["total_plot_area_m2"],
            "total_park_area_m2":      best["total_park_area_m2"],
            "total_road_area_m2":      road_result["total_road_area_m2"],
            "road_length_m":           road_result["road_length_m"],
            "efficiency_score":        best["efficiency_score"],
            "area_m2":                 geo["area_m2"],
            "centroid_lat":            centroid_lat,
            "centroid_lng":            centroid_lng,

            # Pareto front
            "pareto_layouts": converted_pareto,

            # Validation
            "validation":              validation,
            "is_fully_connected":      validation["is_fully_connected"],
            "connectivity_pct":        validation["connectivity_pct"],
            "utility_route_length_m":  validation["utility_route_length_m"],

            # Price prediction
            "price_prediction": price_data,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"  Layout error: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))