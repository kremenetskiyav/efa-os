"""Deterministic legal-document canonicalization and economic change detection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import hashlib
import re
from typing import Iterable


class LegalDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class DocumentUnit:
    identity: str
    kind: str
    heading_path: tuple[str, ...]
    clause_number: str | None
    text: str
    fingerprint: str


@dataclass(frozen=True)
class CanonicalLegalDocument:
    raw_sha256: str
    canonical_sha256: str
    canonical_text: str
    units: tuple[DocumentUnit, ...]


@dataclass(frozen=True)
class NumericChange:
    numeric_type: str
    old_value: str
    new_value: str
    delta: str | None
    unit: str | None
    context: str
    section: str


@dataclass(frozen=True)
class UnitChange:
    change_type: str
    identity: str
    old_fingerprint: str | None
    new_fingerprint: str | None
    old_excerpt: str | None
    new_excerpt: str | None


@dataclass(frozen=True)
class LegalDiff:
    status: str
    changes: tuple[UnitChange, ...]
    numeric_changes: tuple[NumericChange, ...]
    watch_concepts: tuple[str, ...]
    affected_components: tuple[str, ...]
    severity: str
    requires_action: bool


BLOCK_TAGS = {"p": "paragraph", "li": "list_item", "tr": "table_row"}
SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "svg"}
CLAUSE_RE = re.compile(r"^\s*(\d+(?:\.\d+)+\.?)(?:\s+|$)")
SPACE_RE = re.compile(r"\s+")
ANTIBOT_MARKERS = (
    "captcha", "access denied", "redirect loop", "подтвердите, что вы не робот",
    "проверка браузера", "cloudflare ray id",
)


class _LegalHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.active: tuple[str, str] | None = None
        self.parts: list[str] = []
        self.blocks: list[tuple[str, str, str | None]] = []
        self.link: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "a":
            self.link = dict(attrs).get("href")
        if tag in {"td", "th"} and self.active and self.active[1] == "table_row" and self.parts:
            self.parts.append(" | ")
        kind = None
        if re.fullmatch(r"h[1-6]", tag):
            kind = tag
        elif tag in BLOCK_TAGS:
            kind = BLOCK_TAGS[tag]
        if kind:
            self._flush()
            self.active = (tag, kind)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag == "a":
            self.link = None
        if self.active and self.active[0] == tag:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self.skip_depth and self.active:
            self.parts.append(data)

    def _flush(self) -> None:
        if not self.active:
            self.parts.clear()
            return
        text = _normalize_text(" ".join(self.parts))
        if text:
            self.blocks.append((self.active[1], text, self.link))
        self.active = None
        self.parts.clear()

    def close(self) -> None:
        self._flush()
        super().close()


def _normalize_text(value: str) -> str:
    value = value.replace("\xa0", " ").replace("\u200b", "")
    return SPACE_RE.sub(" ", value).strip()


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise LegalDocumentError("legal source is not valid UTF-8 text")


def _reject_invalid_source(raw: bytes, text: str) -> None:
    if not raw or not text.strip():
        raise LegalDocumentError("legal source is empty")
    lowered = text.lower()
    if any(marker in lowered for marker in ANTIBOT_MARKERS):
        raise LegalDocumentError("anti-bot or access-denied page is not legal evidence")


def _text_blocks(text: str) -> list[tuple[str, str, str | None]]:
    return [("paragraph", item, None) for item in (_normalize_text(line) for line in text.splitlines()) if item]


def _units(blocks: Iterable[tuple[str, str, str | None]]) -> tuple[DocumentUnit, ...]:
    heading_levels: dict[int, str] = {}
    counters: dict[tuple[tuple[str, ...], str], int] = {}
    result: list[DocumentUnit] = []
    for kind, text, _link in blocks:
        if re.fullmatch(r"h[1-6]", kind):
            level = int(kind[1])
            heading_levels[level] = text
            for key in [item for item in heading_levels if item > level]:
                del heading_levels[key]
        heading_path = tuple(heading_levels[key] for key in sorted(heading_levels))
        clause_match = CLAUSE_RE.match(text)
        clause_number = clause_match.group(1).rstrip(".") if clause_match else None
        counter_key = (heading_path, kind)
        counters[counter_key] = counters.get(counter_key, 0) + 1
        if clause_number:
            identity = f"clause:{'/'.join(heading_path) or 'document'}:{clause_number}"
        elif re.fullmatch(r"h[1-6]", kind):
            identity = "heading:" + "/".join(heading_path)
        else:
            identity = f"{'/'.join(heading_path) or 'document'}:{kind}:{counters[counter_key]}"
        result.append(DocumentUnit(identity, kind, heading_path, clause_number, text, _fingerprint(text)))
    if not result:
        raise LegalDocumentError("legal source contains no semantic units")
    return tuple(result)


def canonicalize_legal(raw: bytes, *, content_type: str | None = None, filename: str | None = None) -> CanonicalLegalDocument:
    text = _decode(raw)
    _reject_invalid_source(raw, text)
    lower_name = (filename or "").lower()
    html = "html" in (content_type or "").lower() or lower_name.endswith((".html", ".htm")) or bool(re.search(r"<html|<!doctype", text, re.I))
    if html:
        parser = _LegalHTMLParser()
        try:
            parser.feed(text)
            parser.close()
        except Exception as error:
            raise LegalDocumentError("legal HTML cannot be parsed") from error
        blocks = parser.blocks
    elif (content_type and not any(item in content_type.lower() for item in ("text/plain", "text/markdown"))) or (lower_name and not lower_name.endswith((".txt", ".md"))):
        raise LegalDocumentError("unsupported legal document format")
    else:
        blocks = _text_blocks(text)
    units = _units(blocks)
    canonical_text = "\n".join(f"{unit.kind}\t{unit.identity}\t{unit.text}" for unit in units)
    return CanonicalLegalDocument(
        hashlib.sha256(raw).hexdigest(),
        hashlib.sha256(canonical_text.encode("utf-8")).hexdigest(),
        canonical_text,
        units,
    )


WATCH_PATTERNS = {
    "OZON_FUNDED_POINTS": ("балл", "лояльност"),
    "SELLER_COMMISSION": ("комисси", "вознагражден"),
    "FBS_LOGISTICS": ("fbs", "последн", "логист", "достав"),
    "RETURN_LOGISTICS": ("возврат", "обратн"),
    "PROMOTION_ECONOMICS": ("акци", "продвиж", "скидк", "boost"),
    "PERFORMANCE_ADVERTISING_TERMS": ("реклам", "performance", "ставк"),
    "FINANCE_SETTLEMENT": ("расчет", "начислен", "выплат", "платеж"),
    "LEGAL_ENTITY_BUYOUT": ("выкуп", "юридическ"),
    "DOCUMENT_FLOW": ("упд", "укд", "документ"),
    "PAYMENT_TIMING": ("срок оплат", "срок выплат", "дней"),
    "PENALTY_AND_FINE": ("штраф", "пеня", "неустойк"),
}

IMPACT_MAP = {
    "SELLER_COMMISSION": ("Profit Engine", "Price Engine", "Commercial Recovery Review"),
    "FBS_LOGISTICS": ("Profit Engine", "Price Engine", "FBS operations"),
    "OZON_FUNDED_POINTS": ("Commercial Revenue model review",),
    "PROMOTION_ECONOMICS": ("Promotion Monitoring", "Price Engine"),
    "PERFORMANCE_ADVERTISING_TERMS": ("CPC review",),
    "FINANCE_SETTLEMENT": ("Profit Engine", "Finance reconciliation"),
    "LEGAL_ENTITY_BUYOUT": ("Finance", "Documents", "TAX_REVIEW_ONLY"),
    "DOCUMENT_FLOW": ("Documents", "TAX_REVIEW_ONLY"),
    "PAYMENT_TIMING": ("Finance reconciliation",),
    "RETURN_LOGISTICS": ("Profit Engine", "Return reserve review"),
    "PENALTY_AND_FINE": ("Profit Engine", "Operational risk review"),
}


def detect_watch_concepts(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(sorted(name for name, terms in WATCH_PATTERNS.items() if any(term in lowered for term in terms)))


NUMBER_PATTERNS = (
    ("PERCENTAGE", re.compile(r"(?<!\w)(\d+(?:[.,]\d+)?)\s*%"), "%"),
    ("RUB_AMOUNT", re.compile(r"(?<!\w)(\d[\d\s]*(?:[.,]\d+)?)\s*(?:руб(?:\.|лей|ля)?\b|₽|rub\b)", re.I), "RUB"),
    ("DATE", re.compile(r"(?<!\d)(\d{2}\.\d{2}\.\d{4})(?!\d)"), None),
    ("COEFFICIENT", re.compile(r"(?:коэффициент\w*(?:\s+\w+){0,4}\s*(?:=|:)?\s*)(\d+[.,]\d+)", re.I), None),
    ("DEADLINE_OR_LIMIT", re.compile(r"(?<!\w)(\d+(?:[.,]\d+)?)\s*(дн(?:я|ей)?|час(?:а|ов)?|шт\.?|единиц\w*|кг)\b", re.I), None),
)


def _numbers(text: str) -> dict[str, list[tuple[str, str | None]]]:
    found: dict[str, list[tuple[str, str | None]]] = {}
    for kind, pattern, fixed_unit in NUMBER_PATTERNS:
        for match in pattern.finditer(text):
            unit = fixed_unit or (match.group(2) if match.lastindex and match.lastindex >= 2 else None)
            found.setdefault(kind, []).append((match.group(1).replace(" ", "").replace(",", "."), unit))
    return found


def _delta(kind: str, old: str, new: str) -> str | None:
    if kind == "DATE":
        return None
    try:
        return str(Decimal(new) - Decimal(old))
    except InvalidOperation:
        return None


def detect_numeric_changes(old_text: str, new_text: str, section: str) -> tuple[NumericChange, ...]:
    old_numbers, new_numbers = _numbers(old_text), _numbers(new_text)
    result: list[NumericChange] = []
    for kind in sorted(set(old_numbers) | set(new_numbers)):
        old_values, new_values = old_numbers.get(kind, []), new_numbers.get(kind, [])
        for old, new in zip(old_values, new_values):
            if old == new:
                continue
            context = _normalize_text(new_text)[:240]
            result.append(NumericChange(kind, old[0], new[0], _delta(kind, old[0], new[0]), new[1] or old[1], context, section))
    return tuple(result)


def _excerpt(text: str | None) -> str | None:
    return text if text is None or len(text) <= 300 else text[:297] + "..."


def diff_legal(old: CanonicalLegalDocument, new: CanonicalLegalDocument, *, effective_now: bool = False) -> LegalDiff:
    if old.canonical_sha256 == new.canonical_sha256:
        return LegalDiff("SUCCESS_ZERO", (), (), (), (), "INFO", False)
    old_by_id = {unit.identity: unit for unit in old.units}
    new_by_id = {unit.identity: unit for unit in new.units}
    changes: list[UnitChange] = []
    numeric: list[NumericChange] = []
    matched_old: set[str] = set()
    matched_new: set[str] = set()
    for identity in sorted(old_by_id.keys() & new_by_id.keys()):
        previous, current = old_by_id[identity], new_by_id[identity]
        matched_old.add(identity); matched_new.add(identity)
        if previous.fingerprint != current.fingerprint:
            changes.append(UnitChange("MODIFIED", identity, previous.fingerprint, current.fingerprint, _excerpt(previous.text), _excerpt(current.text)))
            numeric.extend(detect_numeric_changes(previous.text, current.text, " / ".join(current.heading_path) or identity))
    remaining_old = [unit for unit in old.units if unit.identity not in matched_old]
    remaining_new = [unit for unit in new.units if unit.identity not in matched_new]
    def movement_fingerprint(unit: DocumentUnit) -> str:
        semantic_text = CLAUSE_RE.sub("", unit.text, count=1) if unit.clause_number else unit.text
        return _fingerprint(semantic_text)

    new_by_fingerprint = {movement_fingerprint(unit): unit for unit in remaining_new}
    for previous in remaining_old:
        moved = new_by_fingerprint.pop(movement_fingerprint(previous), None)
        if moved:
            matched_new.add(moved.identity)
            changes.append(UnitChange("MOVED_OR_RENUMBERED", moved.identity, previous.fingerprint, moved.fingerprint, _excerpt(previous.text), _excerpt(moved.text)))
        else:
            changes.append(UnitChange("REMOVED", previous.identity, previous.fingerprint, None, _excerpt(previous.text), None))
    for current in remaining_new:
        if current.identity not in matched_new:
            changes.append(UnitChange("ADDED", current.identity, None, current.fingerprint, None, _excerpt(current.text)))
    changed_text = "\n".join(filter(None, [item.old_excerpt for item in changes] + [item.new_excerpt for item in changes]))
    concepts = detect_watch_concepts(changed_text)
    affected = tuple(sorted({component for concept in concepts for component in IMPACT_MAP.get(concept, ())}))
    if concepts and numeric:
        severity = "CRITICAL" if effective_now else "ACTION_REQUIRED"
    elif concepts:
        severity = "WATCH"
    else:
        severity = "INFO"
    return LegalDiff("DOCUMENT_CHANGED", tuple(changes), tuple(numeric), concepts, affected, severity, severity in {"ACTION_REQUIRED", "CRITICAL"})


def structural_preview(document: CanonicalLegalDocument) -> dict:
    text = "\n".join(unit.text for unit in document.units)
    return {
        "units": [asdict(unit) for unit in document.units],
        "unit_count": len(document.units),
        "watch_concepts": list(detect_watch_concepts(text)),
        "numeric_facts": {kind: values for kind, values in _numbers(text).items()},
    }
