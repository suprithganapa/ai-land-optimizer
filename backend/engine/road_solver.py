import math
from shapely.geometry import box, LineString, Point
from shapely.ops import unary_union


# ---------------------------------------------------------------------------
# Road Network
# ---------------------------------------------------------------------------

def generate_road_network(setback_polygon, constraints: dict) -> dict:
    road_width   = constraints.get("min_road_width_m", 7.5)
    minx, miny, maxx, maxy = setback_polygon.bounds
    height = maxy - miny
    cx     = (minx + maxx) / 2

    roads = []

    # Spine road (vertical, through centroid)
    spine = box(cx - road_width / 2, miny, cx + road_width / 2, maxy)
    spine = spine.intersection(setback_polygon)
    if not spine.is_empty:
        roads.append({"type": "spine", "geometry": spine, "width_m": road_width})

    # Branch roads (horizontal)
    num_branches = max(1, int(height / 25))
    spacing      = height / (num_branches + 1)
    for i in range(1, num_branches + 1):
        y      = miny + i * spacing
        branch = box(minx, y - road_width / 2, maxx, y + road_width / 2)
        branch = branch.intersection(setback_polygon)
        if not branch.is_empty:
            roads.append({"type": "branch", "geometry": branch, "width_m": road_width})

    if not roads:
        fallback = box(minx, (miny + maxy) / 2 - road_width / 2,
                       maxx, (miny + maxy) / 2 + road_width / 2)
        fallback = fallback.intersection(setback_polygon)
        if not fallback.is_empty:
            roads.append({"type": "branch", "geometry": fallback, "width_m": road_width})

    road_union = unary_union([r["geometry"] for r in roads if not r["geometry"].is_empty])
    entrance   = [cx, miny]  # bottom centre, faces main road

    road_features = []
    for r in roads:
        geom = r["geometry"]
        if geom.is_empty:
            continue
        g      = geom if geom.geom_type == "Polygon" else list(geom.geoms)[0]
        coords = [list(c) for c in g.exterior.coords]
        road_features.append({
            "type":        r["type"],
            "coordinates": [coords],
            "width_m":     r["width_m"],
        })

    total_road_area = round(road_union.area, 2) if not road_union.is_empty else 0.0
    road_length     = round(
        sum(LineString(r["geometry"].exterior.coords).length / 4
            for r in roads if not r["geometry"].is_empty), 2)

    centerlines   = _build_centerlines(roads)
    intersections = _find_intersections(roads, entrance)

    print(f"  Roads: {len(road_features)} segments, "
          f"area={total_road_area:.1f} m2, length~{road_length:.1f} m")

    return {
        "roads":              road_features,
        "road_union":         road_union,
        "road_objects":       roads,
        "centerlines":        centerlines,
        "intersections":      intersections,
        "entrance":           entrance,
        "total_road_area_m2": total_road_area,
        "road_length_m":      road_length,
    }


def _build_centerlines(roads):
    lines = []
    for r in roads:
        geom = r["geometry"]
        if geom.is_empty:
            continue
        b = geom.bounds
        if r["type"] == "spine":
            cx = (b[0] + b[2]) / 2
            lines.append(LineString([(cx, b[1]), (cx, b[3])]))
        else:
            cy = (b[1] + b[3]) / 2
            lines.append(LineString([(b[0], cy), (b[2], cy)]))
    return lines


def _find_intersections(roads, entrance):
    pts     = [tuple(entrance)]
    spines  = [r for r in roads if r["type"] == "spine"]
    branches = [r for r in roads if r["type"] == "branch"]
    for sp in spines:
        sb  = sp["geometry"].bounds
        scx = (sb[0] + sb[2]) / 2
        for br in branches:
            bb  = br["geometry"].bounds
            bcy = (bb[1] + bb[3]) / 2
            pts.append((scx, bcy))
    return pts


def _perp(line):
    coords  = list(line.coords)
    if len(coords) < 2:
        return 0.0, 1.0
    x1, y1 = coords[0]
    x2, y2 = coords[-1]
    dx, dy  = x2 - x1, y2 - y1
    length  = math.hypot(dx, dy) or 1.0
    return -dy / length, dx / length


# ---------------------------------------------------------------------------
# Infrastructure Generation
# ---------------------------------------------------------------------------

def generate_infrastructure(road_result: dict, setback_polygon,
                             plot_centroids: list) -> dict:
    centerlines   = road_result["centerlines"]
    intersections = road_result["intersections"]
    entrance      = road_result["entrance"]
    road_width    = 7.5

    bounds = setback_polygon.bounds
    minx, miny, maxx, maxy = bounds

    # ------------------------------------------------------------------
    # 1. Streetlights  (points along both sides of every road, 20 m apart)
    # ------------------------------------------------------------------
    streetlights = []
    for line in centerlines:
        length = line.length
        n_pts  = max(2, int(length / 20))
        dx, dy = _perp(line)
        offset = road_width / 2 + 0.5
        for i in range(n_pts + 1):
            t  = i / max(n_pts, 1)
            pt = line.interpolate(t, normalized=True)
            streetlights.append([pt.x + dx * offset, pt.y + dy * offset])
            streetlights.append([pt.x - dx * offset, pt.y - dy * offset])

    # ------------------------------------------------------------------
    # 2. Sewage system
    # ------------------------------------------------------------------
    pipe_offset       = road_width / 2 + 1.2
    sewage_pipe_lines = []
    for line in centerlines:
        dx, dy  = _perp(line)
        coords  = list(line.coords)
        left    = [[c[0] + dx * pipe_offset, c[1] + dy * pipe_offset] for c in coords]
        right   = [[c[0] - dx * pipe_offset, c[1] - dy * pipe_offset] for c in coords]
        if len(left) >= 2:
            sewage_pipe_lines.append(left)
            sewage_pipe_lines.append(right)

    # Sewage treatment plant at far corner
    stp_x = maxx - 10 if entrance[0] < (minx + maxx) / 2 else minx + 10
    stp_y = maxy - 10
    sewage_treatment_plant = [stp_x, stp_y]

    # Collector mains: end of each sewage line to STP
    collector_pipes = []
    for pipe in sewage_pipe_lines:
        collector_pipes.append([pipe[-1], sewage_treatment_plant])

    # ------------------------------------------------------------------
    # 3. Water system
    # ------------------------------------------------------------------
    water_tank = [entrance[0] + 12, entrance[1] + 8]

    # Water main along spine centerline
    water_main_lines = []
    if centerlines:
        coords = list(centerlines[0].coords)
        water_main_lines.append([[c[0] + 1.8, c[1]] for c in coords])

    # Branch pipes: spine main to each plot centroid
    water_branch_pipes = []
    if water_main_lines:
        main_line = LineString(water_main_lines[0])
        for pc in plot_centroids:
            nearest = main_line.interpolate(main_line.project(Point(pc)))
            water_branch_pipes.append([[nearest.x, nearest.y], list(pc)])

    # ------------------------------------------------------------------
    # 4. Electrical system
    # ------------------------------------------------------------------
    main_transformer = [entrance[0] - 6, entrance[1] + 6]
    dist_boards      = list(intersections)

    # HV cables: transformer to each distribution board
    hv_cables = []
    for db in dist_boards:
        hv_cables.append([list(main_transformer), list(db)])

    # LV cables: nearest distribution board to each plot centroid
    lv_cables = []
    if dist_boards:
        for pc in plot_centroids:
            nearest_db = min(dist_boards, key=lambda d: math.dist(d, pc))
            lv_cables.append([list(nearest_db), list(pc)])

    print(f"  Infrastructure: {len(streetlights)} streetlights, "
          f"{len(sewage_pipe_lines)} sewage pipes, "
          f"{len(water_branch_pipes)} water branches, "
          f"{len(lv_cables)} LV cables")

    return {
        "streetlights":           streetlights,
        "sewage_pipe_lines":      sewage_pipe_lines,
        "collector_pipes":        collector_pipes,
        "sewage_treatment_plant": sewage_treatment_plant,
        "water_tank":             water_tank,
        "water_main_lines":       water_main_lines,
        "water_branch_pipes":     water_branch_pipes,
        "main_transformer":       main_transformer,
        "distribution_boards":    dist_boards,
        "hv_cables":              hv_cables,
        "lv_cables":              lv_cables,
    }