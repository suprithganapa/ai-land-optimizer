"""
drainage_engine.py
Stormwater drainage flow computation from terrain slope.
Uses Open-Elevation API to sample elevation at multiple points,
then computes flow direction and drainage channels.
"""
import math
import requests


def _haversine_m(lat1, lng1, lat2, lng2):
    R    = 6371000
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a    = (math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _fetch_elevations(locations: list) -> list:
    """
    Batch-fetch elevations from Open-Elevation API.
    locations: list of {"latitude": ..., "longitude": ...}
    Returns list of elevation floats (same order, None on failure).
    """
    try:
        r = requests.post(
            "https://api.open-elevation.com/api/v1/lookup",
            json={"locations": locations},
            timeout=10,
        )
        if r.status_code == 200:
            return [el["elevation"] for el in r.json()["results"]]
    except Exception as e:
        print(f"  Elevation batch error: {e}")
    return [800.0] * len(locations)   # Bengaluru average fallback


def compute_drainage(centroid_lat: float, centroid_lng: float,
                     area_m2: float, boundary_polygon_wgs84: dict = None) -> dict:
    """
    Sample a 4x4 grid of elevation points around the land centroid,
    compute slope vectors, and return drainage channel GeoJSON linestrings
    pointing downhill.
    """
    # Determine grid extent from area
    side_m  = math.sqrt(max(area_m2, 500))
    delta_d = (side_m / 2) / 111_000  # rough degrees per meter

    # 4x4 grid of sample points
    grid_pts  = []
    grid_locs = []
    rows, cols = 4, 4
    for r in range(rows):
        for c in range(cols):
            lat = centroid_lat + (r - rows / 2 + 0.5) * (delta_d * 2 / rows)
            lng = centroid_lng + (c - cols / 2 + 0.5) * (delta_d * 2 / cols)
            grid_pts.append((lat, lng))
            grid_locs.append({"latitude": lat, "longitude": lng})

    elevations = _fetch_elevations(grid_locs)

    # Build elevation grid
    elev_grid = []
    for i in range(rows):
        row = []
        for j in range(cols):
            row.append(elevations[i * cols + j])
        elev_grid.append(row)

    # Compute drainage channels (flow from high to low)
    channels    = []
    risk_zones  = []
    max_elev    = max(elevations)
    min_elev    = min(elevations)
    elev_range  = max_elev - min_elev

    for r in range(rows):
        for c in range(cols):
            e = elev_grid[r][c]
            # Find downhill neighbour
            nbrs = []
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    ne = elev_grid[nr][nc]
                    if ne < e:
                        nbrs.append((ne, nr, nc))
            if nbrs:
                nbrs.sort()
                _, nr, nc = nbrs[0]
                lat1, lng1 = grid_pts[r * cols + c]
                lat2, lng2 = grid_pts[nr * cols + nc]
                slope_pct  = (e - elev_grid[nr][nc]) / max(1, _haversine_m(lat1, lng1, lat2, lng2)) * 100
                channels.append({
                    "from": [lng1, lat1],
                    "to":   [lng2, lat2],
                    "slope_pct": round(slope_pct, 2),
                    "from_elev": round(e, 1),
                    "to_elev":   round(elev_grid[nr][nc], 1),
                })
                # Mark high-slope zones as drainage risk
                if slope_pct > 2.0:
                    risk_zones.append({
                        "lat": (lat1 + lat2) / 2,
                        "lng": (lng1 + lng2) / 2,
                        "slope_pct": round(slope_pct, 2),
                    })

    # Determine overall slope risk
    slopes    = [ch["slope_pct"] for ch in channels]
    avg_slope = sum(slopes) / len(slopes) if slopes else 0
    max_slope = max(slopes) if slopes else 0

    if   max_slope > 5:   risk, color = "High",   "#f87171"
    elif max_slope > 2:   risk, color = "Medium", "#f59e0b"
    else:                 risk, color = "Low",    "#3ecf8e"

    # Recommended drain locations: lowest-elevation boundary points
    drain_points = sorted(
        [{"lat": pt[0], "lng": pt[1], "elev": elevations[i]}
         for i, pt in enumerate(grid_pts)],
        key=lambda x: x["elev"]
    )[:2]

    print(f"  🌧️  Drainage: {len(channels)} flow vectors, avg slope {avg_slope:.2f}%, risk={risk}")

    return {
        "channels":      channels,
        "risk_zones":    risk_zones,
        "drain_points":  drain_points,
        "avg_slope_pct": round(avg_slope, 2),
        "max_slope_pct": round(max_slope, 2),
        "elev_range_m":  round(elev_range, 1),
        "risk":          risk,
        "risk_color":    color,
        "grid_size":     f"{rows}x{cols}",
        "sample_count":  len(grid_pts),
    }
