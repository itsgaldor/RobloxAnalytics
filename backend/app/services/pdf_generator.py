"""
Generador de reportes PDF para Peru City Analytics.
Usa ReportLab Platypus con diseno mejorado: header en cada pagina,
KPI cards con acento de color, tablas bien espaciadas.
"""
import io
import re
from datetime import date
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle, KeepTogether,
)

from app.models.models import Brand

PAGE_W, PAGE_H = A4
MARGIN       = 2.0 * cm
HEADER_H     = 2.2 * cm          # banda coloreada en paginas de contenido
TOP_MARGIN   = HEADER_H + 0.8 * cm
BOTTOM_MARGIN= 2.0 * cm
CONTENT_W    = PAGE_W - 2 * MARGIN

KPI_LABELS = {
    "es": {
        "sessions":            "Sesiones totales",
        "dau":                 "DAU (usuarios/dia)",
        "mau":                 "MAU (30 dias)",
        "avg_session_minutes": "Tiempo prom. sesion",
        "total_hours":         "Horas totales",
    },
    "en": {
        "sessions":            "Total Sessions",
        "dau":                 "DAU (users/day)",
        "mau":                 "MAU (30 days)",
        "avg_session_minutes": "Avg. Session Time",
        "total_hours":         "Total Hours",
    },
}

KPI_ICONS = {
    "sessions":            "SESIONES",
    "dau":                 "DAU",
    "mau":                 "MAU",
    "avg_session_minutes": "TIEMPO",
    "total_hours":         "HORAS",
}


# ── Helpers de color ──────────────────────────────────────────────────────────

def _hex_color(hex_str: str) -> colors.Color:
    h = hex_str.lstrip("#")
    return colors.Color(int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255)


def _darken(c: colors.Color, pct: float = 0.20) -> colors.Color:
    return colors.Color(
        max(0, c.red   * (1 - pct)),
        max(0, c.green * (1 - pct)),
        max(0, c.blue  * (1 - pct)),
    )


def _lighten(c: colors.Color, pct: float = 0.85) -> colors.Color:
    return colors.Color(
        c.red   + (1 - c.red)   * pct,
        c.green + (1 - c.green) * pct,
        c.blue  + (1 - c.blue)  * pct,
    )


def _fmt(n) -> str:
    if n is None:
        return "-"
    return f"{round(n):,}"


def _fmt_min(mins) -> str:
    if not mins and mins != 0:
        return "-"
    mins = float(mins)
    if mins < 60:
        return f"{round(mins)} min"
    h = int(mins // 60)
    m = round(mins % 60)
    return f"{h}h {m}min" if m else f"{h}h"


# ── Canvas helpers ────────────────────────────────────────────────────────────

def _draw_cover(canvas, doc, brand: Brand, date_from: date, date_to: date,
                brand_color: colors.Color, dark_color: colors.Color):
    canvas.saveState()
    w, h = A4

    # -- Fondo inferior (blanco ya es default) --

    # Bloque superior coloreado (70% de la pagina)
    SPLIT = 0.30
    canvas.setFillColor(brand_color)
    canvas.rect(0, h * SPLIT, w, h * (1 - SPLIT), fill=1, stroke=0)

    # Banda de acento oscura en la union
    canvas.setFillColor(dark_color)
    canvas.rect(0, h * SPLIT, w, 0.4 * cm, fill=1, stroke=0)

    # Patron decorativo: circulos semitransparentes en la esquina sup der
    overlay = colors.Color(1, 1, 1, alpha=0.05)
    canvas.setFillColor(overlay)
    for i in range(5):
        sz = 2.5 * cm + i * 2.0 * cm
        canvas.circle(w, h, sz, fill=1, stroke=0)

    # -- Textos en zona coloreada --
    canvas.setFillColor(colors.white)

    # Etiqueta superior pequeña
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.65))
    canvas.drawCentredString(w / 2, h * 0.90, "ANALYTICS REPORT  •  ROBLOX")

    # Linea sutil bajo la etiqueta
    canvas.setStrokeColor(colors.Color(1, 1, 1, alpha=0.20))
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN * 4, h * 0.885, w - MARGIN * 4, h * 0.885)

    # Titulo principal
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 36)
    canvas.drawCentredString(w / 2, h * 0.78, "Reporte de Analytics")

    # Linea decorativa bajo titulo
    canvas.setStrokeColor(colors.Color(1, 1, 1, alpha=0.35))
    canvas.setLineWidth(1.5)
    canvas.line(w/2 - 2*cm, h * 0.745, w/2 + 2*cm, h * 0.745)

    # Nombre de la marca — grande y prominente
    canvas.setFont("Helvetica-Bold", 26)
    canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.95))
    canvas.drawCentredString(w / 2, h * 0.68, brand.name)

    # Periodo
    canvas.setFont("Helvetica", 12)
    canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.78))
    period = f"{date_from.strftime('%d %b %Y')}  —  {date_to.strftime('%d %b %Y')}"
    canvas.drawCentredString(w / 2, h * 0.62, period)

    # Linea separadora zona coloreada / blanca
    canvas.setStrokeColor(colors.Color(1, 1, 1, alpha=0.25))
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN * 2, h * SPLIT + 0.55 * cm, w - MARGIN * 2, h * SPLIT + 0.55 * cm)

    # -- Zona blanca inferior: info de generacion --
    # Rectangulo de fondo sutil
    canvas.setFillColor(colors.Color(0.97, 0.97, 0.99))
    canvas.roundRect(MARGIN * 2, h * 0.14, w - MARGIN * 4, h * 0.115, 4, fill=1, stroke=0)

    # Linea izquierda de color
    canvas.setFillColor(brand_color)
    canvas.rect(MARGIN * 2, h * 0.14, 0.3 * cm, h * 0.115, fill=1, stroke=0)

    canvas.setFont("Helvetica-Bold", 13)
    canvas.setFillColor(colors.Color(0.12, 0.12, 0.12))
    canvas.drawString(MARGIN * 2 + 0.6 * cm, h * 0.225, "Peru City Analytics")

    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(colors.Color(0.45, 0.45, 0.45))
    canvas.drawString(MARGIN * 2 + 0.6 * cm, h * 0.175, f"Generado el {date.today().strftime('%d de %B de %Y')}  •  Reporte de metricas Roblox")

    # Footer
    _draw_footer(canvas, brand.name, 1, None)
    canvas.restoreState()


def _draw_page_header(canvas, brand: Brand, brand_color: colors.Color,
                      dark_color: colors.Color):
    """Banda de color en la parte superior de las paginas de contenido."""
    canvas.saveState()
    w, h = A4

    # Banda principal
    canvas.setFillColor(brand_color)
    canvas.rect(0, h - HEADER_H, w, HEADER_H, fill=1, stroke=0)

    # Linea oscura inferior de la banda
    canvas.setFillColor(dark_color)
    canvas.rect(0, h - HEADER_H, w, 0.18 * cm, fill=1, stroke=0)

    # Nombre de marca (izquierda)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(MARGIN, h - HEADER_H + 0.75 * cm, brand.name)

    # "Peru City Analytics" (derecha)
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.80))
    canvas.drawRightString(PAGE_W - MARGIN, h - HEADER_H + 0.75 * cm, "Peru City Analytics")

    canvas.restoreState()


def _draw_footer(canvas, brand_name: str, page: int, total):
    canvas.saveState()
    canvas.setStrokeColor(colors.Color(0.82, 0.82, 0.82))
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, BOTTOM_MARGIN - 0.3 * cm, PAGE_W - MARGIN, BOTTOM_MARGIN - 0.3 * cm)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.Color(0.55, 0.55, 0.55))

    page_str = f"Pagina {page}"
    canvas.drawString(MARGIN, BOTTOM_MARGIN - 0.7 * cm, f"{brand_name} | Peru City Analytics")
    canvas.drawRightString(PAGE_W - MARGIN, BOTTOM_MARGIN - 0.7 * cm, page_str)
    canvas.restoreState()


# ── Pagina de metricas ────────────────────────────────────────────────────────

def _build_metrics_story(
    brand: Brand,
    metrics: dict,
    prev_metrics: dict,
    daily_data: list,
    selected_kpis: list,
    date_from: date,
    date_to: date,
    brand_color: colors.Color,
    language: str,
) -> list:
    story = []
    labels = KPI_LABELS.get(language, KPI_LABELS["es"])
    is_es  = language == "es"
    light  = _lighten(brand_color, 0.90)
    dark   = _darken(brand_color, 0.15)

    # ── Titulo de seccion ────────────────────────────────────────────────
    title_sty = ParagraphStyle(
        "SecTitle", fontName="Helvetica-Bold", fontSize=17,
        textColor=colors.Color(0.12, 0.12, 0.12), spaceAfter=2,
    )
    sub_sty = ParagraphStyle(
        "SubTitle", fontName="Helvetica", fontSize=10,
        textColor=colors.Color(0.55, 0.55, 0.55), spaceAfter=16,
    )
    heading    = "Resumen del Periodo" if is_es else "Period Summary"
    period_str = f"{date_from.strftime('%d %b %Y')}  -  {date_to.strftime('%d %b %Y')}"

    # Titulo con barra de acento izquierda (via tabla de 2 celdas)
    accent_bar = Table(
        [[Paragraph(heading, title_sty)]],
        colWidths=[CONTENT_W],
    )
    accent_bar.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LINEBEFORECELL", (0, 0), (0, 0), 4, brand_color),
    ]))
    story.append(accent_bar)
    story.append(Paragraph(period_str, sub_sty))

    # ── KPI cards ────────────────────────────────────────────────────────
    kpi_keys = [k for k in ["sessions", "dau", "mau", "avg_session_minutes", "total_hours"]
                if k in selected_kpis]

    if kpi_keys:
        card_label_sty = ParagraphStyle("CL", fontName="Helvetica", fontSize=8,
                                         textColor=colors.Color(0.55, 0.55, 0.55),
                                         alignment=TA_CENTER, spaceAfter=4)
        card_value_sty = ParagraphStyle("CV", fontName="Helvetica-Bold", fontSize=19,
                                         textColor=colors.Color(0.1, 0.1, 0.1),
                                         alignment=TA_CENTER, spaceAfter=4)
        card_delta_sty = ParagraphStyle("CD", fontName="Helvetica", fontSize=9,
                                         alignment=TA_CENTER)

        # Fila superior: acento de color (1 celda por KPI)
        accent_row = []
        label_row  = []
        value_row  = []
        delta_row  = []

        for key in kpi_keys:
            val      = metrics.get(key, 0) or 0
            prev_val = prev_metrics.get(key, 0) or 0

            if key == "avg_session_minutes":
                formatted = _fmt_min(val)
            elif key == "total_hours":
                formatted = f"{_fmt(round(val))}h"
            else:
                formatted = _fmt(val)

            if prev_val and prev_val != 0:
                delta   = ((val - prev_val) / prev_val) * 100
                sign    = "+" if delta >= 0 else ""
                d_txt   = f"{sign}{delta:.1f}%"
                d_color = "#27ae60" if delta >= 0 else "#e74c3c"
                arrow   = "&#9650;" if delta >= 0 else "&#9660;"
            else:
                d_txt, d_color, arrow = "-", "#aaaaaa", ""

            accent_row.append("")
            label_row.append(Paragraph(labels.get(key, key).upper(), card_label_sty))
            value_row.append(Paragraph(formatted, card_value_sty))
            delta_row.append(
                Paragraph(f'<font color="{d_color}">{arrow} {d_txt}</font>', card_delta_sty)
            )

        col_w = CONTENT_W / len(kpi_keys)
        # Tabla con 4 filas: acento (4pt), label, valor, delta
        kpi_tbl = Table(
            [accent_row, label_row, value_row, delta_row],
            colWidths=[col_w] * len(kpi_keys),
            rowHeights=[4, None, None, None],
        )
        style_cmds = [
            # Acento superior (fila 0) con color de marca
            ("BACKGROUND",    (0, 0), (-1, 0), brand_color),
            # Fondo blanco para filas de datos
            ("BACKGROUND",    (0, 1), (-1, -1), colors.white),
            # Borde exterior
            ("BOX",           (0, 0), (-1, -1), 1.0, colors.Color(0.82, 0.82, 0.82)),
            # Divisores verticales entre cards
            ("LINEBEFORE",    (1, 0), (-1, -1), 0.5, colors.Color(0.88, 0.88, 0.88)),
            # Padding
            ("TOPPADDING",    (0, 1), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 10),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("TOPPADDING",    (0, 0), (-1, 0), 0),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
        ]
        kpi_tbl.setStyle(TableStyle(style_cmds))
        story.append(KeepTogether([kpi_tbl]))
        story.append(Spacer(1, 28))

    # ── Tabla de datos diarios ────────────────────────────────────────────
    tbl_title_sty = ParagraphStyle(
        "TblTitle", fontName="Helvetica-Bold", fontSize=13,
        textColor=colors.Color(0.12, 0.12, 0.12), spaceAfter=10,
    )

    daily_title = "Datos diarios" if is_es else "Daily Data"
    daily_accent = Table(
        [[Paragraph(daily_title, tbl_title_sty)]],
        colWidths=[CONTENT_W],
    )
    daily_accent.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("LINEBEFORECELL", (0, 0), (0, 0), 4, brand_color),
    ]))
    story.append(daily_accent)
    story.append(Spacer(1, 6))

    if not daily_data:
        story.append(Paragraph(
            "Sin datos para el periodo seleccionado." if is_es else "No data for selected period.",
            ParagraphStyle("ND", fontName="Helvetica", fontSize=10,
                           textColor=colors.Color(0.5, 0.5, 0.5)),
        ))
    else:
        headers = (
            ["Fecha", "Sesiones", "Usuarios", "T. Promedio", "Horas", "Publico", "Privado"]
            if is_es else
            ["Date", "Sessions", "Users", "Avg Time", "Hours", "Public", "Private"]
        )

        th_sty = ParagraphStyle("TH", fontName="Helvetica-Bold", fontSize=8.5,
                                  textColor=colors.white, alignment=TA_CENTER)
        td_sty = ParagraphStyle("TD", fontName="Helvetica", fontSize=8.5,
                                  textColor=colors.Color(0.18, 0.18, 0.18), alignment=TA_CENTER)
        td_date_sty = ParagraphStyle("TDD", fontName="Helvetica-Bold", fontSize=8.5,
                                      textColor=colors.Color(0.18, 0.18, 0.18), alignment=TA_LEFT)

        rows = [[Paragraph(h, th_sty) for h in headers]]

        for row in daily_data[:30]:
            def g(key):
                return row[key] if isinstance(row, dict) else getattr(row, key, 0)

            d_val    = g("date")
            date_str = d_val.strftime("%d/%m/%Y") if isinstance(d_val, date) else str(d_val)

            rows.append([
                Paragraph(date_str,                              td_date_sty),
                Paragraph(_fmt(g("sessions")),                   td_sty),
                Paragraph(_fmt(g("unique_users")),               td_sty),
                Paragraph(_fmt_min(g("avg_minutes")),            td_sty),
                Paragraph(f"{_fmt(round(g('total_hours')))}h",   td_sty),
                Paragraph(_fmt(g("public_sessions")),            td_sty),
                Paragraph(_fmt(g("private_sessions")),           td_sty),
            ])

        col_widths = [2.8*cm, 2.2*cm, 2.0*cm, 2.4*cm, 1.8*cm, 2.1*cm, 2.1*cm]
        daily_tbl  = Table(rows, colWidths=col_widths, repeatRows=1)

        style_cmds = [
            ("BACKGROUND",    (0, 0), (-1, 0), brand_color),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("LINEABOVE",     (0, 0), (-1, 0), 0, colors.white),
            ("LINEBELOW",     (0, 0), (-1, 0), 0.5, dark),
            ("BOX",           (0, 0), (-1, -1), 0.5, colors.Color(0.82, 0.82, 0.82)),
            ("INNERGRID",     (0, 1), (-1, -1), 0.3, colors.Color(0.88, 0.88, 0.88)),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]
        for i in range(1, len(rows)):
            bg = colors.Color(0.96, 0.96, 0.98) if i % 2 == 0 else colors.white
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

        daily_tbl.setStyle(TableStyle(style_cmds))
        story.append(daily_tbl)

    return story


# ── Pagina de analisis IA ─────────────────────────────────────────────────────

def _build_ai_story(
    ai_analysis: str,
    brand_color: colors.Color,
    used_mock: bool,
    language: str,
) -> list:
    story = []
    is_es = language == "es"
    light = _lighten(brand_color, 0.90)

    title_sty = ParagraphStyle("AITitle", fontName="Helvetica-Bold", fontSize=17,
                                textColor=colors.Color(0.12, 0.12, 0.12), spaceAfter=2)
    sub_sty   = ParagraphStyle("AISub", fontName="Helvetica", fontSize=10,
                                textColor=colors.Color(0.55, 0.55, 0.55), spaceAfter=16)
    sec_sty   = ParagraphStyle("AISec", fontName="Helvetica-Bold", fontSize=11,
                                textColor=brand_color, spaceBefore=16, spaceAfter=6)
    body_sty  = ParagraphStyle("AIBody", fontName="Helvetica", fontSize=10,
                                textColor=colors.Color(0.18, 0.18, 0.18), leading=16, spaceAfter=6)
    foot_sty  = ParagraphStyle("AIFoot", fontName="Helvetica", fontSize=8,
                                textColor=colors.Color(0.6, 0.6, 0.6), alignment=TA_CENTER)

    heading = "Analisis de Inteligencia Artificial" if is_es else "AI Analysis"
    title_accent = Table(
        [[Paragraph(heading, title_sty)]],
        colWidths=[CONTENT_W],
    )
    title_accent.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LINEBEFORECELL", (0, 0), (0, 0), 4, brand_color),
    ]))
    story.append(title_accent)
    story.append(Paragraph("Generado por Peru City Analytics AI", sub_sty))

    # Parsear texto — secciones **bold** y cuerpo
    for para in ai_analysis.strip().split("\n\n"):
        para = para.strip()
        if not para:
            continue

        if para.startswith("**") and para.endswith("**"):
            story.append(Paragraph(para[2:-2], sec_sty))
            continue

        if para.startswith("**"):
            lines = para.split("\n", 1)
            story.append(Paragraph(lines[0].strip("*").strip(), sec_sty))
            if len(lines) > 1:
                for line in lines[1].strip().split("\n"):
                    line = line.strip()
                    if line:
                        line = re.sub(r"^\d+\.\s*", "• ", line)
                        story.append(Paragraph(line, body_sty))
            continue

        if re.match(r"^\d+\.", para):
            for line in para.split("\n"):
                line = line.strip()
                if line:
                    line = re.sub(r"^\d+\.\s*", "• ", line)
                    story.append(Paragraph(line, body_sty))
            continue

        story.append(Paragraph(para.replace("\n", " "), body_sty))

    story.append(Spacer(1, 24))
    story.append(HRFlowable(width=CONTENT_W, thickness=0.5, color=colors.Color(0.85, 0.85, 0.85)))
    story.append(Spacer(1, 8))

    foot = (
        "Analisis simulado — configure ANTHROPIC_API_KEY para analisis real con Claude"
        if used_mock else
        "Analisis generado con Claude by Anthropic"
    ) if is_es else (
        "Simulated analysis — configure ANTHROPIC_API_KEY for real AI analysis with Claude"
        if used_mock else
        "Analysis generated with Claude by Anthropic"
    )
    story.append(Paragraph(foot, foot_sty))
    return story


# ── Funcion principal ─────────────────────────────────────────────────────────

def generate_report_pdf(
    brand: Brand,
    metrics: dict,
    prev_metrics: dict,
    daily_data: list,
    selected_kpis: list,
    ai_analysis: Optional[str],
    used_mock_ai: bool,
    date_from: date,
    date_to: date,
    language: str,
) -> bytes:
    """Genera el PDF completo y devuelve los bytes."""
    buffer      = io.BytesIO()
    brand_color = _hex_color(brand.primary_color)
    dark_color  = _darken(brand_color, 0.22)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=MARGIN, leftMargin=MARGIN,
        topMargin=TOP_MARGIN, bottomMargin=BOTTOM_MARGIN + 0.6 * cm,
        title=f"Reporte {brand.name}",
        author="Peru City Analytics",
    )

    # Pagina 1 = portada (100% canvas via onFirstPage)
    # Paginas 2+ = Platypus con header/footer via on_later_pages
    story: list = [Spacer(1, 1), PageBreak()]

    story += _build_metrics_story(
        brand, metrics, prev_metrics, daily_data,
        selected_kpis, date_from, date_to, brand_color, language,
    )

    if ai_analysis:
        story.append(PageBreak())
        story += _build_ai_story(ai_analysis, brand_color, used_mock_ai, language)

    def on_first_page(canvas, doc):
        _draw_cover(canvas, doc, brand, date_from, date_to,
                    brand_color, dark_color)

    def on_later_pages(canvas, doc):
        _draw_page_header(canvas, brand, brand_color, dark_color)
        _draw_footer(canvas, brand.name, canvas.getPageNumber(), None)

    doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
    return buffer.getvalue()
