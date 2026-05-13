import random
from shapely.geometry import box, Polygon
from shapely.ops import unary_union


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

    results = [_to_dict(s, l) for s, l in top5]
    best    = results[0]

    print(f"  🧬 NSGA-III: {len(population)} layouts evaluated, "
          f"Pareto front: {len(pareto)}, "
          f"Best: {best['num_plots']} plots, {best['efficiency_score']}% eff")

    return {
        "pareto_layouts":   results,
        "best_layout":      best,
        "total_candidates": len(population),
    }


def _random_layout(available, minx, miny, maxx, maxy, min_park):
    plots  = []
    parks  = []
    remain = available

    # Place one park
    pw = random.uniform(15, 30)
    ph = max(15.0, min_park / pw)
    px = random.uniform(minx + 2, max(minx + 3, maxx - pw - 2))
    py = random.uniform(miny + 2, max(miny + 3, maxy - ph - 2))
    park = box(px, py, px + pw, py + ph).intersection(available)
    if not park.is_empty and park.area > 50:
        parks.append(park)
        remain = remain.difference(park)

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
    return {"plots": plots, "parks": parks}


def _fallback_layout(available, min_park, bounds):
    minx, miny, maxx, maxy = bounds
    plots  = []
    parks  = []

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
    return {"plots": plots, "parks": parks}


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


def _to_dict(score, layout):
    plot_area = sum(p.area for p in layout["plots"] if not p.is_empty)
    park_area = sum(p.area for p in layout["parks"] if not p.is_empty)
    total     = plot_area + park_area

    plots_out = []
    for i, p in enumerate(layout["plots"]):
        if p.is_empty or p.area < 10:
            continue
        g = p if p.geom_type == "Polygon" else list(p.geoms)[0]
        plots_out.append({
            "id":          i + 1,
            "area_m2":     round(p.area, 1),
            "coordinates": [[list(c) for c in g.exterior.coords]],
            "type":        "residential",
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
        })

    efficiency = round(plot_area / total * 100, 1) if total > 0 else 0.0

    return {
        "plots":                plots_out,
        "parks":                parks_out,
        "num_plots":            len(plots_out),
        "total_plot_area_m2":   round(plot_area, 2),
        "total_park_area_m2":   round(park_area, 2),
        "efficiency_score":     efficiency,
        "score":                list(score),
    }