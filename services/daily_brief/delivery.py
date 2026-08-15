"""Channel-independent Daily Brief delivery contract (no transport credentials)."""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Callable, Protocol

REPORT_VERSION = "v0.1"
TARGET_SCHEDULE = "08:15 Europe/Moscow"


class DeliveryLedger(Protocol):
    def is_delivered(self, key: str) -> bool: ...
    def mark_delivered(self, key: str) -> None: ...


@dataclass
class InMemoryDeliveryLedger:
    delivered: set[str] = field(default_factory=set)

    def is_delivered(self, key: str) -> bool:
        return key in self.delivered

    def mark_delivered(self, key: str) -> None:
        self.delivered.add(key)


def brief_id(payload: dict[str, Any]) -> str:
    stable = f"{REPORT_VERSION}:{payload['business_date']}:{payload.get('generated_at', '')}"
    return sha256(stable.encode("utf-8")).hexdigest()[:16]


def delivery_key(channel: str, business_date: str, *, test_mode: bool = False, report_id: str | None = None) -> str:
    scope = f"test:{report_id or 'manual'}" if test_mode else "production"
    return f"daily-brief:{REPORT_VERSION}:{scope}:{channel}:{business_date}"


def deliver_channels(
    payload: dict[str, Any], ledger: DeliveryLedger,
    pdf_renderer: Callable[[dict[str, Any]], str],
    email_sender: Callable[[str, str, str, str], None],
    telegram_sender: Callable[[str], None],
    html_renderer: Callable[[dict[str, Any]], str],
    telegram_renderer: Callable[[dict[str, Any]], str],
    *, recipient: str, test_mode: bool = False,
) -> dict[str, Any]:
    """Deliver channels independently; successful channels remain idempotent."""
    report_id = brief_id(payload)
    result: dict[str, Any] = {
        "brief_id": report_id, "business_date": payload["business_date"],
        "report_version": REPORT_VERSION, "test_mode": test_mode,
        "stale_data_warning": bool(payload.get("data_quality", {}).get("warnings")),
        "channels": {},
    }
    email_key = delivery_key("email", payload["business_date"], test_mode=test_mode, report_id=report_id)
    telegram_key = delivery_key("telegram", payload["business_date"], test_mode=test_mode, report_id=report_id)

    if ledger.is_delivered(email_key):
        result["channels"]["email"] = {"status": "SKIPPED_DUPLICATE", "idempotency_key": email_key}
    else:
        try:
            pdf_path = pdf_renderer(payload)
            subject = f"OZON Daily Commercial Brief — {payload['business_date']}"
            email_sender(recipient, subject, html_renderer(payload), pdf_path)
            ledger.mark_delivered(email_key)
            result["channels"]["email"] = {"status": "SUCCESS", "idempotency_key": email_key}
        except Exception as error:
            stage = "PDF_RENDER_FAILED" if "pdf_path" not in locals() else "EMAIL_FAILED"
            result["channels"]["email"] = {"status": stage, "idempotency_key": email_key,
                                                     "error": type(error).__name__}

    if ledger.is_delivered(telegram_key):
        result["channels"]["telegram"] = {"status": "SKIPPED_DUPLICATE", "idempotency_key": telegram_key}
    else:
        try:
            telegram_sender(telegram_renderer(payload))
            ledger.mark_delivered(telegram_key)
            result["channels"]["telegram"] = {"status": "SUCCESS", "idempotency_key": telegram_key}
        except Exception as error:
            result["channels"]["telegram"] = {"status": "TELEGRAM_FAILED", "idempotency_key": telegram_key,
                                                        "error": type(error).__name__}
    return result
