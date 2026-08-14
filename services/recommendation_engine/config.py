"""Secret-safe configuration for the read-only recommendation engine."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


@dataclass(frozen=True)
class RecommendationConfig:
    low_margin_percent: Decimal
    min_window_units: int
    max_price_step_percent: Decimal


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
    return DatabaseConfig(environment["EFA_DB_HOST"].strip(), port, environment["EFA_DB_NAME"].strip(), environment["EFA_DB_USER"].strip(), environment["EFA_DB_PASSWORD"])


def load_recommendation_config(environ: Mapping[str, str] | None = None) -> RecommendationConfig:
    environment = os.environ if environ is None else environ
    try:
        margin = Decimal(environment.get("EFA_RECOMMENDATION_LOW_MARGIN_PERCENT", "15"))
        max_step = Decimal(environment.get("EFA_RECOMMENDATION_MAX_PRICE_STEP_PERCENT", "20"))
        min_units = int(environment.get("EFA_RECOMMENDATION_MIN_WINDOW_UNITS", "10"))
    except (InvalidOperation, ValueError) as error:
        raise ConfigurationError("Recommendation thresholds must be numeric") from error
    if not Decimal("0") < margin < Decimal("100") or not Decimal("0") < max_step <= Decimal("100") or min_units < 1:
        raise ConfigurationError("Recommendation thresholds are outside safe bounds")
    return RecommendationConfig(margin, min_units, max_step)
