import numpy as np
from shapely.geometry import Polygon, LineString, MultiPolygon, box
from shapely.ops import unary_union
import math


def generate_road_network(setback_polygon, constraints: dict) -> dict:
    """
    Generate road network using constraint-based placement.
    Returns road polygons + entrance point.
    """
    road_width = constraints.get("min_road_width_m", 7.5)

    bounds = setback_polygon.bounds  # minx, miny, maxx, maxy
    minx, miny, maxx, maxy = bounds

    width  = maxx - minx
    height = maxy - miny
    cx     = (minx + maxx) / 2
    cy     = (miny + maxy) / 2

    roads = []

    # ── Spine road (vertical through center) ──────────────
    spine = box(
        cx - road_width / 2, miny,
        cx + road_width / 2, maxy
    ).intersection(setback_polygon)

    if not spine.is_empty:
        roads.append({
            "type":   "spine",
            "geometry": spine,
            "width_m": road_width,
        })

    # ── Horizontal branch roads ────────────────────────────
    num_branches = max(1, int(height / 25))
    spacing = height / (num_branches + 1)

    for i in range(1, num_branches + 1):
        y = miny + i * spacing
        branch = box(minx, y - road_width / 2,
                     maxx, y + road_width / 2
                     ).intersection(setback_polygon)
        if not branch.is_empty:
            roads.append({
                "type":    "branch",
                "geometry": branch,
                "width_m": road_width,
            })

    # ── Combine all road polygons ──────────────────────────
    road_union = unary_union([r["geometry"] for r in roads])

    # ── Entrance point (bottom center) ────────────────────
    entrance = [cx, miny]

    # ── Convert to GeoJSON-able format ────────────────────
    road_features = []
    for r in roads:
        geom = r["geometry"]
        if geom.is_empty:
            continue
        if geom.geom_type == "Polygon":
            road_features.append({
                "type":       r["type"],
                "coordinates": [list(geom.exterior.coords)],
                "width_m":    r["width_m"],
            })

    return {
        "roads":        road_features,
        "road_union":   road_union,
        "entrance":     entrance,
        "total_road_area_m2": round(road_union.area, 2),
        "road_length_m":      round(sum(
            LineString(r["geometry"].exterior.coords).length
            for r in roads if not r["geometry"].is_empty
        ) / 4, 2),
    }