from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

from engine.preprocessor import convert_to_meters, convert_layout_to_latlng, get_inverse_transformer, utm_to_lnglat
from engine.road_solver import generate_road_network, generate_infrastructure
from engine.plot_optimizer import optimize_plots, assign_phases
from engine.networkx_validator import validate_connectivity
from engine.price_predictor import predict_land_price
from engine.vastu_scorer import score_all_plots, layout_vastu_summary
from engine.amenity_scorer import query_amenities
from engine.drainage_engine import compute_drainage

router = APIRouter()


class LayoutRequest(BaseModel):
    polygon:     Dict[str, Any]
    constraints: Dict[str, Any]


def _convert_point(pt, transformer):
    if pt and len(pt) >= 2:
        return utm_to_lnglat(pt[0], pt[1], transformer)
    return pt


def _convert_line(line, transformer):
    return [utm_to_lnglat(c[0], c[1], transformer) for c in line if len(c) >= 2]


def _convert_infrastructure(infra: dict, transformer) -> dict:
    out = {}
    out["streetlights"]           = [_convert_point(p, transformer) for p in infra.get("streetlights", [])]
    out["sewage_treatment_plant"] = _convert_point(infra.get("sewage_treatment_plant"), transformer)
    out["water_tank"]             = _convert_point(infra.get("water_tank"), transformer)
    out["main_transformer"]       = _convert_point(infra.get("main_transformer"), transformer)
    out["distribution_boards"]    = [_convert_point(list(p), transformer) for p in infra.get("distribution_boards", [])]
    out["sewage_pipe_lines"]      = [_convert_line(l, transformer) for l in infra.get("sewage_pipe_lines", [])]
    out["collector_pipes"]        = [_convert_line(l, transformer) for l in infra.get("collector_pipes", [])]
    out["water_main_lines"]       = [_convert_line(l, transformer) for l in infra.get("water_main_lines", [])]
    out["water_branch_pipes"]     = [_convert_line(l, transformer) for l in infra.get("water_branch_pipes", [])]
    out["hv_cables"]              = [_convert_line(l, transformer) for l in infra.get("hv_cables", [])]
    out["lv_cables"]              = [_convert_line(l, transformer) for l in infra.get("lv_cables", [])]
    return out


def _convert_amenities(amenities, transformer):
    out = []
    for a in amenities:
        coords    = a.get("coordinates", [[]])
        ring      = coords[0] if coords else []
        converted = _convert_line(ring, transformer)
        if len(converted) >= 3:
            out.append({**a, "coordinates": [converted]})
    return out


@router.post("/generate-layout")
async def generate_layout(request: LayoutRequest):
    try:
        print("\n===== Layout Pipeline =====")

        # Stage 1 — Preprocessing
        print("  [1/9] Preprocessing coordinates...")
        geo          = convert_to_meters(request.polygon)
        setback      = geo["setback_polygon"]
        constraints  = request.constraints
        centroid_lat = geo["centroid_lat"]
        centroid_lng = geo["centroid_lng"]
        transformer  = get_inverse_transformer(centroid_lat, centroid_lng)

        if setback.is_empty or setback.area < 100:
            raise HTTPException(400, "Land area too small after setback")

        # Stage 2 — Road network
        print("  [2/9] Generating road network...")
        road_result = generate_road_network(setback, constraints)
        road_union  = road_result["road_union"]

        # Stage 3 — NSGA-III optimization
        print("  [3/9] NSGA-III optimization...")
        opt_result   = optimize_plots(setback, road_union, constraints)
        best         = opt_result["best_layout"]
        entrance_utm = opt_result.get("entrance_utm", [setback.centroid.x, setback.bounds[1]])

        # Stage 3b — Phase assignment
        print("  [3b] Assigning development phases...")
        best["plots"] = assign_phases(best["plots"], entrance_utm)

        # Stage 4 — NetworkX validation
        print("  [4/9] NetworkX validation...")
        validation = validate_connectivity(best["plots"], road_result["roads"], road_result["entrance"])

        # Stage 5 — Infrastructure generation
        print("  [5/9] Generating infrastructure...")
        plot_centroids = [p["centroid"] for p in best["plots"] if "centroid" in p]
        infra_utm      = generate_infrastructure(road_result, setback, plot_centroids)

        # Stage 5b — Vastu scoring (UTM coords)
        print("  [5b] Scoring Vastu compliance...")
        best["plots"] = score_all_plots(best["plots"])
        vastu_summary = layout_vastu_summary(best["plots"])

        # Stage 5c — Convert UTM → WGS84
        print("  [5c] Converting UTM to WGS84...")
        raw = {
            "plots":              best["plots"],
            "parks":              best["parks"],
            "inst_blocks":        best.get("inst_blocks", []),
            "roads":              road_result["roads"],
            "entrance":           road_result["entrance"],
            "total_road_area_m2": road_result["total_road_area_m2"],
            "road_length_m":      road_result["road_length_m"],
        }
        converted       = convert_layout_to_latlng(raw, centroid_lat, centroid_lng)
        infra_wgs84     = _convert_infrastructure(infra_utm, transformer)
        amenities_wgs84 = _convert_amenities(best.get("amenities", []), transformer)

        # Add centroid_lnglat to each converted plot
        for plot in converted["plots"]:
            if "centroid" in plot:
                plot["centroid_lnglat"] = _convert_point(plot["centroid"], transformer)

        # Convert Pareto layouts + assign phases + vastu
        converted_pareto = []
        for i, pl in enumerate(opt_result["pareto_layouts"]):
            pl["plots"] = assign_phases(pl["plots"], entrance_utm)
            pl["plots"] = score_all_plots(pl["plots"])
            cp = convert_layout_to_latlng(
                {"plots": pl["plots"], "parks": pl["parks"],
                 "inst_blocks": pl.get("inst_blocks", []),
                 "roads": road_result["roads"], "entrance": road_result["entrance"]},
                centroid_lat, centroid_lng,
            )
            for plot in cp["plots"]:
                if "centroid" in plot:
                    plot["centroid_lnglat"] = _convert_point(plot["centroid"], transformer)
            am = _convert_amenities(pl.get("amenities", []), transformer)
            converted_pareto.append({
                **pl,
                "plots":          cp["plots"],
                "parks":          cp["parks"],
                "inst_blocks":    cp.get("inst_blocks", []),
                "roads":          cp["roads"],
                "amenities":      am,
                "vastu_summary":  layout_vastu_summary(pl["plots"]),
            })

        # Stage 6 — ML price prediction
        print("  [6/9] ML price prediction...")
        zone_type  = constraints.get("zone_type", "residential")
        price_data = predict_land_price(
            centroid_lat=centroid_lat,
            centroid_lng=centroid_lng,
            zone_type=zone_type,
            area_m2=geo["area_m2"],
        )

        # Stage 7 — Social amenity scoring
        print("  [7/9] Querying OSM amenities...")
        try:
            amenity_data = query_amenities(centroid_lat, centroid_lng, radius_m=2000)
        except Exception as e:
            print(f"  Amenity query failed: {e}")
            amenity_data = {"overall_score": 50, "grade": "Average", "amenities": {}}

        # Stage 8 — Stormwater drainage
        print("  [9/9] Computing stormwater drainage...")
        try:
            drainage_data = compute_drainage(centroid_lat, centroid_lng, geo["area_m2"])
        except Exception as e:
            print(f"  Drainage computation failed: {e}")
            drainage_data = {"channels": [], "risk": "Low", "avg_slope_pct": 0}

        print(f"  ✅ Pipeline complete: {best['num_plots']} plots, "
              f"{validation['connectivity_pct']}% connected, "
              f"₹{price_data['predicted_rate_per_m2']:,}/m², "
              f"city={price_data.get('city','?')}")

        return {
            "status":   "success",

            # Geometry (WGS84)
            "plots":       converted["plots"],
            "parks":       converted["parks"],
            "inst_blocks": converted.get("inst_blocks", []),
            "roads":       converted["roads"],
            "entrance":    converted["entrance"],
            "amenities":   amenities_wgs84,

            # Infrastructure (WGS84)
            "infrastructure": infra_wgs84,

            # Core metrics
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
            "pareto_layouts":          converted_pareto,

            # Validation
            "validation":              validation,
            "is_fully_connected":      validation["is_fully_connected"],
            "connectivity_pct":        validation["connectivity_pct"],
            "utility_route_length_m":  validation["utility_route_length_m"],

            # Price prediction (multi-city)
            "price_prediction":        price_data,

            # Vastu
            "vastu_summary":           vastu_summary,

            # Social amenities
            "amenity_score":           amenity_data,

            # Drainage
            "drainage":                drainage_data,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"  Layout error: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
