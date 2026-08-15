"""Deterministic PDF, HTML email and Telegram renderers."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from html import escape
import os
from pathlib import Path
from typing import Any


def _display(value: Any, suffix: str = "") -> str:
    if value is None:
        return "НЕТ ДАННЫХ"
    try:
        number = Decimal(str(value))
        text = f"{number:,.2f}".replace(",", " ").replace(".00", "")
        return text + suffix
    except Exception:
        return str(value) + suffix


def _ru_date(value: str | None) -> str:
    return "НЕТ ДАННЫХ" if not value else date.fromisoformat(value[:10]).strftime("%d.%m.%Y")


def finance_lag_text(payload: dict[str, Any]) -> str:
    confirmed = payload.get("latest_confirmed_economics", {}).get("confirmed_through_date")
    return f"Финансовая экономика подтверждена по состоянию на {_ru_date(confirmed)}."


def _short_missing(value: Any) -> str:
    return "нет данных" if value is None else f"{_display_telegram(value)} шт."


def _display_telegram(value: Any, suffix: str = "") -> str:
    return _display(value, suffix).replace(".", ",")


def _human_reason(reason: str) -> str:
    labels = {
        "seller_daily_missing_or_stale_for_business_date": "операционный отчёт по товару требует обновления",
        "promotion_data_quality_review": "данные акции требуют проверки",
        "cpc_data_quality_review": "данные CPC требуют проверки",
    }
    return labels.get(reason, "требуется проверка данных")


def _freshness_lines(payload: dict[str, Any]) -> list[str]:
    warnings = set(payload.get("data_quality", {}).get("warnings", []))
    sources = payload.get("data_quality", {}).get("sources", {})
    lines: list[str] = []
    if "confirmed_finance_not_available_for_business_date" in warnings:
        confirmed_through = payload.get("latest_confirmed_economics", {}).get("confirmed_through_date")
        lines.append(
            f"Финансовая экономика подтверждена по {_ru_date(confirmed_through or sources.get('confirmed_finance_delivery'))}, "
            f"операционный отчёт — за {_ru_date(payload.get('business_date'))}."
        )
        warnings.remove("confirmed_finance_not_available_for_business_date")
    labels = {
        "seller_daily_missing_or_stale_for_business_date": "Операционный отчёт требует обновления.",
        "cpc_daily_missing_or_stale_for_business_date": "Отчёт CPC требует обновления.",
        "promotion_state_missing": "Состояние акций пока недоступно.",
        "promotion_state_stale": "Состояние акций требует обновления.",
        "price_state_missing": "Состояние цены пока недоступно.",
        "price_state_stale": "Состояние цены требует обновления.",
    }
    lines.extend(labels[warning] for warning in sorted(warnings) if warning in labels)
    return lines or ["Данные актуальны по доступным источникам."]


def render_email_html(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    latest = payload["latest_confirmed_economics"]
    warnings = payload.get("data_quality", {}).get("warnings", [])
    warning = escape("; ".join(warnings)) if warnings else "Нет"
    return (
        "<!doctype html><html><body style=\"font-family:Arial,sans-serif;color:#1f2937\">"
        f"<h2>OZON Daily Commercial Brief — {escape(payload['business_date'])}</h2>"
        f"<p><strong>Операционный день:</strong> {_ru_date(payload['business_date'])}</p>"
        f"<ul><li>Заказано: {_display(summary['ordered_units'])} шт.</li>"
        f"<li>Сумма заказов: {_display(summary['ordered_revenue'], ' ₽')}</li>"
        f"<li>CPC spend: {_display(summary['cpc_spend'], ' ₽')}</li>"
        f"<li>ACTION: {summary['offers_action']}; WATCH: {summary['offers_watch']}</li></ul>"
        f"<p><strong>{escape(finance_lag_text(payload))}</strong></p>"
        f"<ul><li>Confirmed profit before tax: {_display(latest['profit_before_tax'], ' ₽')}</li>"
        f"<li>Confirmed margin: {_display(latest['margin_percent'], '%')}</li></ul>"
        f"<p><strong>Data quality:</strong> {warning}</p>"
        "<p>Налоговый слой: Tax Engine NOT IMPLEMENTED.</p></body></html>"
    )


def render_telegram_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    latest = payload["latest_confirmed_economics"]
    lines = [
        f"OZON BRIEF · {_ru_date(payload['business_date'])}", "", "ИТОГО",
        f"Заказано: {_display_telegram(summary['ordered_units'])} шт. · {_display_telegram(summary['ordered_revenue'], ' ₽')}",
        f"Доставки: {_short_missing(summary['delivered_units'])}",
        f"Возвраты: {_short_missing(summary['returned_units'])}",
        f"Прибыль до налога: {_display_telegram(latest['profit_before_tax'], ' ₽')}",
        f"Маржа: {_display_telegram(latest['margin_percent'], '%')}",
        finance_lag_text(payload), "", "ТОВАРЫ",
    ]
    for item in payload["offers"]:
        row = f"{item['offer_id']} — {_display_telegram(item['demand']['ordered_units'])} шт. · {_display_telegram(item['demand']['ordered_revenue'], ' ₽')}"
        economics = item["latest_confirmed_economics"]
        if economics["profit_before_tax"] is not None:
            row += f" · прибыль {_display_telegram(economics['profit_before_tax'], ' ₽')}"
        if economics["confirmed_margin_percent"] is not None:
            row += f" · маржа {_display_telegram(economics['confirmed_margin_percent'], '%')}*"
        lines.append(row)
    global_reasons = set(payload.get("data_quality", {}).get("warnings", []))
    attention = [
        (item, [reason for reason in item["attention"]["reasons"] if reason not in global_reasons])
        for item in payload["offers"]
    ]
    attention = [(item, reasons) for item, reasons in attention if reasons]
    if attention:
        lines.extend(["", "ВНИМАНИЕ"])
        lines.extend(f"{item['offer_id']} — {', '.join(_human_reason(reason) for reason in reasons)}." for item, reasons in attention)
    else:
        lines.extend(["", "ВНИМАНИЕ", "Существенных подтверждённых аномалий нет."])
    if any(item["latest_confirmed_economics"]["confirmed_through_date"] not in (None, payload["business_date"])
           for item in payload["offers"]):
        lines.extend(["", f"* Подтверждённая финансовая экономика относится к данным по {_ru_date(latest['confirmed_through_date'])}."])
    lines.extend(["", "АКТУАЛЬНОСТЬ ДАННЫХ", *_freshness_lines(payload)])
    return "\n".join(lines)


def _font_path(explicit: str | None = None) -> str:
    candidates = [explicit, os.environ.get("EFA_PDF_FONT_PATH"),
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                  "C:/Windows/Fonts/arial.ttf"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("No Cyrillic-capable PDF font found; set EFA_PDF_FONT_PATH")


def render_pdf(payload: dict[str, Any], output_path: str | Path, font_path: str | None = None) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont("EFA", _font_path(font_path)))
    pdfmetrics.registerFont(TTFont("EFA-Bold", _font_path(font_path)))
    page_size = landscape(A4)

    def decorate(canvas, document):
        canvas.saveState(); canvas.setFont("EFA", 8); canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(14 * mm, 8 * mm, f"EFA OS · Daily Commercial Brief · {payload['business_date']}")
        canvas.drawRightString(page_size[0] - 14 * mm, 8 * mm, f"Страница {document.page}")
        canvas.restoreState()

    document = BaseDocTemplate(str(path), pagesize=page_size, rightMargin=14*mm, leftMargin=14*mm,
                               topMargin=14*mm, bottomMargin=14*mm,
                               title=f"OZON Daily Commercial Brief — {payload['business_date']}")
    document.addPageTemplates(PageTemplate(id="main", frames=[Frame(14*mm, 14*mm, page_size[0]-28*mm, page_size[1]-28*mm, id="frame")], onPage=decorate))
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleEFA", parent=styles["Title"], fontName="EFA-Bold", fontSize=22, leading=27, textColor=colors.HexColor("#0f172a"), alignment=TA_LEFT)
    h1 = ParagraphStyle("H1EFA", parent=styles["Heading1"], fontName="EFA-Bold", fontSize=16, leading=20, textColor=colors.HexColor("#0f766e"))
    body = ParagraphStyle("BodyEFA", parent=styles["BodyText"], fontName="EFA", fontSize=9, leading=13, textColor=colors.HexColor("#334155"))
    small = ParagraphStyle("SmallEFA", parent=body, fontSize=7, leading=9)
    center = ParagraphStyle("CenterEFA", parent=body, alignment=TA_CENTER)
    story: list[Any] = []

    def heading(text): story.extend([Paragraph(text, h1), Spacer(1, 4*mm)])
    def table(data, widths=None, font_size=8):
        item = Table(data, colWidths=widths, repeatRows=1)
        item.setStyle(TableStyle([("FONTNAME", (0,0), (-1,-1), "EFA"), ("FONTNAME", (0,0), (-1,0), "EFA-Bold"),
                                  ("FONTSIZE", (0,0), (-1,-1), font_size), ("LEADING", (0,0), (-1,-1), font_size+2),
                                  ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#ccfbf1")),
                                  ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#115e59")),
                                  ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#cbd5e1")),
                                  ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 4),
                                  ("RIGHTPADDING", (0,0), (-1,-1), 4), ("TOPPADDING", (0,0), (-1,-1), 4),
                                  ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
        story.append(item)

    # Page 1
    story.extend([Paragraph("OZON Daily Commercial Brief", title), Paragraph(f"Операционный день: {_ru_date(payload['business_date'])} · сформирован {escape(payload['generated_at'])}", body), Spacer(1, 6*mm)])
    summary, latest = payload["summary"], payload["latest_confirmed_economics"]
    table([["Заказы, ₽", "Заказано, шт.", "CPC spend, ₽", "Profit before tax, ₽", "Margin", "ACTION / WATCH"],
           [_display(summary["ordered_revenue"]), _display(summary["ordered_units"]), _display(summary["cpc_spend"]),
            _display(latest["profit_before_tax"]), _display(latest["margin_percent"], "%"), f"{summary['offers_action']} / {summary['offers_watch']}"]],
          [42*mm, 36*mm, 36*mm, 45*mm, 32*mm, 38*mm], 10)
    story.extend([Spacer(1, 6*mm), Paragraph(finance_lag_text(payload), h1), Spacer(1, 3*mm)])
    heading("Требует внимания")
    for item in payload["offers"]:
        if item["attention"]["level"] != "NO_ACTION":
            story.append(Paragraph(f"<b>{escape(item['offer_id'])} · {item['attention']['level']}</b> — {escape(', '.join(item['attention']['reasons']))}", body))
    story.append(PageBreak())

    # Page 2
    heading("Пять товаров — операционный день и подтверждённая экономика")
    rows = [["offer", "Цена", "Boost", "Активная акция", "Заказано", "Заказы, ₽", "Доставлено", "Возвраты", "Profit до налога", "Margin", "CPC", "Attention"]]
    for item in payload["offers"]:
        active = item["promotions"]["participating"]
        first = active[0] if active else {}
        le = item["latest_confirmed_economics"]
        rows.append([item["offer_id"], _display(item["price"]["current_price"]), _display(first.get("current_boost"), "%"),
                     Paragraph(escape(first.get("action_title") or "НЕТ"), small), _display(item["demand"]["ordered_units"]),
                     _display(item["demand"]["ordered_revenue"]), _display(item["fulfilment"]["delivered_units"]),
                     _display(item["fulfilment"]["returned_units"]), _display(le["profit_before_tax"]),
                     _display(le["confirmed_margin_percent"], "%"), _display(sum(Decimal(x["spend"]) for x in item["advertising"]["cpc"]) if item["advertising"]["cpc"] else None),
                     item["attention"]["level"]])
    table(rows, [18*mm,16*mm,14*mm,46*mm,17*mm,20*mm,19*mm,18*mm,25*mm,18*mm,17*mm,20*mm], 6.2)
    story.extend([Spacer(1, 4*mm), Paragraph(finance_lag_text(payload), body), Paragraph("NULL отображается как «НЕТ ДАННЫХ», а не как ноль. Выкуп по календарному дню не рассчитывается.", body), PageBreak()])

    # Page 3
    heading("Исторические тренды")
    _append_trend_sections(story, payload["extended_report_payload"].get("trends", {}), h1, body, small, table)
    story.append(PageBreak())

    # Page 4
    heading("Акции, Elastic Boosting и CPC")
    promo_rows = [["offer", "Состояние", "Акция / кампания", "Action price", "Boost", "CPC spend", "CPC orders", "Примечание"]]
    for item in payload["offers"]:
        for active in item["promotions"]["participating"]:
            promo_rows.append([item["offer_id"], "PARTICIPATING", Paragraph(escape(active["action_title"] or ""), small), _display(active["action_price"]), _display(active["current_boost"], "%"), "—", "—", active["data_quality_status"]])
        for cpc in item["advertising"]["cpc"]:
            note = item["advertising"]["inactive_attribution_note"] or cpc["data_quality_status"]
            promo_rows.append([item["offer_id"], cpc["campaign_state"], f"CPC {cpc['campaign_id']}", "—", "—", _display(cpc["spend"]), _display(cpc["orders"]), Paragraph(escape(note), small)])
    table(promo_rows, [18*mm,35*mm,55*mm,23*mm,18*mm,22*mm,22*mm,55*mm], 6.8)
    story.extend([Spacer(1, 4*mm), Paragraph("Кандидаты сохраняются отдельно и не трактуются как активное участие. JOIN/LEAVE и рекламные рекомендации не выполняются.", body), PageBreak()])

    # Page 5
    heading("Экономика и качество данных")
    quality_rows = [["Источник", "Последняя доступность / состояние"]]
    for key, value in payload["data_quality"]["sources"].items(): quality_rows.append([key, value or "НЕТ ДАННЫХ"])
    table(quality_rows, [65*mm, 155*mm], 8)
    story.extend([Spacer(1, 5*mm), Paragraph(f"<b>Data quality:</b> {escape(payload['data_quality']['status'])}", body)])
    for warning in payload["data_quality"]["warnings"]: story.append(Paragraph(f"• {escape(warning)}", body))
    story.extend([Spacer(1, 4*mm), Paragraph("Commission/logistics anomalies: в Daily Brief не пересчитываются; применяются только готовые deterministic attention reasons.", body),
                  Paragraph("Current price economics: " + ", ".join(f"{escape(x['offer_id'])}={x['economics']['current_price_economics_status']}" for x in payload["offers"]), body),
                  Paragraph("Tax Engine NOT IMPLEMENTED. Profit after tax не показывается.", h1)])
    document.build(story)
    return path


def _append_trend_sections(story, trends, h1, body, small, table):
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Table, TableStyle

    definitions = [
        (("demand", "Заказы, ₽", "business_date", "ordered_revenue"), ("demand", "Заказано, шт.", "business_date", "ordered_units")),
        (("price", "Цена по товарам", "observed_at", "price"), ("boost", "Elastic Boost, %", "observed_at", "current_boost")),
        (("finance", "Confirmed profit before tax", "business_date", "profit_before_tax"), ("finance", "Confirmed margin, %", "business_date", "margin_percent")),
    ]
    chart_rows = []
    for pair in definitions:
        cells = []
        for key, title, date_key, metric in pair:
            rows = trends.get(key, [])
            chart = _line_chart(rows, title, date_key, metric)
            cells.append(chart if chart is not None else Paragraph(f"<b>{title}</b><br/>График не построен: недостаточно исторических точек.", body))
        chart_rows.append(cells)
    grid = Table(chart_rows, colWidths=[122*mm, 122*mm], rowHeights=[43*mm, 43*mm, 43*mm])
    grid.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("BOX", (0,0), (-1,-1), .3, colors.HexColor("#cbd5e1")),
                              ("INNERGRID", (0,0), (-1,-1), .3, colors.HexColor("#e2e8f0")),
                              ("LEFTPADDING", (0,0), (-1,-1), 3), ("RIGHTPADDING", (0,0), (-1,-1), 3),
                              ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3)]))
    story.extend([grid, Paragraph("Точки агрегированы по календарному дню. Используются только наблюдаемые значения; прогноз отсутствует.", small)])


def _line_chart(rows, title, date_key, metric):
    from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Rect, String
    from reportlab.lib import colors

    grouped = {}
    for row in rows:
        value = row.get(metric)
        if value is not None:
            grouped[(row[date_key][:10], row["offer_id"])] = Decimal(str(value))
    dates = sorted({key[0] for key in grouped})
    if len(dates) < 2:
        return None
    offers = sorted({key[1] for key in grouped})
    values = list(grouped.values())
    minimum, maximum = min(values), max(values)
    if minimum == maximum:
        minimum -= Decimal("1"); maximum += Decimal("1")
    width, height = 340, 116
    left, bottom, plot_width, plot_height = 34, 22, 294, 67
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=colors.white, strokeColor=None))
    drawing.add(String(5, 101, title, fontName="EFA-Bold", fontSize=9, fillColor=colors.HexColor("#0f766e")))
    drawing.add(Line(left, bottom, left, bottom + plot_height, strokeColor=colors.HexColor("#94a3b8"), strokeWidth=.6))
    drawing.add(Line(left, bottom, left + plot_width, bottom, strokeColor=colors.HexColor("#94a3b8"), strokeWidth=.6))
    drawing.add(String(2, bottom + plot_height - 2, _display(maximum), fontName="EFA", fontSize=5.5, fillColor=colors.HexColor("#64748b")))
    drawing.add(String(2, bottom - 1, _display(minimum), fontName="EFA", fontSize=5.5, fillColor=colors.HexColor("#64748b")))
    drawing.add(String(left, 8, dates[0], fontName="EFA", fontSize=5.5, fillColor=colors.HexColor("#64748b")))
    drawing.add(String(left + plot_width - 38, 8, dates[-1], fontName="EFA", fontSize=5.5, fillColor=colors.HexColor("#64748b")))
    palette = [colors.HexColor(value) for value in ("#0f766e", "#2563eb", "#d97706", "#dc2626", "#7c3aed")]
    date_index = {value: index for index, value in enumerate(dates)}
    for index, offer in enumerate(offers):
        points = []
        for day in dates:
            value = grouped.get((day, offer))
            if value is None:
                continue
            x = left + plot_width * date_index[day] / (len(dates) - 1)
            y = bottom + plot_height * float((value - minimum) / (maximum - minimum))
            points.append((x, y))
        color = palette[index % len(palette)]
        if len(points) >= 2:
            drawing.add(PolyLine(points, strokeColor=color, strokeWidth=1.2))
        for x, y in points:
            drawing.add(Circle(x, y, 1.7, fillColor=color, strokeColor=None))
        legend_x = 110 + (index % 3) * 70
        legend_y = 103 - (index // 3) * 8
        drawing.add(Line(legend_x, legend_y, legend_x + 10, legend_y, strokeColor=color, strokeWidth=1.5))
        drawing.add(String(legend_x + 13, legend_y - 2, offer, fontName="EFA", fontSize=5.5, fillColor=colors.HexColor("#334155")))
    return drawing
