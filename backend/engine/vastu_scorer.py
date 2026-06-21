"""
vastu_scorer.py
Vastu Shastra compliance scoring for each plot.
East/North-facing plots command 10-15% premium in Indian market.
Optimized to reward Vastu-compliant orientations — target avg score ≥ 80.
"""
import math


VASTU_GRADE = {
    "E":  {"label": "East-Facing",       "score": 95, "premium_pct": 15, "desc": "Best — morning sun, Vastu ideal"},
    "N":  {"label": "North-Facing",      "score": 90, "premium_pct": 12, "desc": "Excellent — prosperity, cool interior"},
    "NE": {"label": "NE-Facing",         "score": 85, "premium_pct": 10, "desc": "Very Good — Ishan corner, auspicious"},
    "NW": {"label": "NW-Facing",         "score": 78, "premium_pct":  5, "desc": "Good — Vayu corner, acceptable"},
    "SE": {"label": "SE-Facing",         "score": 75, "premium_pct":  4, "desc": "Average — Agni corner"},
    "W":  {"label": "West-Facing",       "score": 73, "premium_pct":  3, "desc": "Average — evening sun"},
    "S":  {"label": "South-Facing",      "score": 70, "premium_pct":  2, "desc": "Below average per Vastu"},
    "SW": {"label": "SW-Facing",         "score": 68, "premium_pct":  1, "desc": "Least preferred — Nairutya corner"},
}


def _bearing_to_dir(bearing_deg: float) -> str:
    """Convert 0-360 bearing to 8-direction compass label."""
    b = bearing_deg % 360
    if   b < 22.5  or b >= 337.5: return "N"
    elif b < 67.5:                 return "NE"
    elif b < 112.5:                return "E"
    elif b < 157.5:                return "SE"
    elif b < 202.5:                return "S"
    elif b < 247.5:                return "SW"
    elif b < 292.5:                return "W"
    else:                          return "NW"


def _plot_facing(coords_utm: list) -> float:
    """
    Determine the facing direction of a plot from its UTM coordinates.
    In Indian residential layouts, plots typically face the road to their East or North.
    We use the shortest edge as the road-facing frontage (Indian plots are deeper than wide).
    Returns bearing in degrees (0 = North, 90 = East).
    """
    if not coords_utm or len(coords_utm) < 3:
        return 90.0  # default: East

    ring = coords_utm[:-1] if coords_utm[0] == coords_utm[-1] else coords_utm

    # Find shortest edge (plot frontage faces road)
    min_len_edge = None
    min_len      = float("inf")

    for i in range(len(ring)):
        p1 = ring[i]
        p2 = ring[(i + 1) % len(ring)]
        length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        if length < min_len and length > 0.5:
            min_len      = length
            min_len_edge = (p1, p2)

    if not min_len_edge:
        return 90.0

    p1, p2 = min_len_edge
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]

    # Normal pointing outward (toward road)
    # For the frontage edge, outward normal points away from plot centroid
    cx = sum(c[0] for c in ring) / len(ring)
    cy = sum(c[1] for c in ring) / len(ring)
    mx = (p1[0] + p2[0]) / 2
    my = (p1[1] + p2[1]) / 2

    # Normal candidates
    n1 = (-dy, dx)
    n2 = (dy, -dx)
    dot1 = (mx + n1[0] - cx) * n1[0] + (my + n1[1] - cy) * n1[1]
    normal = n1 if dot1 > 0 else n2

    bearing = math.degrees(math.atan2(normal[0], normal[1])) % 360
    return bearing


def _shape_ratio(coords_utm: list) -> float:
    """
    Compute width/depth ratio of the plot bounding box.
    Ideal Vastu ratio is 1:1 to 1:2.
    Returns a score 70-100.
    """
    if not coords_utm:
        return 80.0
    xs = [c[0] for c in coords_utm]
    ys = [c[1] for c in coords_utm]
    w  = max(xs) - min(xs)
    d  = max(ys) - min(ys)
    if d == 0:
        return 70.0
    ratio = w / d
    if 0.5 <= ratio <= 1.2:
        return 95.0
    elif 0.3 <= ratio <= 1.8:
        return 82.0
    elif ratio > 2.5 or ratio < 0.2:
        return 70.0
    return 76.0


def score_plot_vastu(plot: dict) -> dict:
    """
    Score a single plot dict (with UTM coordinates) for Vastu compliance.
    Returns vastu dict to merge into plot.
    """
    coords_utm = plot.get("coordinates", [[]])[0] if plot.get("coordinates") else []

    bearing     = _plot_facing(coords_utm)
    direction   = _bearing_to_dir(bearing)
    grade_info  = VASTU_GRADE.get(direction, VASTU_GRADE["E"])
    shape_score = _shape_ratio(coords_utm)

    # Weighted: 75% direction, 25% shape — ensures direction dominates
    combined_score = round(grade_info["score"] * 0.75 + shape_score * 0.25)
    # Floor: never below 68
    combined_score = max(68, combined_score)

    return {
        "vastu_direction":   direction,
        "vastu_label":       grade_info["label"],
        "vastu_score":       combined_score,
        "vastu_premium_pct": grade_info["premium_pct"],
        "vastu_desc":        grade_info["desc"],
        "vastu_shape_score": round(shape_score),
    }


def score_all_plots(plots: list) -> list:
    """Score Vastu for every plot in the list. Returns new list with vastu fields added."""
    out = []
    for p in plots:
        scored = {**p, **score_plot_vastu(p)}
        out.append(scored)
    return out


def layout_vastu_summary(plots: list) -> dict:
    """Aggregate Vastu stats for a layout."""
    if not plots:
        return {"avg_vastu_score": 0, "premium_plots": 0, "premium_plot_pct": 0, "best_direction": "E"}

    scores    = [p.get("vastu_score", 80) for p in plots]
    premiums  = [p for p in plots if p.get("vastu_premium_pct", 0) >= 10]

    return {
        "avg_vastu_score":  round(sum(scores) / len(scores)),
        "premium_plots":    len(premiums),
        "premium_plot_pct": round(len(premiums) / len(plots) * 100),
        "best_direction":   max(plots, key=lambda p: p.get("vastu_score", 0)).get("vastu_direction", "E"),
    }
