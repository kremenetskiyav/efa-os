"""Secret-safe configuration for the read-only recommendation engine."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


class ConfigurationError(ValueError):
    """Raised when required local configuration is absent or invalid."""


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


@dataclass(frozen=True)
class RecommendationConfig:
    """Conservative business thresholds, supplied through environment variables."""

    low_margin_percent: Decimal


def load_database_config(environ: Mapping[str, str] | None = None) -> DatabaseConfig:
    environment = os.environ if environ is None else environ
    required = ("EFA_DB_HOST", "EFA_DB_PORT", "EFA_DB_NAME", "EFA_DB_USER", "EFA_DB_PASSWORD")
    missing = [name for name in required if not environment.get(name, "").strip()]
    if missing:
        raise ConfigurationError("Missing required environment variables: " + ", ".join(missing))
    try:
        port = int(environment["EFA_DB_PORT"])
    except ValueError as error:
        raise ConfigurationError("EFA_DB_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ConfigurationError("EFA_DB_PORT must be between 1 and 65535")
    return DatabaseConfig(
        host=environment["EFA_DB_HOST"].strip(),
        port=port,
        name=environment["EFA_DB_NAME"].strip(),
        user=environment["EFA_DB_USER"].strip(),
        password=environment["EFA_DB_PASSWORD"],
    )


def load_recommendation_config(environ: Mapping[str, str] | None = None) -> RecommendationConfig:
    environment = os.environ if environ is None else environ
    raw_margin = environment.get("EFA_RECOMMENDATION_LOW_MARGIN_PERCENT", "15")
    try:
        low_margin_percent = Decimal(raw_margin)
    except InvalidOperation as error:
        raise ConfigurationError("EFA_RECOMMENDATION_LOW_MARGIN_PERCENT must be numeric") from error
    if not Decimal("0") < low_margin_percent < Decimal("100"):
        raise ConfigurationError("EFA_RECOMMENDATION_LOW_MARGIN_PERCENT must be between 0 and 100")
    return RecommendationConfig(low_margin_percent=low_margin_percent)
