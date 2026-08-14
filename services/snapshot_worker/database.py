"""PostgreSQL connectivity helpers for the Snapshot Worker skeleton."""

from __future__ import annotations

from config import DatabaseConfig


class DatabaseConnectionError(RuntimeError):
    """Raised when the worker cannot establish a PostgreSQL connection."""


def check_connection(config: DatabaseConfig) -> None:
    """Open and close PostgreSQL connectivity without executing any SQL statement."""

    try:
        import psycopg2

        connection = psycopg2.connect(
            host=config.host,
            port=config.port,
            dbname=config.name,
            user=config.user,
            password=config.password,
            connect_timeout=5,
        )
    except Exception as error:  # Driver exceptions are intentionally not exposed.
        raise DatabaseConnectionError("PostgreSQL connection check failed") from error

    connection.close()
