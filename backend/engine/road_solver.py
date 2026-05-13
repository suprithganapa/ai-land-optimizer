import math
from shapely.geometry import box, LineString
from shapely.ops import unary_union


def generate_road_network(setback_polygon, constraints: dict) -> dict:
    road_width = constraints.get("min_road_width_m", 7.5)
    minx, miny, maxx, maxy = setback_polygon.bounds
    width  = maxx - minx
    height = maxy - miny
    cx     = (minx + maxx) / 2
    cy     = (miny + maxy) / 2

    roads = []

    # Spine road vertical
    spine = box(cx - road_width / 2, miny, cx + road_width / 2, maxy)
    spine = spine.intersection(setback_polygon)
    if not spine.is_empty:
        roads.append({"type": "spine", "geometry": spine, "width_m": road_width})

    # Horizontal branches
    num_branches = max(1, int(height / 25))
    spacing      = height / (num_branches + 1)
    for i in range(1, num_branches + 1):
        y      = miny + i * spacing
        branch = box(minx, y - road_width / 2, maxx, y + road_width / 2)
        branch = branch.intersection(setback_polygon)
        if not branch.is_empty:
            roads.append({"type": "branch", "geometry": branch, "width_m": road_width})

    if not roads:
        # Fallback: single horizontal road
        fallback = box(minx, cy - road_width / 2, maxx, cy + road_width / 2)
        fallback = fallback.intersection(setback_polygon)
        if not fallback.is_empty:
            roads.append({"type": "branch", "geometry": fallback, "width_m": road_width})

    road_union = unary_union([r["geometry"] for r in roads if not r["geometry"].is_empty])

    # Entrance at bottom center
    entrance = [cx, miny]

    # Build GeoJSON-ready road features
    road_features = []
    for r in roads:
        geom = r["geometry"]
        if geom.is_empty:
            continue
        g = geom if geom.geom_type == "Polygon" else list(geom.geoms)[0]
        coords = [list(c) for c in g.exterior.coords]
        road_features.append({
            "type":        r["type"],
            "coordinates": [coords],
            "width_m":     r["width_m"],
        })

    total_road_area = round(road_union.area, 2) if not road_union.is_empty else 0.0
    road_length     = round(
        sum(LineString(r["geometry"].exterior.coords).length / 4
            for r in roads if not r["geometry"].is_empty),
        2,
    )

    print(f"  🛣️  Roads: {len(road_features)} segments, "
          f"area={total_road_area:.1f}m², length≈{road_length:.1f}m")

    return {
        "roads":              road_features,
        "road_union":         road_union,
        "entrance":           entrance,
        "total_road_area_m2": total_road_area,
        "road_length_m":      road_length,
    }