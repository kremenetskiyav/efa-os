"""Environment-based configuration for the Snapshot Worker skeleton."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


class ConfigurationError(ValueError):
    """Raised when a required worker setting is missing or invalid."""


@dataclass(frozen=True)
class DatabaseConfig:
    """Minimal PostgreSQL connection settings; never log the password."""

    host: str
    port: int
    name: str
    user: str
    password: str


DEFAULT_BATCH_SIZE = 500


def load_database_config(environ: Mapping[str, str] | None = None) -> DatabaseConfig:
    """Load and validate the required PostgreSQL settings from environment variables."""

    environment = os.environ if environ is None else environ
    required = (
        "EFA_DB_HOST",
        "EFA_DB_PORT",
        "EFA_DB_NAME",
        "EFA_DB_USER",
        "EFA_DB_PASSWORD",
    )
    missing = [name for name in required if not environment.get(name, "").strip()]
    if missing:
        raise ConfigurationError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    port_value = environment["EFA_DB_PORT"].strip()
    try:
        port = int(port_value)
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


def load_batch_size(environ: Mapping[str, str] | None = None) -> int:
    """Load the positive read batch size without introducing database state."""

    environment = os.environ if environ is None else environ
    value = environment.get("EFA_SNAPSHOT_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)).strip()
    try:
        batch_size = int(value)
    except ValueError as error:
        raise ConfigurationError("EFA_SNAPSHOT_BATCH_SIZE must be an integer") from error

    if batch_size < 1:
        raise ConfigurationError("EFA_SNAPSHOT_BATCH_SIZE must be greater than zero")

    return batch_size
