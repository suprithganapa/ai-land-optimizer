"""
dxf_exporter.py
Export layout plots, roads, and parks as a DXF CAD file using ezdxf.
Architects can open this directly in AutoCAD / DraftSight / LibreCAD.
"""
import io

try:
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    EZDXF_OK = True
except ImportError:
    EZDXF_OK = False
    print("ezdxf not installed — run: pip install ezdxf")


def _wgs84_to_local(coords_lnglat: list, origin_lng: float, origin_lat: float):
    """
    Convert WGS84 [lng, lat] pairs to local metric coords (metres from origin).
    Simple equirectangular projection — accurate enough for small sites.
    """
    import math
    out = []
    lat_m = 111_000
    lng_m = 111_000 * math.cos(math.radians(origin_lat))
    for c in coords_lnglat:
        x = (c[0] - origin_lng) * lng_m
        y = (c[1] - origin_lat) * lat_m
        out.append((x, y))
    return out


def export_dxf(layout: dict, centroid_lat: float, centroid_lng: float) -> bytes:
    """
    Build and return DXF file bytes.
    layout: the generate-layout response dict (WGS84 coordinates).
    """
    if not EZDXF_OK:
        raise RuntimeError("ezdxf not installed. Run: pip install ezdxf")

    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = 6     # Metres
    doc.header["$LUNITS"]   = 2     # Decimal

    msp = doc.modelspace()

    # ── Layers ────────────────────────────────────────────
    layer_defs = [
        ("PLOTS",     1,  "continuous"),   # red
        ("ROADS",     8,  "continuous"),   # grey
        ("PARKS",     3,  "continuous"),   # green
        ("BOUNDARY",  5,  "continuous"),   # blue
        ("LABELS",    7,  "continuous"),   # white
        ("ENTRANCE",  2,  "continuous"),   # yellow
        ("AMENITIES", 4,  "continuous"),   # cyan
    ]
    for lname, color, lt in layer_defs:
        if lname not in doc.layers:
            doc.layers.new(name=lname, dxfattribs={"color": color, "linetype": lt})

    olng, olat = centroid_lng, centroid_lat

    def add_polygon(layer: str, coords_lnglat: list, close: bool = True):
        local = _wgs84_to_local(coords_lnglat, olng, olat)
        if not local or len(local) < 2:
            return
        if close and local[0] != local[-1]:
            local.append(local[0])
        msp.add_lwpolyline(local, dxfattribs={"layer": layer, "closed": close})

    def add_text(layer: str, text: str, x: float, y: float, height: float = 0.5):
        msp.add_text(
            text,
            dxfattribs={
                "layer":  layer,
                "height": height,
                "insert": (x, y),
                "halign": 1,  # centre
                "valign": 1,  # middle
            },
        )

    # ── Plots ─────────────────────────────────────────────
    for plot in layout.get("plots", []):
        ring = plot.get("coordinates", [[]])[0]
        if not ring or len(ring) < 3:
            continue
        add_polygon("PLOTS", ring)

        # Label at centroid
        clnglat = plot.get("centroid_lnglat") or plot.get("centroid_lng_lat")
        if clnglat and len(clnglat) >= 2:
            cx, cy = _wgs84_to_local([clnglat], olng, olat)[0]
            add_text("LABELS", f"P{plot.get('id','')}\n{plot.get('area_sqft','')}sqft",
                     cx, cy, height=0.4)

    # ── Roads ─────────────────────────────────────────────
    for road in layout.get("roads", []):
        ring = road.get("coordinates", [[]])[0]
        if not ring or len(ring) < 3:
            continue
        add_polygon("ROADS", ring)

    # ── Parks ─────────────────────────────────────────────
    for park in layout.get("parks", []):
        ring = park.get("coordinates", [[]])[0]
        if not ring or len(ring) < 3:
            continue
        add_polygon("PARKS", ring)
        # Park label
        xs = [c[0] for c in ring]
        ys = [c[1] for c in ring]
        cx_lng = sum(xs) / len(xs)
        cy_lat = sum(ys) / len(ys)
        cx, cy = _wgs84_to_local([[cx_lng, cy_lat]], olng, olat)[0]
        add_text("LABELS", "PARK", cx, cy, height=0.6)

    # ── Entrance ──────────────────────────────────────────
    entrance = layout.get("entrance")
    if entrance and len(entrance) >= 2:
        ex, ey = _wgs84_to_local([entrance], olng, olat)[0]
        msp.add_circle((ex, ey), radius=1.5, dxfattribs={"layer": "ENTRANCE"})
        add_text("LABELS", "ENTRANCE", ex, ey - 2.5, height=0.5)

    # ── Title block ───────────────────────────────────────
    msp.add_text(
        "LandAI Optimizer — Auto-Generated Layout",
        dxfattribs={"layer": "LABELS", "height": 1.2, "insert": (0, -8)},
    )
    msp.add_text(
        f"Plots: {layout.get('num_plots',0)}  |  "
        f"Efficiency: {layout.get('efficiency_score',0)}%  |  "
        f"Connectivity: {layout.get('connectivity_pct',0)}%",
        dxfattribs={"layer": "LABELS", "height": 0.6, "insert": (0, -10)},
    )

    # ── Serialize ─────────────────────────────────────────
    buf = io.BytesIO()
    doc.write(buf)
    buf.seek(0)
    return buf.read()
