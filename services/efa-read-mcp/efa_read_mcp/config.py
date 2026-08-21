"""Environment-only configuration with secret-safe validation."""

from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator


EXPECTED_DATABASE = "efa"
EXPECTED_ROLE = "efa_mcp_readonly"


class ConfigurationError(RuntimeError):
    """A safe startup error that never includes configuration values."""


class Settings(BaseModel):
    """Validated process settings. DATABASE_URL remains masked in representations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    database_url: SecretStr
    pool_min_size: int = Field(default=1, ge=1, le=4)
    pool_max_size: int = Field(default=4, ge=1, le=8)
    statement_timeout_ms: int = Field(default=10_000, ge=1_000, le=30_000)
    lock_timeout_ms: int = Field(default=3_000, ge=100, le=5_000)
    http_host: str = Field(default="0.0.0.0", min_length=1)
    http_port: int = Field(default=8000, ge=1, le=65_535)
    http_path: str = Field(default="/mcp", pattern=r"^/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*$")

    @model_validator(mode="after")
    def validate_database_target(self) -> "Settings":
        if self.pool_min_size > self.pool_max_size:
            raise ValueError("pool_min_size must not exceed pool_max_size")

        value = self.database_url.get_secret_value()
        normalized = _normalize_driver_scheme(value)
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"postgresql", "postgres"}:
            raise ValueError("DATABASE_URL must use the PostgreSQL protocol")
        if parsed.username != EXPECTED_ROLE:
            raise ValueError("DATABASE_URL must authenticate as the dedicated MCP read-only role")
        if parsed.path.lstrip("/") != EXPECTED_DATABASE:
            raise ValueError("DATABASE_URL must target the EFA database")
        if not parsed.hostname:
            raise ValueError("DATABASE_URL must include a database host")
        return self

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if environ is None else environ
        database_url = source.get("DATABASE_URL")
        if database_url is None or not database_url.strip():
            raise ConfigurationError("DATABASE_URL is required")

        try:
            return cls(
                database_url=SecretStr(database_url),
                pool_min_size=_read_int(source, "EFA_MCP_POOL_MIN_SIZE", 1),
                pool_max_size=_read_int(source, "EFA_MCP_POOL_MAX_SIZE", 4),
                statement_timeout_ms=_read_int(source, "EFA_MCP_STATEMENT_TIMEOUT_MS", 10_000),
                lock_timeout_ms=_read_int(source, "EFA_MCP_LOCK_TIMEOUT_MS", 3_000),
                http_host=source.get("EFA_MCP_HTTP_HOST", "0.0.0.0").strip(),
                http_port=_read_int(source, "EFA_MCP_HTTP_PORT", 8_000),
                http_path=source.get("EFA_MCP_HTTP_PATH", "/mcp").strip(),
            )
        except (ValueError, ValidationError) as exc:
            raise ConfigurationError("EFA Read MCP configuration is invalid") from None

    def asyncpg_dsn(self) -> str:
        """Return an in-memory asyncpg-compatible DSN. Callers must never log it."""
        return _normalize_driver_scheme(self.database_url.get_secret_value())


def _normalize_driver_scheme(value: str) -> str:
    parsed = urlsplit(value)
    scheme = "postgresql" if parsed.scheme == "postgresql+asyncpg" else parsed.scheme
    return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def _read_int(source: Mapping[str, str], name: str, default: int) -> int:
    raw = source.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigurationError(f"{name} must be an integer") from None
