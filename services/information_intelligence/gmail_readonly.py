"""Small, read-only Gmail API boundary for Ozon Information Intelligence."""

from __future__ import annotations

from base64 import urlsafe_b64decode
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parseaddr
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_API_ROOT = "https://gmail.googleapis.com/gmail/v1/users/me"
ALLOWED_GMAIL_OPERATIONS = frozenset({"messages.list", "messages.get"})
MAX_CANDIDATE_MESSAGES = 50


def credential_root() -> Path:
    return Path.home() / ".efa-os" / "credentials" / "gmail_ozon_readonly"


def token_path() -> Path:
    return credential_root() / "token.json"


def client_config_path() -> Path:
    return credential_root() / "client.json"


def require_exact_scope(scopes: object) -> None:
    if not isinstance(scopes, (list, tuple, set)) or set(scopes) != {GMAIL_READONLY_SCOPE}:
        raise ValueError("Gmail token must have exactly gmail.readonly scope")


def load_token(path: Path | None = None) -> dict[str, Any]:
    path = path or token_path()
    token = json.loads(path.read_text(encoding="utf-8"))
    require_exact_scope(token.get("scopes"))
    if not isinstance(token.get("access_token"), str) or not token["access_token"]:
        raise ValueError("Gmail token is missing access_token")
    return token


def _decode(data: str) -> str:
    padding = "=" * (-len(data) % 4)
    return urlsafe_b64decode((data + padding).encode("ascii")).decode("utf-8", errors="replace")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "head", "noscript"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "head", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(self.parts)


def normalize_text(value: str, *, html: bool = False) -> str:
    if html:
        parser = _TextExtractor()
        parser.feed(value)
        value = parser.text
    return re.sub(r"\s+", " ", value).strip()


def decode_rfc2047_header(value: str | None) -> tuple[str, str]:
    """Return decoded header and data quality without throwing on broken mail."""
    if not value:
        return "", "VALID"
    quality = "VALID"
    fragments: list[str] = []
    try:
        chunks = decode_header(value)
    except (TypeError, ValueError):
        return normalize_text(str(value)), "REVIEW_REQUIRED"
    for fragment, charset in chunks:
        if isinstance(fragment, str):
            fragments.append(fragment)
            continue
        try:
            fragments.append(fragment.decode(charset or "ascii", errors="strict"))
        except (LookupError, UnicodeDecodeError):
            quality = "REVIEW_REQUIRED"
            fragments.append(fragment.decode("utf-8", errors="replace"))
    decoded = normalize_text("".join(fragments))
    if "\ufffd" in decoded:
        quality = "REVIEW_REQUIRED"
    return decoded, quality


def _walk_parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = [payload]
    for child in payload.get("parts") or []:
        if isinstance(child, dict):
            result.extend(_walk_parts(child))
    return result


def _body(payload: dict[str, Any]) -> str:
    parts = _walk_parts(payload)
    for mime_type, html in (("text/plain", False), ("text/html", True)):
        for part in parts:
            if part.get("mimeType") == mime_type and isinstance(part.get("body", {}).get("data"), str):
                return normalize_text(_decode(part["body"]["data"]), html=html)
    return ""


def _headers(payload: dict[str, Any]) -> tuple[dict[str, str], str]:
    output: dict[str, str] = {}
    quality = "VALID"
    for header in payload.get("headers") or []:
        if not isinstance(header, dict):
            continue
        name = str(header.get("name", "")).lower()
        decoded, header_quality = decode_rfc2047_header(str(header.get("value", "")))
        output[name] = decoded
        if header_quality != "VALID":
            quality = "REVIEW_REQUIRED"
    return output, quality


def _attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for part in _walk_parts(payload):
        body = part.get("body") or {}
        attachment_id = body.get("attachmentId")
        if attachment_id:
            output.append({
                "filename": part.get("filename") or None,
                "mime_type": part.get("mimeType") or None,
                "size": body.get("size") if isinstance(body.get("size"), int) else None,
                "attachment_id": attachment_id,
            })
    return output


def _official_links(text: str) -> list[str]:
    links = re.findall(r"https?://[^\s<>()]+", text)
    return sorted({link.rstrip(".,;:)") for link in links if re.search(r"https?://([\w-]+\.)*ozon\.ru(?:/|$)", link, re.I)})


def is_confirmed_ozon(sender_domain: str | None, subject: str, body: str, links: list[str]) -> bool:
    sender_is_ozon = bool(sender_domain and (sender_domain == "ozon.ru" or sender_domain.endswith(".ozon.ru")))
    context_is_ozon = bool(re.search(r"\bozon\b|озон", f"{subject}\n{body}", re.I) or links)
    return sender_is_ozon and context_is_ozon


@dataclass(frozen=True)
class NormalizedGmailMessage:
    gmail_message_id: str
    rfc_message_id: str | None
    thread_id: str | None
    received_at: str | None
    sender: str | None
    sender_domain: str | None
    subject: str
    normalized_text: str
    official_links: tuple[str, ...]
    attachments: tuple[dict[str, Any], ...]
    content_hash: str
    classification: str
    confirmed_ozon: bool
    header_data_quality: str


def normalize_message(message: dict[str, Any]) -> NormalizedGmailMessage:
    payload = message.get("payload") or {}
    headers, header_data_quality = _headers(payload)
    sender_name, sender_address = parseaddr(headers.get("from", ""))
    sender = sender_address or headers.get("from") or None
    sender_domain = sender_address.rsplit("@", 1)[-1].lower() if "@" in sender_address else None
    subject = normalize_text(headers.get("subject", ""))
    body = _body(payload)
    links = _official_links(body)
    received_at = None
    if str(message.get("internalDate", "")).isdigit():
        received_at = datetime.fromtimestamp(int(message["internalDate"]) / 1000, timezone.utc).isoformat()
    confirmed = is_confirmed_ozon(sender_domain, subject, body, links)
    classification = "OTHER / REVIEW_REQUIRED"
    lower = f"{subject}\n{body}".lower()
    for word, domain in (("комис", "COMMISSION"), ("логист", "LOGISTICS"), ("fbs", "FBS"), ("акци", "PROMOTION"), ("реклам", "ADVERTISING"), ("финанс", "FINANCE"), ("возврат", "RETURNS"), ("api", "API"), ("договор", "LEGAL")):
        if word in lower:
            classification = domain
            break
    # Content identity is deliberately independent of Gmail and RFC transport IDs.
    # Those IDs are primary and secondary replay keys; this hash detects the same
    # normalized evidence received through a different message or thread.
    identity = {"sender_domain": sender_domain, "subject": subject, "body": body, "official_links": links}
    content_hash = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return NormalizedGmailMessage(
        gmail_message_id=str(message.get("id", "")), rfc_message_id=headers.get("message-id"),
        thread_id=message.get("threadId"), received_at=received_at, sender=sender,
        sender_domain=sender_domain, subject=subject, normalized_text=body,
        official_links=tuple(links), attachments=tuple(_attachments(payload)), content_hash=content_hash,
        classification=classification, confirmed_ozon=confirmed,
        header_data_quality=header_data_quality,
    )


def gmail_get(token: dict[str, Any], url: str, *, opener: Callable = urlopen) -> dict[str, Any]:
    if not url.startswith(f"{GMAIL_API_ROOT}/messages"):
        raise ValueError("Only Gmail messages.list/messages.get are allowed")
    request = Request(url, headers={"Authorization": f"Bearer {token['access_token']}", "Accept": "application/json"}, method="GET")
    with opener(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def collect_recent(token: dict[str, Any], days: int, *, opener: Callable = urlopen) -> dict[str, Any]:
    normalized = read_recent_messages(token, days, opener=opener)
    ozon = [item for item in normalized if item.confirmed_ozon]
    return {
        "status": "SUCCESS_ZERO" if not ozon else "SUCCESS",
        "candidate_message_count": len(normalized), "confirmed_ozon_message_count": len(ozon),
        "messages": [{"gmail_message_id": item.gmail_message_id, "received_at": item.received_at,
                      "sender": item.sender, "sender_domain": item.sender_domain, "subject": item.subject,
                      "attachment_count": len(item.attachments), "classification": item.classification,
                      "header_data_quality": item.header_data_quality,
                      "content_hash": item.content_hash} for item in ozon],
    }


def read_recent_messages(token: dict[str, Any], days: int, *, opener: Callable = urlopen) -> list[NormalizedGmailMessage]:
    if not 1 <= days <= 30:
        raise ValueError("days must be between 1 and 30")
    require_exact_scope(token.get("scopes"))
    query = urlencode({"q": f"newer_than:{days}d", "maxResults": MAX_CANDIDATE_MESSAGES})
    listing = gmail_get(token, f"{GMAIL_API_ROOT}/messages?{query}", opener=opener)
    refs = listing.get("messages") or []
    normalized: list[NormalizedGmailMessage] = []
    for ref in refs:
        if not isinstance(ref, dict) or not ref.get("id"):
            continue
        raw = gmail_get(token, f"{GMAIL_API_ROOT}/messages/{ref['id']}?format=full", opener=opener)
        normalized.append(normalize_message(raw))
    return normalized
