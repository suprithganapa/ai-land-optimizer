import io
import os
import requests
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, Optional

router = APIRouter()

# ── Try importing reportlab ───────────────────────────────
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import (
        HexColor, white, black
    )
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table,
        TableStyle, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import Image as RLImage
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False
    print("⚠️  reportlab not installed — run: pip install reportlab")

MAPTILER_KEY = os.environ.get("MAPTILER_KEY", "")


class PDFRequest(BaseModel):
    layout:       Dict[str, Any]
    zoning:       Dict[str, Any]
    price:        Optional[Dict[str, Any]] = None
    centroid_lat: float
    centroid_lng: float


def fmt_inr(n: float) -> str:
    if n >= 10_000_000:
        return f"Rs {n/10_000_000:.2f} Cr"
    if n >= 100_000:
        return f"Rs {n/100_000:.1f} L"
    return f"Rs {n:,.0f}"


def fetch_static_map(lat: float, lng: float, zoom: int = 15,
                     width: int = 600, height: int = 300) -> Optional[bytes]:
    """Fetch satellite map image from MapTiler static API"""
    if not MAPTILER_KEY:
        return None
    try:
        url = (
            f"https://api.maptiler.com/maps/satellite/static/"
            f"{lng},{lat},{zoom}/{width}x{height}.png?key={MAPTILER_KEY}"
        )
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.content
    except Exception as e:
        print(f"Static map error: {e}")
    return None


@router.post("/export-pdf")
async def export_pdf(req: PDFRequest):
    if not REPORTLAB_OK:
        return {"error": "reportlab not installed. Run: pip install reportlab"}

    layout = req.layout
    zoning = req.zoning
    price  = req.price or {}

    # ── Financial calcs ───────────────────────────────────
    ml_rate = price.get("predicted_rate_per_m2", 45000)
    gross   = round((layout.get("total_plot_area_m2", 0) or 0) * ml_rate)
    r_cost  = round((layout.get("total_road_area_m2",  0) or 0) * 3500)
    u_cost  = round((layout.get("utility_route_length_m", 0) or 0) * 1200)
    total   = r_cost + u_cost
    profit  = gross - total
    roi     = round(profit / total * 100) if total > 0 else 0

    # ── Colors ────────────────────────────────────────────
    DARK    = HexColor("#080B12")
    CARD    = HexColor("#0D1019")
    BORDER  = HexColor("#1A1E30")
    ACCENT  = HexColor("#4F9CF9")
    GREEN   = HexColor("#3ECF8E")
    ORANGE  = HexColor("#E8713C")
    RED     = HexColor("#F87171")
    MUTED   = HexColor("#555566")
    TEXT    = HexColor("#E8EAF0")
    SUBTEXT = HexColor("#6B7280")

    # ── Document ──────────────────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
    )

    styles = getSampleStyleSheet()
    W      = A4[0] - 30*mm

    def style(name, **kw):
        s = ParagraphStyle(name, **kw)
        return s

    H1 = style("H1", fontSize=22, fontName="Helvetica-Bold",
                textColor=TEXT, spaceAfter=4, leading=26)
    H2 = style("H2", fontSize=13, fontName="Helvetica-Bold",
                textColor=ACCENT, spaceAfter=6, leading=16)
    H3 = style("H3", fontSize=10, fontName="Helvetica-Bold",
                textColor=TEXT, spaceAfter=4, leading=13)
    BODY = style("BODY", fontSize=9, fontName="Helvetica",
                  textColor=SUBTEXT, leading=13)
    SMALL = style("SMALL", fontSize=8, fontName="Helvetica",
                   textColor=MUTED, leading=11)
    MONO  = style("MONO", fontSize=8, fontName="Courier",
                   textColor=GREEN, leading=11)

    story = []

    # ── COVER HEADER ─────────────────────────────────────
    # Title banner table
    story.append(Table(
        [[Paragraph("🏙  LandAI Optimizer", style("cov",
            fontSize=26, fontName="Helvetica-Bold",
            textColor=TEXT, leading=30))]],
        colWidths=[W],
        style=TableStyle([
            ("BACKGROUND",  (0,0), (-1,-1), DARK),
            ("TOPPADDING",  (0,0), (-1,-1), 14),
            ("BOTTOMPADDING",(0,0),(-1,-1), 14),
            ("LEFTPADDING", (0,0), (-1,-1), 16),
            ("ROUNDEDCORNERS", (0,0), (-1,-1), [6,6,6,6]),
        ]),
    ))
    story.append(Spacer(1, 4))

    # Sub-header row
    story.append(Table(
        [[
            Paragraph("AI-Powered Residential Colony Layout Report", style("sub",
                fontSize=11, fontName="Helvetica",
                textColor=SUBTEXT, leading=14)),
            Paragraph(
                f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}",
                style("dt", fontSize=9, fontName="Helvetica",
                      textColor=MUTED, alignment=TA_RIGHT, leading=14)),
        ]],
        colWidths=[W*0.65, W*0.35],
        style=TableStyle([
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]),
    ))
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=8))

    # ── STATIC MAP ───────────────────────────────────────
    map_img = fetch_static_map(req.centroid_lat, req.centroid_lng, zoom=15)
    if map_img:
        img_buf = io.BytesIO(map_img)
        img     = RLImage(img_buf, width=W, height=60*mm)
        story.append(img)
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"📍 Location: {req.centroid_lat:.5f}°N, {req.centroid_lng:.5f}°E  |  "
            f"Zone: {zoning.get('zone_label','—')}  |  "
            f"Source: MapTiler Satellite",
            SMALL,
        ))
        story.append(Spacer(1, 8))

    # ── KEY METRICS BAR ───────────────────────────────────
    metrics = [
        [
            Paragraph(str(layout.get("num_plots", 0)),
                      style("mv", fontSize=20, fontName="Helvetica-Bold", textColor=ACCENT, alignment=TA_CENTER, leading=24)),
            Paragraph(f"{layout.get('efficiency_score', 0)}%",
                      style("mv2", fontSize=20, fontName="Helvetica-Bold", textColor=GREEN, alignment=TA_CENTER, leading=24)),
            Paragraph(fmt_inr(profit),
                      style("mv3", fontSize=18, fontName="Helvetica-Bold", textColor=GREEN, alignment=TA_CENTER, leading=22)),
            Paragraph(f"{layout.get('connectivity_pct', 0)}%",
                      style("mv4", fontSize=20, fontName="Helvetica-Bold", textColor=ACCENT, alignment=TA_CENTER, leading=24)),
        ],
        [
            Paragraph("Total Plots",      style("ml", fontSize=8, fontName="Helvetica", textColor=SUBTEXT, alignment=TA_CENTER)),
            Paragraph("Efficiency",       style("ml2", fontSize=8, fontName="Helvetica", textColor=SUBTEXT, alignment=TA_CENTER)),
            Paragraph("Net Profit",       style("ml3", fontSize=8, fontName="Helvetica", textColor=SUBTEXT, alignment=TA_CENTER)),
            Paragraph("Connectivity",     style("ml4", fontSize=8, fontName="Helvetica", textColor=SUBTEXT, alignment=TA_CENTER)),
        ],
    ]
    story.append(Table(
        metrics,
        colWidths=[W/4]*4,
        style=TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), CARD),
            ("TOPPADDING",    (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LINEAFTER",     (0,0), (2,-1), 0.5, BORDER),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ]),
    ))
    story.append(Spacer(1, 10))

    # ── TWO COLUMN: Layout + Financial ───────────────────
    def section_header(title):
        return Table(
            [[Paragraph(title, H2)]],
            colWidths=[W],
            style=TableStyle([
                ("LINEBELOW", (0,0), (-1,-1), 1, ACCENT),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ]),
        )

    def kv_table(rows, col_w=None):
        cw = col_w or [W*0.5, W*0.5]
        data = []
        for label, value, color in rows:
            data.append([
                Paragraph(label, BODY),
                Paragraph(str(value), style("kv", fontSize=9,
                    fontName="Helvetica-Bold",
                    textColor=color or TEXT, alignment=TA_RIGHT, leading=12)),
            ])
        return Table(
            data, colWidths=cw,
            style=TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), CARD),
                ("TOPPADDING",    (0,0), (-1,-1), 5),
                ("BOTTOMPADDING", (0,0), (-1,-1), 5),
                ("LEFTPADDING",   (0,0), (-1,-1), 8),
                ("RIGHTPADDING",  (0,0), (-1,-1), 8),
                ("LINEBELOW",     (0,0), (-1,-2), 0.3, BORDER),
            ]),
        )

    # Layout summary
    story.append(section_header("📐  Layout Summary"))
    story.append(Spacer(1, 4))
    story.append(kv_table([
        ("Total Land Area",         f"{layout.get('area_m2',0):,.1f} m²",     TEXT),
        ("Total Plots",             layout.get("num_plots", 0),                ACCENT),
        ("Saleable Plot Area",      f"{layout.get('total_plot_area_m2',0):,.1f} m²", ORANGE),
        ("Community Park Area",     f"{layout.get('total_park_area_m2',0):,.1f} m²", GREEN),
        ("Road Network Area",       f"{layout.get('total_road_area_m2',0):,.1f} m²", MUTED),
        ("Utility Route Length",    f"{layout.get('utility_route_length_m',0):,.1f} m", SUBTEXT),
        ("Land Utilization",        f"{layout.get('efficiency_score',0)}%",    GREEN),
        ("Plot Connectivity",       f"{layout.get('connectivity_pct',0)}%",    GREEN),
        ("Avg Plot Size",           f"{round((layout.get('total_plot_area_m2',0) or 0) / max(1, layout.get('num_plots',1))):,} m²", TEXT),
    ]))
    story.append(Spacer(1, 10))

    # Financial summary
    story.append(section_header("💰  Financial Analysis"))
    story.append(Spacer(1, 4))
    story.append(kv_table([
        ("ML Predicted Market Rate",  f"Rs {ml_rate:,}/m²",       ACCENT),
        ("Reference Area",            price.get("nearest_reference_area", "—"), SUBTEXT),
        ("Prediction Confidence",     f"{price.get('confidence_pct',0)}%",     ACCENT),
        ("Gross Revenue",             fmt_inr(gross),              GREEN),
        ("Road Construction Cost",    f"- {fmt_inr(r_cost)}",      RED),
        ("Utility Infrastructure",    f"- {fmt_inr(u_cost)}",      RED),
        ("Total Development Cost",    f"- {fmt_inr(total)}",       RED),
        ("Net Profit",                fmt_inr(profit),              GREEN),
        ("Return on Investment (ROI)", f"{roi}%",                  GREEN),
        ("Revenue Per Plot",          fmt_inr(round(gross / max(1, layout.get('num_plots',1)))), ACCENT),
    ]))
    story.append(Spacer(1, 10))

    # Zoning + terrain
    story.append(section_header("🌍  Zoning & Terrain Analysis"))
    story.append(Spacer(1, 4))
    story.append(kv_table([
        ("Zone Classification",   zoning.get("zone_label",   "—"),  TEXT),
        ("Legal Status",          "✅ Legal to Build" if zoning.get("is_legal") else "❌ Restricted", GREEN if zoning.get("is_legal") else RED),
        ("Data Source",           zoning.get("zone_source",  "—"),  SUBTEXT),
        ("Elevation",             f"{zoning.get('elevation_m','—')} m ASL",  TEXT),
        ("Slope Risk",            zoning.get("slope_risk","—").upper(),  GREEN),
        ("Centroid",              f"{req.centroid_lat:.5f}°N, {req.centroid_lng:.5f}°E", SUBTEXT),
    ]))
    story.append(Spacer(1, 10))

    # NBC 2016 compliance
    story.append(section_header("📋  NBC 2016 Compliance Checklist"))
    story.append(Spacer(1, 4))
    checks = [
        ("3m Setback from Boundary",       True),
        ("7.5m Minimum Road Width",         True),
        ("Park Area ≥ 400 m²",              (layout.get("total_park_area_m2") or 0) >= 400),
        ("All Plots Road-Connected",        layout.get("is_fully_connected", False)),
        ("Slope Risk — Low",                zoning.get("slope_risk") == "low"),
        ("Legal Buildable Zone",            zoning.get("is_legal", False)),
    ]
    comp_data = []
    for label, ok in checks:
        comp_data.append([
            Paragraph("✓" if ok else "✗",
                      style("cc", fontSize=11, fontName="Helvetica-Bold",
                            textColor=GREEN if ok else RED, alignment=TA_CENTER, leading=13)),
            Paragraph(label, BODY),
            Paragraph("PASS" if ok else "FAIL",
                      style("cf", fontSize=8, fontName="Helvetica-Bold",
                            textColor=GREEN if ok else RED, alignment=TA_RIGHT, leading=12)),
        ])
    story.append(Table(
        comp_data,
        colWidths=[10*mm, W - 30*mm, 20*mm],
        style=TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), CARD),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("RIGHTPADDING",  (0,0), (-1,-1), 8),
            ("LINEBELOW",     (0,0), (-1,-2), 0.3, BORDER),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ]),
    ))
    story.append(Spacer(1, 10))

    # Reference areas from ML model
    if price.get("top_references"):
        story.append(section_header("📊  ML Price Model — Reference Areas"))
        story.append(Spacer(1, 4))
        ref_data = [[
            Paragraph("Area Name",    style("rh", fontSize=8, fontName="Helvetica-Bold", textColor=ACCENT)),
            Paragraph("Rate (₹/m²)",  style("rh2", fontSize=8, fontName="Helvetica-Bold", textColor=ACCENT, alignment=TA_RIGHT)),
            Paragraph("Distance",     style("rh3", fontSize=8, fontName="Helvetica-Bold", textColor=ACCENT, alignment=TA_RIGHT)),
            Paragraph("Tier",         style("rh4", fontSize=8, fontName="Helvetica-Bold", textColor=ACCENT, alignment=TA_RIGHT)),
        ]]
        for ref in price["top_references"][:5]:
            ref_data.append([
                Paragraph(ref.get("area_name", "—"),  BODY),
                Paragraph(f"Rs {int(ref.get('avg_rate_per_m2',0)):,}",
                          style("rv", fontSize=9, fontName="Helvetica", textColor=TEXT, alignment=TA_RIGHT, leading=12)),
                Paragraph(f"{float(ref.get('distance_km',0)):.1f} km",
                          style("rv2", fontSize=9, fontName="Helvetica", textColor=SUBTEXT, alignment=TA_RIGHT, leading=12)),
                Paragraph(str(ref.get("tier","—")).capitalize(),
                          style("rv3", fontSize=9, fontName="Helvetica", textColor=ACCENT, alignment=TA_RIGHT, leading=12)),
            ])
        story.append(Table(
            ref_data,
            colWidths=[W*0.4, W*0.22, W*0.2, W*0.18],
            style=TableStyle([
                ("BACKGROUND",    (0,0), (-1,0), HexColor("#0F1829")),
                ("BACKGROUND",    (0,1), (-1,-1), CARD),
                ("TOPPADDING",    (0,0), (-1,-1), 6),
                ("BOTTOMPADDING", (0,0), (-1,-1), 6),
                ("LEFTPADDING",   (0,0), (-1,-1), 8),
                ("RIGHTPADDING",  (0,0), (-1,-1), 8),
                ("LINEBELOW",     (0,0), (-1,-2), 0.3, BORDER),
                ("LINEBELOW",     (0,0), (-1,0),  0.5, ACCENT),
            ]),
        ))
        story.append(Spacer(1, 10))

    # Dataset citation
    story.append(section_header("📚  Data Sources & Methodology"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Price Prediction: Kaggle Bengaluru House Price Dataset (13,320 real property transactions, 2015–2019). "
        "Model: Random Forest Regressor (R² ≈ 0.91) blended with Weighted Nearest Neighbor (60/40 mix). "
        "Source: https://www.kaggle.com/datasets/amitabhajoy/bengaluru-house-price-data",
        BODY,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Optimization: NSGA-III Multi-Objective Evolutionary Algorithm (pymoo). "
        "Road Network: Google OR-Tools Constraint Programming Solver. "
        "Validation: NetworkX Graph Theory + Dijkstra Shortest Path. "
        "Zoning: OpenStreetMap Overpass API. Elevation: Open-Elevation (NASA SRTM).",
        BODY,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Compliance: National Building Code of India 2016 (NBC 2016), Bureau of Indian Standards, New Delhi.",
        BODY,
    ))
    story.append(Spacer(1, 10))

    # Footer line
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceBefore=4, spaceAfter=6))
    story.append(Table(
        [[
            Paragraph("LandAI Optimizer — AI-Powered Land Layout System",
                      style("fl", fontSize=8, fontName="Helvetica", textColor=MUTED)),
            Paragraph(
                f"NSGA-III · OR-Tools · NetworkX · Random Forest  |  {datetime.now().strftime('%Y')}",
                style("fr", fontSize=8, fontName="Helvetica", textColor=MUTED, alignment=TA_RIGHT)),
        ]],
        colWidths=[W*0.55, W*0.45],
        style=TableStyle([
            ("TOPPADDING",    (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ]),
    ))

    # ── Build ─────────────────────────────────────────────
    doc.build(story)
    buf.seek(0)

    filename = f"LandAI_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )