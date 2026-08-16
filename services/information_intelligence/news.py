"""Deterministic Seller News fallback contract for operator-supplied evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .legal import CanonicalLegalDocument, canonicalize_legal, diff_legal, detect_watch_concepts


SOURCE_ID = "OZON_SELLER_NEWS"
CANONICAL_LISTING_URL = "https://seller.ozon.ru/media/news/"
TRACKING_QUERY_KEYS = {"gclid", "yclid", "ref", "referrer"}


class NewsEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class NewsEvidence:
    canonical_url: str
    title: str
    published_at: str
    body: str
    content_type: str
    stable_id: str | None = None
    updated_at: str | None = None
    category: str | None = None
    official_links: tuple[str, ...] = ()


@dataclass(frozen=True)
class CanonicalNewsArticle:
    identity: str
    canonical_url: str
    title: str
    published_at: str
    updated_at: str | None
    category: str | None
    official_links: tuple[str, ...]
    raw_sha256: str
    canonical_sha256: str
    document: CanonicalLegalDocument
    domains: tuple[str, ...]
    watch_concepts: tuple[str, ...]
    effective_date: str | None
    effective_context: str | None


@dataclass(frozen=True)
class NewsDiff:
    status: str
    classification: str
    severity: str
    requires_action: bool
    watch_concepts: tuple[str, ...]
    domains: tuple[str, ...]


DOMAIN_PATTERNS = {
    "PRICING": ("цен", "price"),
    "COMMISSION": ("комисси",),
    "LOGISTICS": ("логист", "достав"),
    "FBS": ("fbs", "отгруз"),
    "FBO": ("fbo", "склад ozon"),
    "PROMOTION": ("акци", "продвиж", "скидк"),
    "ADVERTISING": ("реклам", "cpc", "cpo"),
    "FINANCE": ("финанс", "выплат", "расчёт", "расчет"),
    "RETURNS": ("возврат", "невыкуп"),
    "PRODUCT_CONTENT": ("карточк", "контент"),
    "API": ("api", "интеграц"),
    "LEGAL": ("договор", "правил", "юридическ"),
    "MARKING": ("маркиров",),
    "WAREHOUSE": ("склад", "приёмк", "приемк"),
    "DOCUMENTS": ("упд", "укд", "документ"),
}

EFFECTIVE_DATE_RE = re.compile(
    r"(?P<context>(?:вступает\s+в\s+силу|действует\s+с|начиная\s+с|с)\s+"
    r"(?P<date>\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|"
    r"сентября|октября|ноября|декабря)\s+\d{4})(?:\s+г(?:ода|\.))?)",
    re.IGNORECASE,
)


def normalize_official_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme != "https" or not parts.hostname or not parts.hostname.endswith("ozon.ru"):
        raise NewsEvidenceError("news evidence URL must be official Ozon HTTPS")
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_KEYS
    ]
    path = parts.path or "/"
    return urlunsplit(("https", parts.netloc.lower(), path, urlencode(sorted(query)), ""))


def _domains(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    matched = tuple(sorted(name for name, patterns in DOMAIN_PATTERNS.items() if any(term in lowered for term in patterns)))
    return matched or ("OTHER",)


def _effective_date(text: str) -> tuple[str | None, str | None]:
    match = EFFECTIVE_DATE_RE.search(text)
    if not match:
        return None, None
    return match.group("date"), match.group("context")


def canonicalize_news(evidence: NewsEvidence) -> CanonicalNewsArticle:
    url = normalize_official_url(evidence.canonical_url)
    links = tuple(sorted({normalize_official_url(item) for item in evidence.official_links}))
    if not evidence.title.strip() or not evidence.published_at.strip() or not evidence.body.strip():
        raise NewsEvidenceError("title, published_at and body are required")
    document = canonicalize_legal(
        evidence.body.encode("utf-8"),
        content_type=evidence.content_type,
        filename="article.html" if "html" in evidence.content_type else "article.txt",
    )
    semantic_text = "\n".join((evidence.title.strip(), document.canonical_text))
    effective_date, effective_context = _effective_date(semantic_text)
    payload = {
        "identity": evidence.stable_id.strip() if evidence.stable_id else url,
        "canonical_url": url,
        "title": evidence.title.strip(),
        "published_at": evidence.published_at.strip(),
        "updated_at": evidence.updated_at.strip() if evidence.updated_at else None,
        "category": evidence.category.strip() if evidence.category else None,
        "official_links": links,
        "units": [asdict(unit) for unit in document.units],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return CanonicalNewsArticle(
        identity=payload["identity"],
        canonical_url=url,
        title=payload["title"],
        published_at=payload["published_at"],
        updated_at=payload["updated_at"],
        category=payload["category"],
        official_links=links,
        raw_sha256=hashlib.sha256(evidence.body.encode("utf-8")).hexdigest(),
        canonical_sha256=hashlib.sha256(canonical).hexdigest(),
        document=document,
        domains=_domains(semantic_text),
        watch_concepts=detect_watch_concepts(semantic_text),
        effective_date=effective_date,
        effective_context=effective_context,
    )


def diff_news(old: CanonicalNewsArticle | None, new: CanonicalNewsArticle) -> NewsDiff:
    if old is None:
        return NewsDiff("NEW", "INFO_ONLY", "INFO", False, new.watch_concepts, new.domains)
    if old.identity != new.identity:
        raise NewsEvidenceError("article identity mismatch")
    if old.canonical_sha256 == new.canonical_sha256:
        return NewsDiff("NO_CHANGE", "INFO_ONLY", "INFO", False, (), ())
    legal_diff = diff_legal(old.document, new.document)
    watch = tuple(sorted(set(old.watch_concepts) | set(new.watch_concepts) | set(legal_diff.watch_concepts)))
    domains = tuple(sorted(set(old.domains) | set(new.domains)))
    numeric_review = bool(legal_diff.numeric_changes and watch)
    return NewsDiff("UPDATED", "REVIEW", "ACTION_REQUIRED" if numeric_review else "WATCH", numeric_review, watch, domains)


def listing_fingerprint(articles: tuple[CanonicalNewsArticle, ...]) -> str:
    values = sorted((article.identity, article.canonical_sha256) for article in articles)
    raw = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
