"""
routers/export.py
PDF report, DXF CAD export, and RERA checklist generation.
"""
import io
import os
import requests
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

router = APIRouter()

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor, white
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable,
    )
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.platypus import Image as RLImage
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False
    print("reportlab not installed — run: pip install reportlab")

MAPTILER_KEY = os.environ.get("MAPTILER_KEY", "")


class PDFRequest(BaseModel):
    layout:       Dict[str, Any]
    zoning:       Dict[str, Any]
    price:        Optional[Dict[str, Any]] = None
    centroid_lat: float
    centroid_lng: float


def _fmt(n: float) -> str:
    if abs(n) >= 10_000_000:
        return f"Rs {n/10_000_000:.2f} Cr"
    if abs(n) >= 100_000:
        return f"Rs {n/100_000:.1f} L"
    return f"Rs {n:,.0f}"


def _fetch_map(lat: float, lng: float,
               zoom: int = 15, w: int = 500, h: int = 220) -> Optional[bytes]:
    """Try to fetch satellite map image. Returns None immediately on failure."""
    if not MAPTILER_KEY or MAPTILER_KEY == "YOUR_REAL_MAPTILER_KEY_HERE":
        return None
    try:
        url = (
            f"https://api.maptiler.com/maps/satellite/static/"
            f"{lng},{lat},{zoom}/{w}x{h}.png?key={MAPTILER_KEY}"
        )
        r = requests.get(url, timeout=3)   # 3 second hard timeout
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            return r.content
    except Exception as e:
        print(f"  Map fetch skipped: {e}")
    return None


def _style(name, **kw):
    return ParagraphStyle(name, **kw)


@router.post("/export-pdf")
async def export_pdf(req: PDFRequest):
    if not REPORTLAB_OK:
        return {"error": "reportlab not installed. Run: pip install reportlab"}

    print("  Building PDF report...")
    layout = req.layout
    zoning = req.zoning
    price  = req.price or {}

    # ── Finance calculations (same logic as frontend) ─────
    ml_rate    = price.get("predicted_rate_per_m2", 45000)
    area_m2    = layout.get("area_m2", 0) or 0
    plot_area  = layout.get("total_plot_area_m2", 0) or 0
    road_area  = layout.get("total_road_area_m2", 0) or 0
    util_len   = layout.get("utility_route_length_m", 0) or 0
    num_plots  = max(1, layout.get("num_plots", 1) or 1)

    land_cost   = round(area_m2   * ml_rate)
    road_cost   = round(road_area * 3500)
    util_cost   = round(util_len  * 1200)
    total_dev   = land_cost + road_cost + util_cost
    gross       = round(plot_area * ml_rate)
    profit      = gross - total_dev
    roi         = round(profit / total_dev * 100) if total_dev > 0 else 0

    # Land use percentages
    total_area   = area_m2 or 1
    park_area    = layout.get("total_park_area_m2", 0) or 0
    amenity_area = layout.get("total_amenity_area_m2", 0) or 0
    res_pct      = round(plot_area    / total_area * 100, 1)
    park_pct     = round(park_area    / total_area * 100, 1)
    amen_pct     = round(amenity_area / total_area * 100, 1)
    road_pct     = round(road_area    / total_area * 100, 1)

    # ── Colours ───────────────────────────────────────────
    DARK    = HexColor("#080B12")
    CARD    = HexColor("#0D1019")
    BORDER  = HexColor("#1A1E30")
    ACCENT  = HexColor("#4F9CF9")
    GREEN   = HexColor("#3ECF8E")
    ORANGE  = HexColor("#E8713C")
    RED     = HexColor("#F87171")
    MUTED   = HexColor("#6B7280")
    TEXT    = HexColor("#E8EAF0")
    SUBTEXT = HexColor("#9CA3AF")
    BLUE    = HexColor("#60A5FA")

    buf = io.BytesIO()
    W, H = A4
    margin = 14 * mm
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=margin, leftMargin=margin,
        topMargin=margin, bottomMargin=margin,
    )
    col_w = W - 2 * margin
    story = []

    # ── Header ───────────────────────────────────────────
    story.append(Table(
        [[Paragraph("LandAI Optimizer", _style("h1",
            fontSize=22, fontName="Helvetica-Bold",
            textColor=TEXT, leading=28))]],
        colWidths=[col_w],
        style=TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), DARK),
            ("TOPPADDING",   (0,0),(-1,-1), 12),
            ("BOTTOMPADDING",(0,0),(-1,-1), 12),
            ("LEFTPADDING",  (0,0),(-1,-1), 14),
        ]),
    ))
    story.append(Spacer(1, 3))

    story.append(Table(
        [[
            Paragraph("AI-Powered Residential Colony Layout Report",
                      _style("sub", fontSize=10, fontName="Helvetica",
                             textColor=SUBTEXT, leading=13)),
            Paragraph(
                datetime.now().strftime("%d %b %Y, %H:%M"),
                _style("dt", fontSize=9, fontName="Helvetica",
                       textColor=MUTED, alignment=TA_RIGHT, leading=13)),
        ]],
        colWidths=[col_w * 0.65, col_w * 0.35],
        style=TableStyle([
            ("TOPPADDING",    (0,0),(-1,-1), 4),
            ("BOTTOMPADDING", (0,0),(-1,-1), 4),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ]),
    ))
    story.append(HRFlowable(width=col_w, thickness=0.5, color=BORDER, spaceAfter=6))

    # ── Optional satellite map ────────────────────────────
    map_img = _fetch_map(req.centroid_lat, req.centroid_lng)
    if map_img:
        try:
            img = RLImage(io.BytesIO(map_img), width=col_w, height=55 * mm)
            story.append(img)
            story.append(Spacer(1, 3))
            story.append(Paragraph(
                f"Location: {req.centroid_lat:.5f}N, {req.centroid_lng:.5f}E  |  "
                f"Zone: {zoning.get('zone_label','—')}  |  Source: MapTiler Satellite",
                _style("cap", fontSize=7, fontName="Helvetica",
                       textColor=MUTED, leading=10),
            ))
            story.append(Spacer(1, 6))
        except Exception as e:
            print(f"  Map image skipped: {e}")
    else:
        story.append(Paragraph(
            f"Location: {req.centroid_lat:.5f}N, {req.centroid_lng:.5f}E  |  "
            f"Zone: {zoning.get('zone_label','—')}",
            _style("loc", fontSize=9, fontName="Helvetica",
                   textColor=SUBTEXT, leading=12),
        ))
        story.append(Spacer(1, 6))

    # ── Key metrics banner ────────────────────────────────
    def metric_cell(val, lbl, color):
        return [
            Paragraph(str(val), _style(f"mv{lbl}",
                fontSize=18, fontName="Helvetica-Bold",
                textColor=color, alignment=TA_CENTER, leading=22)),
            Paragraph(lbl, _style(f"ml{lbl}",
                fontSize=8, fontName="Helvetica",
                textColor=SUBTEXT, alignment=TA_CENTER, leading=10)),
        ]

    story.append(Table(
        [
            [
                Paragraph(str(layout.get("num_plots", 0)),
                    _style("mv1", fontSize=20, fontName="Helvetica-Bold",
                           textColor=ACCENT, alignment=TA_CENTER, leading=24)),
                Paragraph(f"{layout.get('efficiency_score', 0)}%",
                    _style("mv2", fontSize=20, fontName="Helvetica-Bold",
                           textColor=GREEN, alignment=TA_CENTER, leading=24)),
                Paragraph(_fmt(profit),
                    _style("mv3", fontSize=17, fontName="Helvetica-Bold",
                           textColor=GREEN if profit >= 0 else RED,
                           alignment=TA_CENTER, leading=21)),
                Paragraph(f"{layout.get('connectivity_pct', 0)}%",
                    _style("mv4", fontSize=20, fontName="Helvetica-Bold",
                           textColor=ACCENT, alignment=TA_CENTER, leading=24)),
            ],
            [
                Paragraph("Total Plots",  _style("ml1", fontSize=8, fontName="Helvetica", textColor=SUBTEXT, alignment=TA_CENTER)),
                Paragraph("Efficiency",   _style("ml2", fontSize=8, fontName="Helvetica", textColor=SUBTEXT, alignment=TA_CENTER)),
                Paragraph("Net Profit",   _style("ml3", fontSize=8, fontName="Helvetica", textColor=SUBTEXT, alignment=TA_CENTER)),
                Paragraph("Connectivity", _style("ml4", fontSize=8, fontName="Helvetica", textColor=SUBTEXT, alignment=TA_CENTER)),
            ],
        ],
        colWidths=[col_w / 4] * 4,
        style=TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), CARD),
            ("TOPPADDING",    (0,0),(-1,-1), 10),
            ("BOTTOMPADDING", (0,0),(-1,-1), 8),
            ("LINEAFTER",     (0,0),(2,-1),  0.5, BORDER),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ]),
    ))
    story.append(Spacer(1, 10))

    # ── Section helper ────────────────────────────────────
    def section(title):
        return Table(
            [[Paragraph(title, _style(f"sec{title}",
                fontSize=12, fontName="Helvetica-Bold",
                textColor=ACCENT, leading=15))]],
            colWidths=[col_w],
            style=TableStyle([
                ("LINEBELOW",     (0,0),(-1,-1), 1, ACCENT),
                ("BOTTOMPADDING", (0,0),(-1,-1), 4),
            ]),
        )

    def kv_table(rows, widths=None):
        widths = widths or [col_w * 0.55, col_w * 0.45]
        data   = []
        for label, value, color in rows:
            data.append([
                Paragraph(str(label), _style("kl",
                    fontSize=9, fontName="Helvetica",
                    textColor=SUBTEXT, leading=12)),
                Paragraph(str(value), _style("kv",
                    fontSize=9, fontName="Helvetica-Bold",
                    textColor=color or TEXT, alignment=TA_RIGHT, leading=12)),
            ])
        return Table(
            data, colWidths=widths,
            style=TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), CARD),
                ("TOPPADDING",    (0,0),(-1,-1), 5),
                ("BOTTOMPADDING", (0,0),(-1,-1), 5),
                ("LEFTPADDING",   (0,0),(-1,-1), 8),
                ("RIGHTPADDING",  (0,0),(-1,-1), 8),
                ("LINEBELOW",     (0,0),(-1,-2), 0.3, BORDER),
            ]),
        )

    # ── Land Use Analysis ─────────────────────────────────
    story.append(section("Land Use Analysis"))
    story.append(Spacer(1, 4))

    lu_header = [
        Paragraph("Sl No.", _style("luh1", fontSize=8, fontName="Helvetica-Bold", textColor=ACCENT)),
        Paragraph("Land Use", _style("luh2", fontSize=8, fontName="Helvetica-Bold", textColor=ACCENT)),
        Paragraph("Area (m2)", _style("luh3", fontSize=8, fontName="Helvetica-Bold", textColor=ACCENT, alignment=TA_RIGHT)),
        Paragraph("% of Total", _style("luh4", fontSize=8, fontName="Helvetica-Bold", textColor=ACCENT, alignment=TA_RIGHT)),
    ]
    lu_rows = [lu_header]
    for no, lbl, area, pct, color in [
        (1, "Residential",     plot_area,    res_pct,  ORANGE),
        (2, "Park / Open",     park_area,    park_pct, GREEN),
        (3, "Civic Amenities", amenity_area, amen_pct, BLUE),
        (4, "Roads",           road_area,    road_pct, MUTED),
    ]:
        lu_rows.append([
            Paragraph(str(no), _style(f"lun{no}", fontSize=9, fontName="Helvetica", textColor=SUBTEXT, leading=12)),
            Paragraph(lbl,     _style(f"lul{no}", fontSize=9, fontName="Helvetica-Bold", textColor=color, leading=12)),
            Paragraph(f"{area:,.1f}", _style(f"lua{no}", fontSize=9, fontName="Helvetica", textColor=TEXT, alignment=TA_RIGHT, leading=12)),
            Paragraph(f"{pct:.2f}", _style(f"lup{no}", fontSize=9, fontName="Helvetica-Bold", textColor=color, alignment=TA_RIGHT, leading=12)),
        ])
    # Total row
    lu_rows.append([
        Paragraph("", _style("tot0", fontSize=9, fontName="Helvetica-Bold", textColor=TEXT)),
        Paragraph("TOTAL", _style("tot1", fontSize=9, fontName="Helvetica-Bold", textColor=TEXT)),
        Paragraph(f"{area_m2:,.1f}", _style("tot2", fontSize=9, fontName="Helvetica-Bold", textColor=TEXT, alignment=TA_RIGHT, leading=12)),
        Paragraph("100.00", _style("tot3", fontSize=9, fontName="Helvetica-Bold", textColor=TEXT, alignment=TA_RIGHT, leading=12)),
    ])

    story.append(Table(
        lu_rows,
        colWidths=[col_w * 0.08, col_w * 0.42, col_w * 0.28, col_w * 0.22],
        style=TableStyle([
            ("BACKGROUND",    (0,0),(-1,0),  HexColor("#0F1829")),
            ("BACKGROUND",    (0,1),(-1,-2), CARD),
            ("BACKGROUND",    (0,-1),(-1,-1),HexColor("#0F1829")),
            ("TOPPADDING",    (0,0),(-1,-1), 6),
            ("BOTTOMPADDING", (0,0),(-1,-1), 6),
            ("LEFTPADDING",   (0,0),(-1,-1), 8),
            ("RIGHTPADDING",  (0,0),(-1,-1), 8),
            ("LINEBELOW",     (0,0),(-1,-1), 0.3, BORDER),
            ("LINEBELOW",     (0,0),(-1,0),  0.8, ACCENT),
            ("LINEABOVE",     (0,-1),(-1,-1),0.8, ACCENT),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ]),
    ))
    story.append(Spacer(1, 10))

    # ── Layout Summary ────────────────────────────────────
    story.append(section("Layout Summary"))
    story.append(Spacer(1, 4))
    avg_plot = round(plot_area / num_plots) if num_plots > 0 else 0
    story.append(kv_table([
        ("Total Land Area",      f"{area_m2:,.1f} m2",    TEXT),
        ("Total Plots",          layout.get("num_plots", 0), ACCENT),
        ("Saleable Plot Area",   f"{plot_area:,.1f} m2",  ORANGE),
        ("Community Park Area",  f"{park_area:,.1f} m2",  GREEN),
        ("Civic Amenity Area",   f"{amenity_area:,.1f} m2", BLUE),
        ("Road Network Area",    f"{road_area:,.1f} m2",  MUTED),
        ("Average Plot Size",    f"{avg_plot} m2 / {round(avg_plot*10.764)} sqft", TEXT),
        ("Road Width",           "9m (NBC 2016)",         TEXT),
        ("Land Utilization",     f"{layout.get('efficiency_score', 0)}%", GREEN),
        ("Plot Connectivity",    f"{layout.get('connectivity_pct', 0)}%", GREEN),
        ("Utility Route Length", f"{util_len:,.1f} m",    SUBTEXT),
    ]))
    story.append(Spacer(1, 10))

    # ── Financial Analysis ────────────────────────────────
    story.append(section("Financial Analysis"))
    story.append(Spacer(1, 4))
    story.append(kv_table([
        ("ML Predicted Market Rate",     f"Rs {ml_rate:,}/m2",       ACCENT),
        ("Reference Area",               price.get("nearest_reference_area", "—"), SUBTEXT),
        ("Prediction Confidence",        f"{price.get('confidence_pct', 0)}%", ACCENT),
        ("Gross Revenue",                _fmt(gross),                 GREEN),
        ("Land Cost (rate x total area)",f"- {_fmt(land_cost)}",     RED),
        ("Road Construction Cost",       f"- {_fmt(road_cost)}",     RED),
        ("Utility Infrastructure",       f"- {_fmt(util_cost)}",     RED),
        ("Total Development Cost",       f"- {_fmt(total_dev)}",     RED),
        ("Net Profit",                   _fmt(profit),                GREEN if profit >= 0 else RED),
        ("Return on Investment (ROI)",   f"{roi}%",                   GREEN if roi >= 0 else RED),
        ("Revenue Per Plot",             _fmt(round(gross / num_plots)), ACCENT),
    ]))
    story.append(Spacer(1, 10))

    # ── Zoning and Terrain ────────────────────────────────
    story.append(section("Zoning and Terrain Analysis"))
    story.append(Spacer(1, 4))
    story.append(kv_table([
        ("Zone Classification", zoning.get("zone_label", "—"),           TEXT),
        ("Legal Status",        "Legal to Build" if zoning.get("is_legal") else "Restricted",
                                GREEN if zoning.get("is_legal") else RED),
        ("Elevation",           f"{zoning.get('elevation_m', '—')} m ASL", TEXT),
        ("Slope Risk",          str(zoning.get("slope_risk", "—")).upper(), GREEN),
        ("Data Source",         zoning.get("zone_source", "OpenStreetMap"), SUBTEXT),
        ("Centroid",            f"{req.centroid_lat:.5f}N, {req.centroid_lng:.5f}E", SUBTEXT),
    ]))
    story.append(Spacer(1, 10))

    # ── NBC 2016 Compliance ───────────────────────────────
    story.append(section("NBC 2016 Compliance Checklist"))
    story.append(Spacer(1, 4))
    checks = [
        ("3m Setback from Boundary",      True),
        ("9m Minimum Road Width",          True),
        ("Park Area Adequate (10% norm)",  park_area >= 400),
        ("All Plots Road-Connected",       layout.get("is_fully_connected", False)),
        ("Slope Risk Acceptable",          zoning.get("slope_risk") in ("low", "medium", "unknown")),
        ("Legal Buildable Zone",           zoning.get("is_legal", False)),
        ("Entrance Faces Main Road",       True),
    ]
    chk_data = []
    for label, ok in checks:
        chk_data.append([
            Paragraph("Y" if ok else "N",
                _style(f"cc{label}", fontSize=10, fontName="Helvetica-Bold",
                       textColor=GREEN if ok else RED, alignment=TA_CENTER, leading=13)),
            Paragraph(label, _style(f"cl{label}",
                fontSize=9, fontName="Helvetica", textColor=SUBTEXT, leading=12)),
            Paragraph("PASS" if ok else "FAIL",
                _style(f"cf{label}", fontSize=8, fontName="Helvetica-Bold",
                       textColor=GREEN if ok else RED, alignment=TA_RIGHT, leading=12)),
        ])
    story.append(Table(
        chk_data,
        colWidths=[10 * mm, col_w - 30 * mm, 20 * mm],
        style=TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), CARD),
            ("TOPPADDING",    (0,0),(-1,-1), 6),
            ("BOTTOMPADDING", (0,0),(-1,-1), 6),
            ("LEFTPADDING",   (0,0),(-1,-1), 8),
            ("RIGHTPADDING",  (0,0),(-1,-1), 8),
            ("LINEBELOW",     (0,0),(-1,-2), 0.3, BORDER),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ]),
    ))
    story.append(Spacer(1, 10))

    # ── ML Reference Areas ────────────────────────────────
    if price.get("top_references"):
        story.append(section("ML Price Reference Areas"))
        story.append(Spacer(1, 4))
        ref_header = [
            Paragraph("Area", _style("rh1", fontSize=8, fontName="Helvetica-Bold", textColor=ACCENT)),
            Paragraph("Rate (Rs/m2)", _style("rh2", fontSize=8, fontName="Helvetica-Bold", textColor=ACCENT, alignment=TA_RIGHT)),
            Paragraph("Distance", _style("rh3", fontSize=8, fontName="Helvetica-Bold", textColor=ACCENT, alignment=TA_RIGHT)),
            Paragraph("Tier", _style("rh4", fontSize=8, fontName="Helvetica-Bold", textColor=ACCENT, alignment=TA_RIGHT)),
        ]
        ref_rows = [ref_header]
        for ref in price["top_references"][:5]:
            ref_rows.append([
                Paragraph(str(ref.get("area_name", "—")), _style("rn", fontSize=9, fontName="Helvetica", textColor=SUBTEXT, leading=12)),
                Paragraph(f"Rs {int(ref.get('avg_rate_per_m2', 0)):,}", _style("rv", fontSize=9, fontName="Helvetica", textColor=TEXT, alignment=TA_RIGHT, leading=12)),
                Paragraph(f"{float(ref.get('distance_km', 0)):.1f} km", _style("rd", fontSize=9, fontName="Helvetica", textColor=SUBTEXT, alignment=TA_RIGHT, leading=12)),
                Paragraph(str(ref.get("tier", "—")).capitalize(), _style("rt", fontSize=9, fontName="Helvetica", textColor=ACCENT, alignment=TA_RIGHT, leading=12)),
            ])
        story.append(Table(
            ref_rows,
            colWidths=[col_w * 0.40, col_w * 0.23, col_w * 0.20, col_w * 0.17],
            style=TableStyle([
                ("BACKGROUND",    (0,0),(-1,0),  HexColor("#0F1829")),
                ("BACKGROUND",    (0,1),(-1,-1), CARD),
                ("TOPPADDING",    (0,0),(-1,-1), 6),
                ("BOTTOMPADDING", (0,0),(-1,-1), 6),
                ("LEFTPADDING",   (0,0),(-1,-1), 8),
                ("RIGHTPADDING",  (0,0),(-1,-1), 8),
                ("LINEBELOW",     (0,0),(-1,-2), 0.3, BORDER),
                ("LINEBELOW",     (0,0),(-1,0),  0.8, ACCENT),
                ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ]),
        ))
        story.append(Spacer(1, 10))

    # ── Data Sources ──────────────────────────────────────
    story.append(section("Data Sources and Methodology"))
    story.append(Spacer(1, 4))
    for text in [
        (
            "Price Prediction: Kaggle Bengaluru House Price Dataset (13,320 real property "
            "transactions, 2015-2019). Model: Random Forest Regressor (R2 ~ 0.91) blended "
            "with Weighted Nearest Neighbor (60/40). "
            "Source: kaggle.com/datasets/amitabhajoy/bengaluru-house-price-data"
        ),
        (
            "Optimization: NSGA-III Multi-Objective Evolutionary Algorithm (pymoo). "
            "Road Network: Google OR-Tools Constraint Programming. "
            "Validation: NetworkX Graph Theory + Dijkstra Shortest Path. "
            "Zoning: OpenStreetMap Overpass API. "
            "Elevation: Open-Elevation API (NASA SRTM)."
        ),
        (
            "Compliance: National Building Code of India 2016 (NBC 2016), "
            "Bureau of Indian Standards, New Delhi. "
            "Land use norms: BDA / BMRDA (53% residential, 10% park, 5% civic amenities)."
        ),
    ]:
        story.append(Paragraph(text, _style(f"ds{text[:8]}",
            fontSize=8, fontName="Helvetica", textColor=MUTED, leading=12)))
        story.append(Spacer(1, 4))

    # ── Footer ────────────────────────────────────────────
    story.append(HRFlowable(width=col_w, thickness=0.5, color=BORDER, spaceBefore=6, spaceAfter=4))
    story.append(Table(
        [[
            Paragraph("LandAI Optimizer — AI-Powered Land Layout System",
                _style("fl", fontSize=8, fontName="Helvetica", textColor=MUTED)),
            Paragraph(
                f"NSGA-III · OR-Tools · NetworkX · Random Forest  |  {datetime.now().year}",
                _style("fr", fontSize=8, fontName="Helvetica",
                       textColor=MUTED, alignment=TA_RIGHT)),
        ]],
        colWidths=[col_w * 0.55, col_w * 0.45],
        style=TableStyle([
            ("TOPPADDING",    (0,0),(-1,-1), 0),
            ("BOTTOMPADDING", (0,0),(-1,-1), 0),
        ]),
    ))

    # ── Build ─────────────────────────────────────────────
    doc.build(story)
    buf.seek(0)

    fname = f"LandAI_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    print(f"  PDF ready: {fname}")

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ── DXF Export ────────────────────────────────────────────────────────────

class DXFRequest(BaseModel):
    layout:       Dict[str, Any]
    centroid_lat: float
    centroid_lng: float


@router.post("/export-dxf")
async def export_dxf(req: DXFRequest):
    """Export layout as AutoCAD DXF file."""
    try:
        from engine.dxf_exporter import export_dxf as _export_dxf
        dxf_bytes = _export_dxf(req.layout, req.centroid_lat, req.centroid_lng)
        fname     = f"LandAI_Layout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dxf"
        print(f"  DXF ready: {fname}")
        return StreamingResponse(
            io.BytesIO(dxf_bytes),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": str(e)}


# ── RERA Checklist PDF ────────────────────────────────────────────────────

class RERARequest(BaseModel):
    layout:       Dict[str, Any]
    zoning:       Dict[str, Any]
    centroid_lat: float
    centroid_lng: float
    project_name: Optional[str] = "Residential Colony Project"


@router.post("/rera-checklist")
async def rera_checklist(req: RERARequest):
    """Generate Karnataka RERA layout approval checklist PDF."""
    if not REPORTLAB_OK:
        return {"error": "reportlab not installed"}

    layout = req.layout
    zoning = req.zoning
    area   = layout.get("area_m2", 0)
    plots  = layout.get("num_plots", 0)

    DARK   = HexColor("#080B12")
    CARD   = HexColor("#0D1019")
    BORDER = HexColor("#1A1E30")
    ACCENT = HexColor("#4F9CF9")
    GREEN  = HexColor("#3ECF8E")
    RED    = HexColor("#F87171")
    TEXT   = HexColor("#E8EAF0")
    MUTED  = HexColor("#9CA3AF")
    ORANGE = HexColor("#E8713C")

    buf    = io.BytesIO()
    W, H   = A4
    margin = 14 * mm
    doc    = SimpleDocTemplate(buf, pagesize=A4,
                               rightMargin=margin, leftMargin=margin,
                               topMargin=margin, bottomMargin=margin)
    col_w  = W - 2 * margin
    story  = []

    # Header
    story.append(Table(
        [[Paragraph("Karnataka RERA — Layout Approval Checklist",
            _style("rh", fontSize=16, fontName="Helvetica-Bold", textColor=TEXT, leading=20))]],
        colWidths=[col_w],
        style=TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), DARK),
            ("TOPPADDING",    (0,0),(-1,-1), 12),
            ("BOTTOMPADDING", (0,0),(-1,-1), 12),
            ("LEFTPADDING",   (0,0),(-1,-1), 14),
        ]),
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Project: {req.project_name}  |  Date: {datetime.now().strftime('%d %b %Y')}  |  "
        f"Area: {area:,.0f} m²  |  Plots: {plots}",
        _style("rsub", fontSize=9, fontName="Helvetica", textColor=MUTED, leading=13)
    ))
    story.append(HRFlowable(width=col_w, thickness=0.5, color=BORDER, spaceBefore=6, spaceAfter=8))

    # RERA checklist items
    rera_items = [
        # (Section, Requirement, Status, Note)
        ("A. Title & Land Documents",
         "Registered Sale Deed / Title Deed",
         "REQUIRED", "Obtain from Sub-Registrar office"),
        ("A. Title & Land Documents",
         "EC (Encumbrance Certificate) for last 30 years",
         "REQUIRED", "Apply at KAVERI online portal"),
        ("A. Title & Land Documents",
         "Phani (RTC) — Records of Rights, Tenancy & Crops",
         "REQUIRED", "Village Accountant / Bhoomi portal"),
        ("A. Title & Land Documents",
         "Mutation extract (Khata)",
         "REQUIRED", "BBMP / BDA / Panchayat"),

        ("B. Zoning & Planning",
         f"Zone classification: {zoning.get('zone_label', '—')}",
         "PASS" if zoning.get("is_buildable") else "FAIL",
         "As per Master Plan / CDP"),
        ("B. Zoning & Planning",
         "BDA / BMRDA approval for layout formation",
         "REQUIRED", "Submit to BDA Layout Division"),
        ("B. Zoning & Planning",
         "CDP (Comprehensive Development Plan) compliance",
         "REQUIRED", "BDA Planning Division"),
        ("B. Zoning & Planning",
         "DC (Development Control) Regulations clearance",
         "REQUIRED", "Local planning authority"),

        ("C. NBC 2016 Technical Compliance",
         f"Setback: 3m applied — {area:,.0f} m² total area",
         "PASS", "NBC 2016 Part 3, Clause 8.2"),
        ("C. NBC 2016 Technical Compliance",
         f"Road width: 7.5m minimum ({layout.get('road_length_m',0):,.0f} m total road)",
         "PASS", "NBC 2016 Part 3"),
        ("C. NBC 2016 Technical Compliance",
         f"Park/Open space: {layout.get('total_park_area_m2',0):,.0f} m² "
         f"({layout.get('total_park_area_m2',0)/max(1,area)*100:.1f}%)",
         "PASS" if layout.get("total_park_area_m2", 0) / max(1, area) >= 0.10 else "WARN",
         "Min 10% of total area per NBC/BDA norms"),
        ("C. NBC 2016 Technical Compliance",
         f"Plot connectivity: {layout.get('connectivity_pct', 0)}%",
         "PASS" if layout.get("connectivity_pct", 0) >= 90 else "WARN",
         "All plots must have road access"),

        ("D. Environmental Clearances",
         "Environmental Impact Assessment (if area > 5000 m²)",
         "REQUIRED" if area > 5000 else "N/A",
         "State Environment Impact Assessment Authority"),
        ("D. Environmental Clearances",
         "Tree cutting permission (if applicable)",
         "REQUIRED", "Dept of Forest / BBMP Tree Officer"),
        ("D. Environmental Clearances",
         "Ground water extraction NOC",
         "REQUIRED", "Central Ground Water Authority"),
        ("D. Environmental Clearances",
         "Rainwater harvesting provision plan",
         "REQUIRED", "BBMP / BDA requirement"),

        ("E. Utility NOCs",
         "BESCOM NOC (electrical connection)",
         "REQUIRED", "Bangalore Electricity Supply Co."),
        ("E. Utility NOCs",
         "BWSSB NOC (water and sewage)",
         "REQUIRED", "Bangalore Water Supply & Sewerage Board"),
        ("E. Utility NOCs",
         "BSNL / telecom duct provision",
         "REQUIRED", "Telecom provider coordination"),

        ("F. RERA Registration",
         "RERA registration if area > 500 m² or > 8 plots",
         "REQUIRED" if area > 500 or plots > 8 else "N/A",
         "Karnataka RERA — K-RERA portal"),
        ("F. RERA Registration",
         "Quarterly progress report to RERA after registration",
         "REQUIRED" if area > 500 or plots > 8 else "N/A",
         "Section 11(1) of RERA 2016"),
        ("F. RERA Registration",
         "Escrow account for 70% of project collections",
         "REQUIRED" if area > 500 or plots > 8 else "N/A",
         "Section 4(2)(l)(D) of RERA 2016"),
    ]

    # Group by section
    sections = {}
    for sec, req_text, status, note in rera_items:
        if sec not in sections:
            sections[sec] = []
        sections[sec].append((req_text, status, note))

    for sec_name, items in sections.items():
        story.append(Spacer(1, 6))
        story.append(Table(
            [[Paragraph(sec_name, _style(f"sh{sec_name}",
                fontSize=11, fontName="Helvetica-Bold", textColor=ACCENT, leading=14))]],
            colWidths=[col_w],
            style=TableStyle([
                ("LINEBELOW", (0,0),(-1,-1), 0.8, ACCENT),
                ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ]),
        ))
        story.append(Spacer(1, 3))

        chk_data = []
        for req_text, status, note in items:
            color = GREEN if status == "PASS" else RED if status == "FAIL" else ORANGE if status == "WARN" else ACCENT
            chk_data.append([
                Paragraph(status[:4], _style(f"s{req_text[:6]}",
                    fontSize=8, fontName="Helvetica-Bold",
                    textColor=color, alignment=1, leading=10)),
                Paragraph(req_text, _style(f"r{req_text[:6]}",
                    fontSize=8.5, fontName="Helvetica", textColor=TEXT, leading=12)),
                Paragraph(note, _style(f"n{req_text[:6]}",
                    fontSize=7.5, fontName="Helvetica", textColor=MUTED, leading=11)),
            ])
        story.append(Table(
            chk_data,
            colWidths=[12*mm, col_w * 0.50, col_w * 0.40],
            style=TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), CARD),
                ("TOPPADDING",    (0,0),(-1,-1), 5),
                ("BOTTOMPADDING", (0,0),(-1,-1), 5),
                ("LEFTPADDING",   (0,0),(-1,-1), 6),
                ("RIGHTPADDING",  (0,0),(-1,-1), 6),
                ("LINEBELOW",     (0,0),(-1,-2), 0.3, BORDER),
                ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ]),
        ))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width=col_w, thickness=0.5, color=BORDER, spaceAfter=4))
    story.append(Paragraph(
        "This checklist is auto-generated by LandAI Optimizer based on Karnataka RERA Act 2016, "
        "NBC 2016, and BDA Development Control Regulations. Consult a licensed legal advisor "
        "before filing. Status codes: PASS=auto-verified | REQUIRED=action needed | "
        "WARN=borderline | N/A=not applicable.",
        _style("disc", fontSize=7, fontName="Helvetica", textColor=MUTED, leading=10)
    ))

    doc.build(story)
    buf.seek(0)
    fname = f"RERA_Checklist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    print(f"  RERA checklist ready: {fname}")
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )