"""Deterministic normalization for seller-authenticated manual evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib


MANUAL_SOURCE_ID = "OZON_SELLER_MAIN_MANUAL"
MANUAL_AUTHORITY = "SELLER_AUTHENTICATED_UI_MANUAL_EVIDENCE"


@dataclass(frozen=True)
class ManualEvidence:
    published_date: str
    channel: str
    title: str
    themes: tuple[str, ...]
    domains: tuple[str, ...]
    severity: str
    requires_action: bool
    affected_components: tuple[str, ...]
    effective_date: str | None
    correlation: str
    data_quality: str = "MANUAL_SELLER_UI_SUMMARY"
    review_status: str = "PENDING"

    @property
    def normalized_text(self) -> str:
        return "\n".join((
            f"Дата наблюдения: {self.published_date}",
            f"Канал: {self.channel}",
            f"Заголовок: {self.title}",
            "Подтверждённые темы:",
            *(f"- {theme}" for theme in self.themes),
        ))

    @property
    def content_sha256(self) -> str:
        value = "\n".join((MANUAL_SOURCE_ID, self.normalized_text))
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @property
    def event_key(self) -> str:
        return f"manual-evidence:{MANUAL_SOURCE_ID}:{self.content_sha256}"

    @property
    def evidence_reference(self) -> str:
        return f"seller-ui-main:manual-observation:{self.published_date}:{self.content_sha256[:12]}"


SELLER_MAIN_NOTICES = (
    ManualEvidence(
        published_date="2026-08-13",
        channel="FBS: новости о схеме",
        title="FBS: как избежать ошибок при отгрузке",
        themes=(
            "Правила FBS-отгрузок.",
            "Доверительная приёмка и предварительная сортировка.",
            "Указанная операционная дата: 14.08.2026.",
            "Требования к упаковке.",
            "Сроки регистрации отгрузки.",
            "Возможное влияние скидки на тариф и штрафа за позднюю отгрузку.",
            "Ссылки на официальные FBS-регламенты и базу знаний.",
        ),
        domains=("FBS", "LOGISTICS", "FINANCE"),
        severity="ACTION_REQUIRED",
        requires_action=True,
        affected_components=(
            "FBS operations",
            "Finance reconciliation",
            "Profit Engine",
            "Price Engine",
            "Daily operational review",
        ),
        effective_date="2026-08-14",
        correlation="POTENTIAL_CORRELATION",
    ),
    ManualEvidence(
        published_date="2026-08-11",
        channel="Финансы и документы",
        title="Открыли продажи юрлицам через выкупы",
        themes=(
            "Механика выкупа товаров маркетплейсом для последующей продажи юридическому лицу.",
            "Применимость к FBS/FBO с учётом исключений.",
            "Коэффициент цены выкупа.",
            "Стандартные тарифы логистики.",
            "Документооборот УПД/УКД.",
            "Процесс расчётов и выплат.",
            "Ссылки на официальную информацию.",
        ),
        domains=("FINANCE", "DOCUMENTS", "PRICING", "FBS", "FBO", "TAX_REVIEW_ONLY"),
        severity="WATCH",
        requires_action=False,
        affected_components=(
            "Finance",
            "Documents",
            "Profit Engine",
            "Price Engine",
            "TAX_REVIEW_ONLY",
            "FBS operations",
            "FBO operations",
        ),
        effective_date=None,
        correlation="POTENTIAL_CORRELATION",
    ),
)


def daily_brief_preview(notices: tuple[ManualEvidence, ...] = SELLER_MAIN_NOTICES) -> str:
    """Render a compact deterministic future-only preview; it sends nothing."""
    lines = ["OZON CHANGES"]
    for notice in notices:
        lines.extend((
            "",
            notice.severity.replace("ACTION_REQUIRED", "ACTION REQUIRED"),
            notice.title,
            f"Наблюдение: {notice.published_date} · {notice.channel}",
        ))
        if notice.effective_date:
            lines.append(f"Операционная дата: {notice.effective_date}")
        lines.append("Требуется review подтверждённых условий; автоматических действий нет.")
    return "\n".join(lines)
