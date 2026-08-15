"""Runtime-only configuration for the Daily Commercial Brief."""
from __future__ import annotations

import os
from dataclasses import dataclass
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


def load_database_config(environ: Mapping[str, str] | None = None) -> DatabaseConfig:
    values = os.environ if environ is None else environ
    required = ("EFA_DB_HOST", "EFA_DB_PORT", "EFA_DB_NAME", "EFA_DB_USER", "EFA_DB_PASSWORD")
    missing = [key for key in required if not values.get(key, "").strip()]
    if missing:
        raise ConfigurationError("Missing required environment variables: " + ", ".join(missing))
    try:
        port = int(values["EFA_DB_PORT"])
    except ValueError as error:
        raise ConfigurationError("EFA_DB_PORT must be an integer") from error
    return DatabaseConfig(values["EFA_DB_HOST"].strip(), port, values["EFA_DB_NAME"].strip(), values["EFA_DB_USER"].strip(), values["EFA_DB_PASSWORD"])
