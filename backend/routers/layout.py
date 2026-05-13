from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

from engine.preprocessor import convert_to_meters, convert_layout_to_latlng
from engine.road_solver import generate_road_network
from engine.plot_optimizer import optimize_plots
from engine.networkx_validator import validate_connectivity
from engine.price_predictor import predict_land_price

router = APIRouter()


class LayoutRequest(BaseModel):
    polygon:     Dict[str, Any]
    constraints: Dict[str, Any]


@router.post("/generate-layout")
async def generate_layout(request: LayoutRequest):
    try:
        print("\n🚀 ═══ Layout Pipeline Starting ═══")

        # Stage 1
        print("📐 [1/6] Preprocessing coordinates...")
        geo          = convert_to_meters(request.polygon)
        setback      = geo["setback_polygon"]
        constraints  = request.constraints
        centroid_lat = geo["centroid_lat"]
        centroid_lng = geo["centroid_lng"]
        print(f"  Area: {geo['area_m2']} m², Centroid: [{centroid_lng:.5f}, {centroid_lat:.5f}]")
        print(f"  UTM zone: {geo['utm_zone']}{geo['hemisphere'][0].upper()}")

        if setback.is_empty or setback.area < 100:
            raise HTTPException(400, "Land area too small after setback")

        # Stage 2
        print("🛣️  [2/6] OR-Tools road network...")
        road_result = generate_road_network(setback, constraints)
        road_union  = road_result["road_union"]

        # Stage 3
        print("🧬 [3/6] NSGA-III multi-objective optimization...")
        opt_result = optimize_plots(setback, road_union, constraints)
        best       = opt_result["best_layout"]

        # Stage 4
        print("🔍 [4/6] NetworkX graph validation...")
        validation = validate_connectivity(
            best["plots"], road_result["roads"], road_result["entrance"]
        )

        # Stage 5
        print("🌍 [5/6] Converting UTM → WGS84 lat/lng...")
        raw = {
            "plots":              best["plots"],
            "parks":              best["parks"],
            "roads":              road_result["roads"],
            "entrance":           road_result["entrance"],
            "total_road_area_m2": road_result["total_road_area_m2"],
            "road_length_m":      road_result["road_length_m"],
        }
        converted = convert_layout_to_latlng(raw, centroid_lat, centroid_lng)

        converted_pareto = []
        for pl in opt_result["pareto_layouts"]:
            cp = convert_layout_to_latlng(
                {"plots": pl["plots"], "parks": pl["parks"],
                 "roads": road_result["roads"], "entrance": road_result["entrance"]},
                centroid_lat, centroid_lng,
            )
            converted_pareto.append({**pl, "plots": cp["plots"],
                                      "parks": cp["parks"], "roads": cp["roads"]})

        # Stage 6
        print("💰 [6/6] ML price prediction...")
        zone_type  = constraints.get("zone_type", "residential")
        price_data = predict_land_price(
            centroid_lat=centroid_lat,
            centroid_lng=centroid_lng,
            zone_type=zone_type,
            area_m2=geo["area_m2"],
        )

        print(f"\n✅ ═══ Pipeline Complete ═══")
        print(f"   Plots: {best['num_plots']}, "
              f"Efficiency: {best['efficiency_score']}%, "
              f"Connectivity: {validation['connectivity_pct']}%")
        print(f"   Price: ₹{price_data['predicted_rate_per_m2']:,}/m² "
              f"({price_data['nearest_reference_area']})\n")

        return {
            "status":                  "success",
            "plots":                   converted["plots"],
            "parks":                   converted["parks"],
            "roads":                   converted["roads"],
            "entrance":                converted["entrance"],
            "num_plots":               best["num_plots"],
            "total_plot_area_m2":      best["total_plot_area_m2"],
            "total_park_area_m2":      best["total_park_area_m2"],
            "total_road_area_m2":      road_result["total_road_area_m2"],
            "road_length_m":           road_result["road_length_m"],
            "efficiency_score":        best["efficiency_score"],
            "area_m2":                 geo["area_m2"],
            "centroid_lat":            centroid_lat,
            "centroid_lng":            centroid_lng,
            "pareto_layouts":          converted_pareto,
            "validation":              validation,
            "is_fully_connected":      validation["is_fully_connected"],
            "connectivity_pct":        validation["connectivity_pct"],
            "utility_route_length_m":  validation["utility_route_length_m"],
            "price_prediction":        price_data,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Layout error: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))