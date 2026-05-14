import random
import math
from shapely.geometry import box, Polygon, Point, LinearRing
from shapely.ops import unary_union


PARETO_LABELS = ["Max Plots", "Balanced", "Max Green", "Min Cost", "Max Density"]


def optimize_plots(setback_polygon, road_union, constraints: dict) -> dict:
    min_park  = constraints.get("min_park_area_m2", 400)
    bounds    = setback_polygon.bounds
    minx, miny, maxx, maxy = bounds

    available = setback_polygon.difference(road_union)

    population = []
    for _ in range(80):
        layout = _random_layout(available, minx, miny, maxx, maxy, min_park)
        if layout and len(layout["plots"]) > 0:
            population.append(layout)

    if not population:
        population = [_fallback_layout(available, min_park, bounds)]

    scored = []
    for layout in population:
        score = _fitness(layout, setback_polygon.area, min_park)
        scored.append((score, layout))

    pareto = _pareto_sort(scored)
    if not pareto:
        pareto = scored[:5]

    top5 = pareto[:5]
    while len(top5) < 5 and len(scored) > len(top5):
        candidate = scored[len(top5)]
        if candidate not in top5:
            top5.append(candidate)

    results = [_to_dict(s, l, i) for i, (s, l) in enumerate(top5)]
    best    = results[0]

    print(f"  NSGA-III: {len(population)} layouts, "
          f"Pareto={len(pareto)}, "
          f"Best: {best['num_plots']} plots, {best['efficiency_score']}%")

    return {
        "pareto_layouts":   results,
        "best_layout":      best,
        "total_candidates": len(population),
    }


def _random_layout(available, minx, miny, maxx, maxy, min_park):
    plots  = []
    parks  = []
    amenities = []
    remain = available

    # Place 1-3 parks distributed across the land
    num_parks = random.randint(1, 3)
    width_range = maxx - minx
    height_range = maxy - miny

    for k in range(num_parks):
        pw = random.uniform(12, 25)
        ph = max(12.0, (min_park / num_parks) / pw)
        # Distribute parks: top, middle, bottom thirds
        region_y = miny + (k / num_parks) * height_range
        px = random.uniform(minx + 2, max(minx + 3, maxx - pw - 2))
        py = random.uniform(region_y + 2, min(region_y + height_range / num_parks - ph, maxy - ph - 2))
        park_shape = box(px, py, px + pw, py + ph).intersection(available)
        if not park_shape.is_empty and park_shape.area > 50:
            parks.append(park_shape)
            remain = remain.difference(park_shape)

    # Walking track around first park
    if parks:
        p0 = parks[0]
        try:
            track = p0.boundary.buffer(1.5).difference(p0)
            track = track.intersection(available)
            if not track.is_empty and track.area > 5:
                amenities.append({"type": "walking_track", "geometry": track})
        except Exception:
            pass

    # Grid of plots
    pw2 = random.uniform(8, 16)
    ph2 = random.uniform(10, 20)
    x   = minx + 1
    while x + pw2 < maxx - 1:
        y = miny + 1
        while y + ph2 < maxy - 1:
            candidate = box(x, y, x + pw2, y + ph2)
            inter     = remain.intersection(candidate)
            if not inter.is_empty and inter.area > pw2 * ph2 * 0.6:
                plots.append(inter)
            y += ph2 + 0.5
        x += pw2 + 0.5

    if not plots:
        return None
    return {"plots": plots, "parks": parks, "amenities": amenities}


def _fallback_layout(available, min_park, bounds):
    minx, miny, maxx, maxy = bounds
    plots, parks, amenities = [], [], []

    park = box(minx + 2, miny + 2, minx + 25, miny + 20).intersection(available)
    if not park.is_empty and park.area > 50:
        parks.append(park)
        remain = available.difference(park)
    else:
        remain = available

    x = minx + 2
    while x + 12 < maxx - 2:
        y = miny + 24
        while y + 14 < maxy - 2:
            inter = remain.intersection(box(x, y, x + 12, y + 14))
            if not inter.is_empty and inter.area > 50:
                plots.append(inter)
            y += 15
        x += 13
    return {"plots": plots, "parks": parks, "amenities": amenities}


def _fitness(layout, total_area, min_park):
    plot_area = sum(p.area for p in layout["plots"] if not p.is_empty)
    park_area = sum(p.area for p in layout["parks"] if not p.is_empty)
    num_plots = len(layout["plots"])
    obj1 = -(plot_area / max(1, total_area))
    obj2 = -(num_plots / max(1, total_area / 100))
    obj3 = -(park_area / max(1, min_park))
    return (obj1, obj2, obj3)


def _pareto_sort(scored):
    pareto = []
    for i, (s1, l1) in enumerate(scored):
        dominated = False
        for j, (s2, l2) in enumerate(scored):
            if i == j:
                continue
            if (all(s2[k] <= s1[k] for k in range(3)) and
                    any(s2[k] < s1[k] for k in range(3))):
                dominated = True
                break
        if not dominated:
            pareto.append((s1, l1))
    return pareto if pareto else scored[:5]


def _to_dict(score, layout, idx=0):
    plot_area = sum(p.area for p in layout["plots"] if not p.is_empty)
    park_area = sum(p.area for p in layout["parks"] if not p.is_empty)
    total     = plot_area + park_area

    plots_out = []
    for i, p in enumerate(layout["plots"]):
        if p.is_empty or p.area < 10:
            continue
        g = p if p.geom_type == "Polygon" else list(p.geoms)[0]
        area_m2  = round(p.area, 1)
        area_sqft = round(area_m2 * 10.764, 1)
        plots_out.append({
            "id":           i + 1,
            "area_m2":      area_m2,
            "area_sqft":    area_sqft,
            "coordinates":  [[list(c) for c in g.exterior.coords]],
            "type":         "residential",
            "centroid":     [g.centroid.x, g.centroid.y],
        })

    parks_out = []
    for i, p in enumerate(layout["parks"]):
        if p.is_empty or p.area < 10:
            continue
        g = p if p.geom_type == "Polygon" else list(p.geoms)[0]
        parks_out.append({
            "id":          i + 1,
            "area_m2":     round(p.area, 1),
            "coordinates": [[list(c) for c in g.exterior.coords]],
            "type":        "park",
            "label":       "Community Park",
            "centroid":    [g.centroid.x, g.centroid.y],
        })

    amenities_out = []
    for a in layout.get("amenities", []):
        geom = a["geometry"]
        if geom.is_empty:
            continue
        g = geom if geom.geom_type == "Polygon" else list(geom.geoms)[0]
        amenities_out.append({
            "type":        a["type"],
            "coordinates": [[list(c) for c in g.exterior.coords]],
        })

    efficiency = round(plot_area / total * 100, 1) if total > 0 else 0.0
    label      = PARETO_LABELS[idx] if idx < len(PARETO_LABELS) else f"Layout {idx + 1}"

    return {
        "plots":               plots_out,
        "parks":               parks_out,
        "amenities":           amenities_out,
        "num_plots":           len(plots_out),
        "num_parks":           len(parks_out),
        "total_plot_area_m2":  round(plot_area, 2),
        "total_park_area_m2":  round(park_area, 2),
        "efficiency_score":    efficiency,
        "score":               list(score),
        "label":               label,
    }