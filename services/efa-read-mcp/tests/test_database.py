from __future__ import annotations

import unittest

from efa_read_mcp.config import Settings
from efa_read_mcp.database import EfaReadRepository


class _AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _Attribute:
    def __init__(self, name: str):
        self.name = name


class _Record:
    def __init__(self, *values):
        self._values = values

    def values(self):
        return self._values


class _Statement:
    def __init__(self):
        self.fetch_arguments = None

    def get_attributes(self):
        return [_Attribute("offer_id"), _Attribute("total_present")]

    async def fetch(self, *arguments):
        self.fetch_arguments = arguments
        return [_Record("A", 1), _Record("B", 2), _Record("C", 3)]


class _Connection:
    def __init__(self):
        self.readonly = None
        self.settings = []
        self.prepared_query = None
        self.statement = _Statement()

    def transaction(self, *, readonly: bool):
        self.readonly = readonly
        return _AsyncContext(self)

    async def fetchval(self, query, value):
        self.settings.append((query, value))

    async def prepare(self, query):
        self.prepared_query = query
        return self.statement


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _AsyncContext(self.connection)


class AnalyticsRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_is_readonly_timed_and_bounded(self) -> None:
        settings = Settings.from_environment(
            {
                "DATABASE_URL": (
                    "postgresql://efa_mcp_readonly:placeholder@127.0.0.1:5432/efa"
                )
            }
        )
        repository = EfaReadRepository(settings)
        connection = _Connection()
        repository._pool = _Pool(connection)

        result = await repository.query_analytics(
            "SELECT offer_id, total_present FROM mcp_read.product_overview", 2
        )

        self.assertTrue(connection.readonly)
        self.assertEqual(["offer_id", "total_present"], result.columns)
        self.assertEqual([["A", 1], ["B", 2]], result.rows)
        self.assertTrue(result.truncated)
        self.assertEqual((3,), connection.statement.fetch_arguments)
        self.assertIn("LIMIT $1", connection.prepared_query)
        configured_values = [value for _, value in connection.settings]
        self.assertEqual(["10000ms", "3000ms"], configured_values)


if __name__ == "__main__":
    unittest.main()
