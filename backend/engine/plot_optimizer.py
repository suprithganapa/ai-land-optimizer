import random
import math
from shapely.geometry import box, Polygon, Point, LinearRing
from shapely.ops import unary_union


PARETO_LABELS = ["Max Plots", "Balanced", "Max Green", "Min Cost", "Max Density"]

# NBC 2016 mandates >= 10% of layout area for parks/open space
NBC_MIN_PARK_PCT = 0.10

# Institutional sites reserved inside the colony
INSTITUTIONAL_LABELS = [
    "School Site",
    "Hospital / Clinic",
    "Community Hall",
    "Place of Worship",
]


def assign_phases(plots_out: list, entrance_utm: list) -> list:
    """
    Split plots into 3 development phases based on proximity to main entrance.
    Phase 1 = closest 40%, Phase 2 = next 35%, Phase 3 = remaining 25%.
    """
    if not plots_out or not entrance_utm:
        for p in plots_out:
            p["phase"] = 1
        return plots_out

    ex, ey = float(entrance_utm[0]), float(entrance_utm[1])

    for p in plots_out:
        cx, cy = float(p["centroid"][0]), float(p["centroid"][1])
        p["_dist"] = math.hypot(cx - ex, cy - ey)

    sorted_plots = sorted(plots_out, key=lambda p: p["_dist"])
    n   = len(sorted_plots)
    th1 = int(n * 0.40)
    th2 = int(n * 0.75)

    for i, p in enumerate(sorted_plots):
        if   i < th1: p["phase"] = 1
        elif i < th2: p["phase"] = 2
        else:         p["phase"] = 3
        del p["_dist"]

    return plots_out


def optimize_plots(setback_polygon, road_union, constraints: dict) -> dict:
    bounds   = setback_polygon.bounds
    minx, miny, maxx, maxy = bounds

    available = setback_polygon.difference(road_union)

    # NBC minimum park area = 10% of the full setback polygon area
    nbc_park_min = max(
        constraints.get("min_park_area_m2", 400),
        setback_polygon.area * NBC_MIN_PARK_PCT,
    )

    population = []
    for _ in range(80):
        layout = _random_layout(available, minx, miny, maxx, maxy, nbc_park_min, setback_polygon.area)
        if layout and len(layout["plots"]) > 0:
            population.append(layout)

    if not population:
        population = [_fallback_layout(available, nbc_park_min, bounds, setback_polygon.area)]

    scored = []
    for layout in population:
        score = _fitness(layout, setback_polygon.area, nbc_park_min)
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

    park_pct = round(best["total_park_area_m2"] / max(1, setback_polygon.area) * 100, 1)
    print(f"  NSGA-III: {len(population)} layouts, "
          f"Pareto={len(pareto)}, "
          f"Best: {best['num_plots']} plots, {best['efficiency_score']}%, "
          f"Park={park_pct}% (NBC min 10%)")

    return {
        "pareto_layouts":   results,
        "best_layout":      best,
        "total_candidates": len(population),
        "entrance_utm":     [setback_polygon.centroid.x, setback_polygon.bounds[1]],
    }


def _random_layout(available, minx, miny, maxx, maxy, nbc_park_min, total_area):
    plots        = []
    parks        = []
    inst_blocks  = []
    amenities    = []
    remain       = available

    width_range  = maxx - minx
    height_range = maxy - miny

    # ── 1. Allocate parks (NBC >= 10% of total area) ──────────────────────
    num_parks   = random.randint(1, 3)
    park_target = max(nbc_park_min, total_area * NBC_MIN_PARK_PCT)

    for k in range(num_parks):
        # Size each park so that together they hit park_target
        target_each = park_target / num_parks
        pw  = random.uniform(max(15, math.sqrt(target_each * 0.5)),
                             max(20, math.sqrt(target_each * 1.2)))
        ph  = max(15.0, target_each / pw)
        region_y = miny + (k / num_parks) * height_range
        px = random.uniform(minx + 2, max(minx + 3, maxx - pw - 2))
        py_min = region_y + 2
        py_max = min(region_y + height_range / num_parks - ph, maxy - ph - 2)
        if py_max <= py_min:
            py_max = py_min + 1
        py = random.uniform(py_min, py_max)
        park_shape = box(px, py, px + pw, py + ph).intersection(available)
        if not park_shape.is_empty and park_shape.area > 50:
            parks.append(park_shape)
            remain = remain.difference(park_shape)

    # If still under NBC minimum, add one more park to top up
    current_park_area = sum(p.area for p in parks)
    if current_park_area < park_target * 0.85:
        deficit = park_target - current_park_area
        extra_pw = random.uniform(12, 25)
        extra_ph = max(12.0, deficit / extra_pw)
        px = random.uniform(minx + 2, max(minx + 3, maxx - extra_pw - 2))
        py = random.uniform(miny + 2, max(miny + 3, maxy - extra_ph - 2))
        extra_park = box(px, py, px + extra_pw, py + extra_ph).intersection(remain)
        if not extra_park.is_empty and extra_park.area > 50:
            parks.append(extra_park)
            remain = remain.difference(extra_park)

    # Walking track around first park
    if parks:
        try:
            track = parks[0].boundary.buffer(1.5).difference(parks[0])
            track = track.intersection(available)
            if not track.is_empty and track.area > 5:
                amenities.append({"type": "walking_track", "geometry": track})
        except Exception:
            pass

    # ── 2. Reserve institutional / charitable sites (1-2 blocks) ─────────
    num_inst = random.randint(1, 2)
    # Place institutions in central/accessible locations
    cx = (minx + maxx) / 2
    cy = (miny + maxy) / 2
    for k in range(num_inst):
        # 800-1500 m² each — enough for a small school/clinic/community hall
        inst_w = random.uniform(25, 35)
        inst_h = random.uniform(28, 40)
        # Offset each institution so they don't overlap
        offset_x = (k * width_range  * 0.3) - (width_range  * 0.15)
        offset_y = (k * height_range * 0.25)
        ix = cx + offset_x - inst_w / 2
        iy = cy + offset_y - inst_h / 2
        # Keep inside bounds
        ix = max(minx + 2, min(ix, maxx - inst_w - 2))
        iy = max(miny + 2, min(iy, maxy - inst_h - 2))
        inst_shape = box(ix, iy, ix + inst_w, iy + inst_h).intersection(remain)
        if not inst_shape.is_empty and inst_shape.area > 300:
            label_idx = k % len(INSTITUTIONAL_LABELS)
            inst_blocks.append({
                "geometry": inst_shape,
                "label":    INSTITUTIONAL_LABELS[label_idx],
            })
            remain = remain.difference(inst_shape)

    # ── 3. Fill remaining area with residential plots ─────────────────────
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
    return {"plots": plots, "parks": parks, "inst_blocks": inst_blocks, "amenities": amenities}


def _fallback_layout(available, nbc_park_min, bounds, total_area):
    minx, miny, maxx, maxy = bounds
    plots, parks, inst_blocks, amenities = [], [], [], []

    park_target = max(nbc_park_min, total_area * NBC_MIN_PARK_PCT)
    pw = max(25.0, math.sqrt(park_target))
    ph = max(25.0, park_target / pw)
    park = box(minx + 2, miny + 2, minx + 2 + pw, miny + 2 + ph).intersection(available)
    if not park.is_empty and park.area > 50:
        parks.append(park)
        remain = available.difference(park)
    else:
        remain = available

    # One fallback institutional block
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    inst_shape = box(cx - 15, cy - 18, cx + 15, cy + 18).intersection(remain)
    if not inst_shape.is_empty and inst_shape.area > 200:
        inst_blocks.append({"geometry": inst_shape, "label": "Community Hall"})
        remain = remain.difference(inst_shape)

    x = minx + 2
    while x + 12 < maxx - 2:
        y = miny + 2 + ph + 2
        while y + 14 < maxy - 2:
            inter = remain.intersection(box(x, y, x + 12, y + 14))
            if not inter.is_empty and inter.area > 50:
                plots.append(inter)
            y += 15
        x += 13
    return {"plots": plots, "parks": parks, "inst_blocks": inst_blocks, "amenities": amenities}


def _fitness(layout, total_area, nbc_park_min):
    plot_area = sum(p.area for p in layout["plots"] if not p.is_empty)
    park_area = sum(p.area for p in layout["parks"] if not p.is_empty)
    num_plots = len(layout["plots"])

    # Heavy penalty if park area is below NBC 10% minimum
    park_ratio = park_area / max(1, total_area)
    park_penalty = max(0, NBC_MIN_PARK_PCT - park_ratio) * 10  # large multiplier

    obj1 = -(plot_area / max(1, total_area)) + park_penalty
    obj2 = -(num_plots / max(1, total_area / 100))
    obj3 = -(park_area / max(1, nbc_park_min))
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
        g         = p if p.geom_type == "Polygon" else list(p.geoms)[0]
        area_m2   = round(p.area, 1)
        area_sqft = round(area_m2 * 10.764, 1)
        plots_out.append({
            "id":          i + 1,
            "area_m2":     area_m2,
            "area_sqft":   area_sqft,
            "coordinates": [[list(c) for c in g.exterior.coords]],
            "type":        "residential",
            "centroid":    [g.centroid.x, g.centroid.y],
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

    inst_out = []
    for i, item in enumerate(layout.get("inst_blocks", [])):
        geom = item["geometry"]
        if geom.is_empty or geom.area < 50:
            continue
        g = geom if geom.geom_type == "Polygon" else list(geom.geoms)[0]
        inst_out.append({
            "id":          i + 1,
            "area_m2":     round(geom.area, 1),
            "coordinates": [[list(c) for c in g.exterior.coords]],
            "type":        "institutional",
            "label":       item["label"],
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
        "plots":              plots_out,
        "parks":              parks_out,
        "inst_blocks":        inst_out,
        "amenities":          amenities_out,
        "num_plots":          len(plots_out),
        "num_parks":          len(parks_out),
        "num_inst_blocks":    len(inst_out),
        "total_plot_area_m2": round(plot_area, 2),
        "total_park_area_m2": round(park_area, 2),
        "efficiency_score":   efficiency,
        "score":              list(score),
        "label":              label,
    }
