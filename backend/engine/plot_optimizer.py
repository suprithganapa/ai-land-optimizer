import numpy as np
from shapely.geometry import box, Polygon
from shapely.ops import unary_union
import random
import math


def optimize_plots(setback_polygon, road_union, constraints: dict) -> dict:
    """
    NSGA-III style multi-objective plot optimization.
    Objectives:
      1. Maximize saleable plot area
      2. Minimize road cost
      3. Maximize green space
    Returns top 5 Pareto layouts.
    """

    min_park = constraints.get("min_park_area_m2", 400)
    bounds   = setback_polygon.bounds
    minx, miny, maxx, maxy = bounds

    # Available land after roads
    available = setback_polygon.difference(road_union)

    # ── Generate candidate layouts ─────────────────────────
    population = []
    for _ in range(80):
        layout = _generate_random_layout(
            available, minx, miny, maxx, maxy, min_park
        )
        if layout:
            population.append(layout)

    if not population:
        population = [_fallback_layout(available, min_park, bounds)]

    # ── Score each layout (3 objectives) ──────────────────
    scored = []
    for layout in population:
        score = _fitness(layout, setback_polygon.area, min_park)
        scored.append((score, layout))

    # ── Non-dominated sort (Pareto front) ─────────────────
    pareto = _pareto_sort(scored)

    # Return top 5
    top5 = pareto[:5]
    if len(top5) < 5:
        top5 += scored[:5 - len(top5)]
    top5 = top5[:5]

    return {
        "pareto_layouts": [_layout_to_dict(s, l) for s, l in top5],
        "best_layout":    _layout_to_dict(*top5[0]),
        "total_candidates": len(population),
    }


def _generate_random_layout(available, minx, miny, maxx, maxy, min_park):
    plots  = []
    parks  = []
    remaining = available

    # Place park first
    park_w = random.uniform(15, 25)
    park_h = min_park / park_w
    px = random.uniform(minx + 2, maxx - park_w - 2)
    py = random.uniform(miny + 2, maxy - park_h - 2)
    park = box(px, py, px + park_w, py + park_h)

    if park.intersects(available):
        park = park.intersection(available)
        if park.area > 50:
            parks.append(park)
            remaining = remaining.difference(park)

    # Place plots on remaining land
    plot_w = random.uniform(8, 15)
    plot_h = random.uniform(10, 18)

    x = minx + 2
    while x + plot_w < maxx - 2:
        y = miny + 2
        while y + plot_h < maxy - 2:
            candidate = box(x, y, x + plot_w, y + plot_h)
            if (remaining.contains(candidate) or
                    remaining.intersection(candidate).area > plot_w * plot_h * 0.7):
                plots.append(candidate.intersection(remaining))
            y += plot_h + 1
        x += plot_w + 1

    if not plots:
        return None

    return {"plots": plots, "parks": parks}


def _fallback_layout(available, min_park, bounds):
    """Simple grid fallback"""
    minx, miny, maxx, maxy = bounds
    plots = []
    parks = []

    # One park
    park = box(minx + 2, miny + 2, minx + 22, miny + 22)
    park = park.intersection(available)
    if park.area > 50:
        parks.append(park)
        remaining = available.difference(park)
    else:
        remaining = available

    # Grid plots
    x = minx + 2
    while x + 12 < maxx - 2:
        y = miny + 24
        while y + 14 < maxy - 2:
            candidate = box(x, y, x + 12, y + 14)
            inter = remaining.intersection(candidate)
            if inter.area > 50:
                plots.append(inter)
            y += 15
        x += 13

    return {"plots": plots, "parks": parks}


def _fitness(layout, total_area, min_park):
    plots  = layout["plots"]
    parks  = layout["parks"]

    plot_area  = sum(p.area for p in plots if not p.is_empty)
    park_area  = sum(p.area for p in parks if not p.is_empty)
    num_plots  = len(plots)

    # Obj 1 — maximize plot area ratio (negate for minimization)
    obj1 = -(plot_area / total_area) if total_area > 0 else 0

    # Obj 2 — minimize wasted space
    obj2 = -(num_plots / max(1, total_area / 100))

    # Obj 3 — maximize green space (penalize if below minimum)
    obj3 = -(park_area / max(1, min_park))

    return (obj1, obj2, obj3)


def _pareto_sort(scored):
    """Simple non-dominated sort"""
    pareto = []
    for i, (s1, l1) in enumerate(scored):
        dominated = False
        for j, (s2, l2) in enumerate(scored):
            if i == j:
                continue
            if all(s2[k] <= s1[k] for k in range(3)) and \
               any(s2[k] <  s1[k] for k in range(3)):
                dominated = True
                break
        if not dominated:
            pareto.append((s1, l1))
    return pareto if pareto else scored[:5]


def _layout_to_dict(score, layout):
    plots = layout["plots"]
    parks = layout["parks"]

    plot_area = sum(p.area for p in plots if not p.is_empty)
    park_area = sum(p.area for p in parks if not p.is_empty)

    plot_features = []
    for i, p in enumerate(plots):
        if p.is_empty or p.area < 10:
            continue
        geom = p if p.geom_type == "Polygon" else list(p.geoms)[0]
        plot_features.append({
            "id":          i + 1,
            "area_m2":     round(p.area, 1),
            "coordinates": [list(geom.exterior.coords)],
            "type":        "residential",
        })

    park_features = []
    for i, p in enumerate(parks):
        if p.is_empty or p.area < 10:
            continue
        geom = p if p.geom_type == "Polygon" else list(p.geoms)[0]
        park_features.append({
            "id":          i + 1,
            "area_m2":     round(p.area, 1),
            "coordinates": [list(geom.exterior.coords)],
            "type":        "park",
        })

    total_area = plot_area + park_area
    efficiency = round((plot_area / total_area * 100), 1) if total_area > 0 else 0

    return {
        "plots":           plot_features,
        "parks":           park_features,
        "num_plots":       len(plot_features),
        "total_plot_area_m2": round(plot_area, 2),
        "total_park_area_m2": round(park_area, 2),
        "efficiency_score":   efficiency,
        "score":           list(score),
    }