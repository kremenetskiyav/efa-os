"""Deterministic Daily Brief v1.1 PDF, HTML and Telegram renderers."""
from __future__ import annotations

from datetime import date
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


def _display_telegram(value: Any, suffix: str = "") -> str:
    return _display(value, suffix).replace(".", ",")


def _ru_date(value: str | None) -> str:
    return "НЕТ ДАННЫХ" if not value else date.fromisoformat(value[:10]).strftime("%d.%m.%Y")


def finance_lag_text(payload: dict[str, Any]) -> str:
    current = payload["current_day_economics"]
    latest = payload["latest_confirmed_economics"]
    if current["confirmation_state"] == "CONFIRMED":
        return f"Экономика за {_ru_date(payload['business_date'])} подтверждена."
    return (
        f"Экономика за {_ru_date(payload['business_date'])} не подтверждена; "
        f"последняя подтверждённая дата — {_ru_date(latest['confirmed_through_date'])}."
    )


def _freshness_compact(payload: dict[str, Any]) -> str:
    labels = {
        "seller_analytics": "Seller", "postings": "Postings", "returns": "Returns",
        "finance": "Finance", "cpc": "CPC", "information_intelligence": "Info",
        "tax_engine": "Tax",
    }
    return " · ".join(f"{labels[key]} {value['state'].upper()}" for key, value in payload["source_freshness"].items())


def _tax_line(payload: dict[str, Any]) -> str:
    tax = payload["tax"]
    return (
        f"Tax {tax['engine_state']}: доход {_display_telegram(tax['taxable_revenue'], ' ₽')}; "
        f"УСН {_display_telegram(tax['gross_usn'], ' ₽')}; к уплате {_display_telegram(tax['estimated_payable'], ' ₽')}; "
        f"доп. 1% {_display_telegram(tax['additional_1pct'], ' ₽')} · {tax['data_quality']}"
    )


def render_telegram_text(payload: dict[str, Any]) -> str:
    summary, current, latest = payload["summary"], payload["current_day_economics"], payload["latest_confirmed_economics"]
    cpc = payload["advertising"]["cpc"]
    lines = [
        f"OZON DAILY BRIEF v1.1 · {_ru_date(payload['business_date'])}",
        _freshness_compact(payload), "", "ПРОДАЖИ",
        f"Сегодня: {_display_telegram(summary['ordered_units'])} шт. · {_display_telegram(summary['ordered_revenue'], ' ₽')}",
    ]
    for item in payload["offers"]:
        lines.append(f"{item['offer_id']}: {_display_telegram(item['demand']['ordered_units'])} шт. · {_display_telegram(item['demand']['ordered_revenue'], ' ₽')}")
    lines.extend(["", "ЭКОНОМИКА"])
    if current["confirmation_state"] == "CONFIRMED":
        lines.append(f"Сегодня: вклад {_display_telegram(current['contribution_profit'], ' ₽')} · маржа {_display_telegram(current['contribution_margin_pct'], '%')}")
    else:
        lines.append("Сегодня: не подтверждена")
    lines.append(
        f"Последняя подтверждённая ({_ru_date(latest['confirmed_through_date'])}): "
        f"выручка {_display_telegram(latest['revenue'], ' ₽')} · вклад {_display_telegram(latest['contribution_profit'], ' ₽')} · "
        f"маржа {_display_telegram(latest['contribution_margin_pct'], '%')}"
    )
    lines.extend(["", "РЕКЛАМА"])
    if cpc["state"] in {"SUCCESS_ZERO", "SUCCESS_NONZERO"}:
        lines.append(f"CPC {payload['business_date']}: {cpc['state']} · spend {_display_telegram(cpc['spend'], ' ₽')}")
    else:
        lines.append(f"CPC {payload['business_date']}: {cpc['state']} · отчёт недоступен, нулём не считается")
    lines.extend(["", "ОПЕРАЦИИ",
                  f"Postings {payload['source_freshness']['postings']['state'].upper()} · Returns {payload['source_freshness']['returns']['state'].upper()} · Finance {payload['source_freshness']['finance']['state'].upper()}"])
    if payload["experiments"]:
        lines.extend(["", "ЭКСПЕРИМЕНТЫ"])
        for experiment in payload["experiments"]:
            config = experiment["target_config"]
            lines.append(
                f"{experiment['experiment_id']} · {experiment['status']} · {experiment['offer_id']} · "
                f"лимит {experiment['unit_limit']} шт./{experiment['duration_limit_days']} дн. · "
                f"start UNKNOWN · атрибуция недоступна"
            )
    events = payload["information_intelligence"]["events"]
    lines.extend(["", "ИНФОРМАЦИЯ"])
    if events:
        lines.extend(f"{event['severity']}: {event['source_title']} · {event['event_kind']}" for event in events)
    else:
        lines.append("Текущих событий нет")
    lines.extend(["", "НАЛОГ", _tax_line(payload), "", "ВНИМАНИЕ"])
    counts = {kind: sum(item["class"] == kind for item in payload["attention_items"])
              for kind in payload["attention_taxonomy"]}
    nonzero = [f"{kind} {count}" for kind, count in counts.items() if count]
    lines.append(" · ".join(nonzero) if nonzero else "Нет активных attention items")
    return "\n".join(lines)


def render_email_html(payload: dict[str, Any]) -> str:
    summary, current, latest = payload["summary"], payload["current_day_economics"], payload["latest_confirmed_economics"]
    cpc = payload["advertising"]["cpc"]
    offer_rows = "".join(
        f"<tr><td>{escape(item['offer_id'])}</td><td>{_display(item['demand']['ordered_units'])}</td>"
        f"<td>{_display(item['demand']['ordered_revenue'], ' ₽')}</td>"
        f"<td>{escape(item['latest_confirmed_economics']['confirmed_through_date'] or 'НЕТ ДАННЫХ')}</td>"
        f"<td>{_display(item['latest_confirmed_economics']['contribution_profit'], ' ₽')}</td></tr>"
        for item in payload["offers"]
    )
    return (
        "<!doctype html><html><body style=\"font-family:Arial,sans-serif;color:#1f2937\">"
        f"<h2>OZON Daily Commercial Brief v1.1 — {escape(payload['business_date'])}</h2>"
        f"<p><strong>Сегодня:</strong> {_display(summary['ordered_units'])} шт. / {_display(summary['ordered_revenue'], ' ₽')}</p>"
        f"<p><strong>Экономика сегодня:</strong> {escape(current['confirmation_state'])}. "
        f"<strong>Последняя подтверждённая:</strong> {_ru_date(latest['confirmed_through_date'])}, "
        f"вклад {_display(latest['contribution_profit'], ' ₽')}, маржа {_display(latest['contribution_margin_pct'], '%')}.</p>"
        f"<p><strong>CPC:</strong> {escape(cpc['state'])}; missing/pending/stuck не преобразуются в ноль.</p>"
        "<table border=\"1\" cellpadding=\"5\" cellspacing=\"0\"><tr><th>Offer</th><th>Units</th><th>Orders</th><th>Latest confirmed</th><th>Contribution</th></tr>"
        f"{offer_rows}</table>"
        f"<p><strong>{escape(_tax_line(payload))}</strong></p>"
        f"<p><strong>Information:</strong> ACTION_REQUIRED {payload['information_intelligence']['counts']['ACTION_REQUIRED']}; "
        f"WATCH {payload['information_intelligence']['counts']['WATCH']}.</p>"
        "</body></html>"
    )


def _font_path(explicit: str | None = None) -> str:
    candidates = [explicit, os.environ.get("EFA_PDF_FONT_PATH"),
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("No Cyrillic-capable PDF font found; set EFA_PDF_FONT_PATH")


def render_pdf(payload: dict[str, Any], output_path: str | Path, font_path: str | None = None) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle

    path = Path(output_path); path.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont("EFA", _font_path(font_path)))
    pdfmetrics.registerFont(TTFont("EFA-Bold", _font_path(font_path)))
    page_size = landscape(A4)

    def decorate(canvas, document):
        canvas.saveState(); canvas.setFont("EFA", 8); canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(14*mm, 8*mm, f"EFA OS · Daily Brief v1.1 · {payload['business_date']}")
        canvas.drawRightString(page_size[0]-14*mm, 8*mm, f"Страница {document.page}"); canvas.restoreState()

    document = BaseDocTemplate(str(path), pagesize=page_size, rightMargin=14*mm, leftMargin=14*mm,
                               topMargin=14*mm, bottomMargin=14*mm,
                               title=f"OZON Daily Commercial Brief v1.1 — {payload['business_date']}")
    document.addPageTemplates(PageTemplate(id="main", frames=[Frame(14*mm,14*mm,page_size[0]-28*mm,page_size[1]-28*mm,id="frame")], onPage=decorate))
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleEFA", parent=styles["Title"], fontName="EFA-Bold", fontSize=21, leading=25, textColor=colors.HexColor("#0f172a"))
    h1 = ParagraphStyle("H1EFA", parent=styles["Heading1"], fontName="EFA-Bold", fontSize=15, leading=18, textColor=colors.HexColor("#0f766e"))
    body = ParagraphStyle("BodyEFA", parent=styles["BodyText"], fontName="EFA", fontSize=8, leading=11, textColor=colors.HexColor("#334155"))
    small = ParagraphStyle("SmallEFA", parent=body, fontSize=6.7, leading=8.5)
    story: list[Any] = []

    def p(value: Any, style=body): return Paragraph(escape(str(value)), style)
    def heading(text: str): story.extend([Paragraph(text, h1), Spacer(1,3*mm)])
    def table(rows, widths=None, size=7):
        item = Table(rows, colWidths=widths, repeatRows=1)
        item.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),"EFA"),("FONTNAME",(0,0),(-1,0),"EFA-Bold"),
                                  ("FONTSIZE",(0,0),(-1,-1),size),("LEADING",(0,0),(-1,-1),size+2),
                                  ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#ccfbf1")),
                                  ("GRID",(0,0),(-1,-1),.35,colors.HexColor("#cbd5e1")),
                                  ("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),4),
                                  ("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),4),
                                  ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
        story.append(item)

    # Page 1 — executive summary, freshness, attention.
    story.extend([Paragraph("OZON Daily Commercial Brief v1.1", title),
                  p(f"Операционный день: {_ru_date(payload['business_date'])}"), Spacer(1,5*mm)])
    summary, current, latest = payload["summary"], payload["current_day_economics"], payload["latest_confirmed_economics"]
    table([["Заказано", "Сумма заказов", "Economics today", "Latest confirmed", "Contribution", "CPC"],
           [_display(summary["ordered_units"]," шт."), _display(summary["ordered_revenue"]," ₽"),
            current["confirmation_state"], _ru_date(latest["confirmed_through_date"]),
            _display(latest["contribution_profit"]," ₽"), payload["advertising"]["cpc"]["state"]]],
          [35*mm,42*mm,45*mm,42*mm,42*mm,42*mm],9)
    story.extend([Spacer(1,4*mm), p(finance_lag_text(payload)), Spacer(1,4*mm)])
    heading("Source freshness")
    table([["Источник","State","Business/source date","Run / detail"]] + [
        [name, value["state"], value.get("business_date") or value.get("latest_source_period") or value.get("checked_at") or "—",
         value.get("collection_ref") or value.get("run_status") or value.get("data_quality") or "—"]
        for name,value in payload["source_freshness"].items()], [45*mm,32*mm,60*mm,110*mm],7)
    story.extend([Spacer(1,4*mm)]); heading("Attention")
    for item in payload["attention_items"]: story.append(p(f"{item['severity']} · {item['class']} · {item['scope']} · {item['code']}", small))
    story.append(PageBreak())

    # Page 2 — offer-level current versus confirmed.
    heading("Продажи по offer и подтверждённая экономика")
    rows = [["Offer","SKU","Units today","Orders, ₽","Delivered","Returns","Today economics","Latest date","Latest revenue","Latest contribution","Margin"]]
    for item in payload["offers"]:
        current_offer, last = item["current_day"]["economics"], item["latest_confirmed_economics"]
        rows.append([item["offer_id"],str(item["sku"]),_display(item["demand"]["ordered_units"]),_display(item["demand"]["ordered_revenue"]),
                     _display(item["fulfilment"]["delivered_units"]),_display(item["fulfilment"]["returned_units"]),
                     current_offer["confirmation_state"],_ru_date(last["confirmed_through_date"]),_display(last["revenue"]),
                     _display(last["contribution_profit"]),_display(last["contribution_margin_pct"],"%")])
    table(rows,[22*mm,27*mm,19*mm,23*mm,20*mm,18*mm,28*mm,25*mm,25*mm,28*mm,20*mm],6.2)
    story.extend([Spacer(1,5*mm),p("NULL ≠ zero. Historical confirmed economics are never inserted into current-day fields."),PageBreak()])

    # Page 3 — advertising, operational state, experiments.
    heading("Advertising and operational state")
    cpc = payload["advertising"]["cpc"]
    table([["CPC date","Lifecycle state","External state","Spend","Orders","Error"],
           [cpc["business_date"],cpc["state"],cpc.get("external_state") or "—",_display(cpc["spend"]),_display(cpc["orders"]),p(cpc.get("error") or "—",small)]],
          [35*mm,38*mm,38*mm,32*mm,30*mm,75*mm],7)
    story.extend([Spacer(1,5*mm)]); heading("Experiments")
    exp_rows = [["ID","Offer","Status","Started","Configuration","Limits","Attribution"]]
    for exp in payload["experiments"]:
        config = exp["target_config"]
        config_text = f"action {config.get('action_id')} · seller {config.get('seller_price_rub')} · UI {config.get('action_ui_price_rub')} · Elastic {config.get('elastic_boost_pct')}% · CPC {config.get('cpc_enabled')}"
        limits = f"{exp['unit_limit']} units / {exp['duration_limit_days']} days / {_display(exp['loss_limit'],' ₽')}"
        exp_rows.append([p(exp["experiment_id"],small),exp["offer_id"],exp["status"],exp["started_at"] or "UNKNOWN",p(config_text,small),p(limits,small),p(exp["attribution_state"],small)])
    table(exp_rows,[43*mm,20*mm,22*mm,25*mm,72*mm,46*mm,45*mm],6.2)
    story.extend([Spacer(1,4*mm),p("Experiment performance is not calculated when started_at is unknown. Fixed annual insurance is not allocated to offers."),PageBreak()])

    # Page 4 — Information Intelligence and Tax Engine.
    heading("Information Intelligence")
    info_rows = [["Severity","Source","Event","Review","Effective","Confidence"]]
    for event in payload["information_intelligence"]["events"]:
        info_rows.append([event["severity"],p(event["source_title"],small),event["event_kind"],event["review_status"],event["effective_date"] or "—",event["confidence"]])
    table(info_rows,[30*mm,65*mm,55*mm,30*mm,35*mm,30*mm],7)
    story.extend([Spacer(1,5*mm)]); heading("Tax Engine")
    tax = payload["tax"]
    table([["Engine","Taxable revenue","Gross USN","Estimated payable","Additional 1%","Fixed obligation","Quality"],
           [tax["engine_state"],_display(tax["taxable_revenue"]," ₽"),_display(tax["gross_usn"]," ₽"),
            _display(tax["estimated_payable"]," ₽"),_display(tax["additional_1pct"]," ₽"),
            _display(tax["fixed_insurance_obligation"]," ₽"),tax["data_quality"]]],
          [30*mm,42*mm,35*mm,43*mm,35*mm,42*mm,32*mm],7)
    story.extend([Spacer(1,4*mm),p("The statutory state is produced by Tax Engine v0.1. Daily Brief does not recalculate tax and does not allocate the fixed annual obligation to SKU economics."),PageBreak()])

    # Page 5 — trend eligibility and data-quality notes.
    heading("Trend coverage and data-quality notes")
    trends = payload["extended_report_payload"]["trends"]
    trend_rows = [["Series","Overall state","Offer","Distinct valid days","Offer state"]]
    for name, block in trends.items():
        if block["series"]:
            for offer, state in block["series"].items(): trend_rows.append([name,block["status"],offer,state["distinct_business_days"],state["status"]])
        else:
            trend_rows.append([name,block["status"],"—",0,"INSUFFICIENT_DATA"])
    table(trend_rows,[38*mm,48*mm,38*mm,45*mm,58*mm],7)
    story.extend([Spacer(1,5*mm),p("Trend calculations require at least seven distinct valid business days per offer series. Short series remain INSUFFICIENT_DATA and are not extrapolated."),Spacer(1,3*mm)])
    for item in payload["attention_items"]:
        if item["class"] == "DATA_QUALITY": story.append(p(f"• {item['code']}: {item['message']}",small))
    document.build(story)
    return path
