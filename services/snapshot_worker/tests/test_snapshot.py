"""Unit tests for Snapshot Worker v1.2 snapshot preparation and writes."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
import unittest
from unittest.mock import patch

from config import DatabaseConfig
from database import ProductPriceHistory, SnapshotWriteError, write_daily_snapshot_run
from snapshot import (
    build_daily_idempotency_key,
    build_snapshot_candidates,
    calculate_business_date,
)


class SnapshotPreparationTests(unittest.TestCase):
    def test_daily_idempotency_key_is_deterministic(self) -> None:
        business_date = date(2026, 8, 15)
        self.assertEqual(
            build_daily_idempotency_key(business_date),
            "snapshot_worker:v1:daily:2026-08-15",
        )
        self.assertEqual(
            build_daily_idempotency_key(business_date),
            build_daily_idempotency_key(business_date),
        )

    def test_business_date_uses_europe_moscow(self) -> None:
        instant = datetime(2026, 8, 14, 21, 30, tzinfo=timezone.utc)
        self.assertEqual(calculate_business_date(instant), date(2026, 8, 15))

    def test_valid_price_creates_valid_snapshot_candidate(self) -> None:
        source = ProductPriceHistory(
            "УФ 005Б", Decimal("166"), Decimal("667"),
            datetime(2026, 8, 14, tzinfo=timezone.utc), None, None,
        )
        candidate = build_snapshot_candidates([source])[0]
        self.assertEqual(candidate.data_quality_status, "valid")
        self.assertEqual(candidate.current_price, Decimal("667"))

    def test_missing_price_creates_invalid_snapshot_candidate(self) -> None:
        source = ProductPriceHistory("УФ 005Б", Decimal("166"), None, None, None, None)
        candidate = build_snapshot_candidates([source])[0]
        self.assertEqual(candidate.data_quality_status, "invalid")
        self.assertIsNone(candidate.current_price)


class _Cursor:
    def __init__(self, connection: "_Connection") -> None:
        self.connection = connection
        self.rowcount = 1

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None:
        self.connection.queries.append(query)
        if query.lstrip().startswith("SELECT"):
            self.connection.selected = True

    def executemany(self, query: str, params: list[tuple[object, ...]]) -> None:
        self.connection.queries.append(query)
        if self.connection.fail_on_snapshots:
            raise RuntimeError("simulated insert failure")

    def fetchone(self) -> tuple[object, ...] | None:
        if self.connection.selected:
            self.connection.selected = False
            return self.connection.existing
        return (UUID("11111111-1111-1111-1111-111111111111"),)


class _Connection:
    def __init__(self, existing: tuple[object, ...] | None = None, fail_on_snapshots: bool = False) -> None:
        self.existing = existing
        self.fail_on_snapshots = fail_on_snapshots
        self.selected = False
        self.queries: list[str] = []
        self.committed = False
        self.rolled_back = False

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        return None


class _ConnectionContext:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def __enter__(self) -> _Connection:
        return self.connection

    def __exit__(self, *args: object) -> None:
        self.connection.close()


TEST_CONFIG = DatabaseConfig("localhost", 5432, "efa", "worker", "secret")
TEST_SNAPSHOTS = build_snapshot_candidates(
    [
        ProductPriceHistory(
            "УФ 005Б", Decimal("166"), Decimal("667"),
            datetime(2026, 8, 14, tzinfo=timezone.utc), None, None,
        )
    ]
)


class SnapshotWriteSafetyTests(unittest.TestCase):
    def test_existing_daily_run_is_noop(self) -> None:
        # The deterministic key is the same on a retry; the database lookup
        # therefore returns the completed logical run without INSERT statements.
        existing = (UUID("22222222-2222-2222-2222-222222222222"), "success", 5, 5, 0)
        connection = _Connection(existing=existing)
        with patch(
            "database.open_write_connection",
            return_value=_ConnectionContext(connection),
        ):
            result = write_daily_snapshot_run(
                TEST_CONFIG,
                idempotency_key=build_daily_idempotency_key(date(2026, 8, 14)),
                business_date=date(2026, 8, 14),
                snapshots=TEST_SNAPSHOTS,
            )
        self.assertTrue(result.already_exists)
        self.assertEqual(result.run_id, existing[0])
        self.assertFalse(any("INSERT" in query for query in connection.queries))
        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)

    def test_write_error_requires_rollback(self) -> None:
        failing_connection = _Connection(fail_on_snapshots=True)
        failure_record_connection = _Connection()
        with patch(
            "database.open_write_connection",
            side_effect=[
                _ConnectionContext(failing_connection),
                _ConnectionContext(failure_record_connection),
            ],
        ):
            with self.assertRaises(SnapshotWriteError):
                write_daily_snapshot_run(
                    TEST_CONFIG,
                    idempotency_key=build_daily_idempotency_key(date(2026, 8, 14)),
                    business_date=date(2026, 8, 14),
                    snapshots=TEST_SNAPSHOTS,
                )
        self.assertTrue(failing_connection.rolled_back)
        self.assertFalse(failing_connection.committed)


if __name__ == "__main__":
    unittest.main()
