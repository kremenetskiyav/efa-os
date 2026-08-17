"""Local, interactive bootstrap for the dedicated Gmail read-only token."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
import webbrowser

from .gmail_readonly import GMAIL_READONLY_SCOPE, client_config_path, credential_root, require_exact_scope, token_path


REDIRECT_URI = "http://127.0.0.1:8765/oauth2/callback"
AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def load_client_config(path: Path | None = None) -> dict[str, str]:
    config = json.loads((path or client_config_path()).read_text(encoding="utf-8"))
    required = ("client_id", "client_secret", "redirect_uri")
    if any(not isinstance(config.get(key), str) or not config[key] for key in required):
        raise ValueError("client config must contain client_id, client_secret and redirect_uri")
    if config["redirect_uri"] != REDIRECT_URI:
        raise ValueError(f"redirect_uri must be exactly {REDIRECT_URI}")
    return config


def authorization_url(client_id: str, state: str) -> str:
    return f"{AUTHORIZATION_URL}?{urlencode({'client_id': client_id, 'redirect_uri': REDIRECT_URI, 'response_type': 'code', 'scope': GMAIL_READONLY_SCOPE, 'access_type': 'offline', 'prompt': 'consent', 'state': state})}"


def _callback(state: str) -> str:
    received: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            values = parse_qs(parsed.query)
            received["state"] = values.get("state", [""])[0]
            received["code"] = values.get("code", [""])[0]
            received["error"] = values.get("error", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("EFA OS authorization received. You may close this window.".encode("utf-8"))

        def log_message(self, *_: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 8765), Handler)
    server.timeout = 300
    while not received:
        server.handle_request()
    if received.get("state") != state or not received.get("code"):
        raise RuntimeError("OAuth callback rejected or cancelled")
    return received["code"]


def _exchange(client: dict[str, str], code: str) -> dict:
    payload = urlencode({"code": code, "client_id": client["client_id"], "client_secret": client["client_secret"], "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code"}).encode()
    request = Request(TOKEN_URL, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urlopen(request, timeout=20) as response:
        token = json.loads(response.read().decode("utf-8"))
    scopes = token.get("scope", "").split()
    require_exact_scope(scopes)
    token["scopes"] = scopes
    return token


def main() -> None:
    client = load_client_config()
    state = secrets.token_urlsafe(32)
    webbrowser.open(authorization_url(client["client_id"], state))
    token = _exchange(client, _callback(state))
    root = credential_root()
    root.mkdir(parents=True, exist_ok=True)
    target = token_path()
    target.write_text(json.dumps(token, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        target.chmod(0o600)
    except OSError:
        pass
    print("Gmail read-only token stored in protected local credential area.")


if __name__ == "__main__":
    main()
