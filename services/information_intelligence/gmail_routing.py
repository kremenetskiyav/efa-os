"""Deterministic routing for normalized Gmail evidence."""

from __future__ import annotations

from .gmail_readonly import NormalizedGmailMessage


ROUTINE_OPERATIONAL = "ROUTINE_OPERATIONAL"
EVENT_CANDIDATE = "EVENT_CANDIDATE"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

_RELEVANT = (
    ("commission", "COMMISSION"), ("комисси", "COMMISSION"),
    ("contract", "LEGAL"), ("договор", "LEGAL"), ("regulation", "LEGAL"), ("регламент", "LEGAL"),
    ("finance", "FINANCE"), ("финанс", "FINANCE"), ("document", "DOCUMENTS"), ("документ", "DOCUMENTS"),
    ("tariff", "LOGISTICS"), ("тариф", "LOGISTICS"), ("logistics", "LOGISTICS"), ("логист", "LOGISTICS"),
    ("premium", "PROMOTION"), ("акци", "PROMOTION"), ("promotion", "PROMOTION"),
    ("advertising", "ADVERTISING"), ("реклам", "ADVERTISING"), ("marking", "MARKING"), ("маркиров", "MARKING"),
    ("quality", "PRODUCT_CONTENT"), ("качест", "PRODUCT_CONTENT"), ("fbs", "FBS"), ("fbo", "FBO"),
)
_ROUTINE = ("есть новый заказ", "новый заказ", "статус заказа", "движение заказа", "движение товара", "остатк")


def route_message(message: NormalizedGmailMessage) -> tuple[str, str]:
    subject = message.subject.strip().lower()
    # Exact routine subjects are operational facts already covered by Seller API.
    # They must not be promoted because presentation HTML contains FBS/CSS text.
    if subject in {"есть новый заказ", "новый заказ"}:
        return ROUTINE_OPERATIONAL, message.classification
    text = f"{message.subject}\n{message.normalized_text}".lower()
    for phrase, domain in _RELEVANT:
        if phrase in text and ("измен" in text or phrase not in {"fbs", "fbo"}):
            return EVENT_CANDIDATE, domain
    if any(phrase in text for phrase in _ROUTINE):
        return ROUTINE_OPERATIONAL, message.classification
    return REVIEW_REQUIRED, "OTHER"
