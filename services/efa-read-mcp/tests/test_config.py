from __future__ import annotations

import unittest
from urllib.parse import urlunsplit

from efa_read_mcp.config import (
    EXPECTED_DATABASE,
    EXPECTED_ROLE,
    ConfigurationError,
    Settings,
)


def safe_test_url(
    *, role: str = EXPECTED_ROLE, database: str = EXPECTED_DATABASE, scheme: str = "postgresql+asyncpg"
) -> str:
    return urlunsplit(
        (scheme, f"{role}:unit-test-placeholder@127.0.0.1:5432", f"/{database}", "", "")
    )


class SettingsTests(unittest.TestCase):
    def test_environment_loads_expected_target_and_masks_url(self) -> None:
        settings = Settings.from_environment({"DATABASE_URL": safe_test_url()})
        self.assertTrue(settings.asyncpg_dsn().startswith("postgresql://"))
        self.assertNotIn("not-a-real-secret", repr(settings))

    def test_database_url_is_required(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings.from_environment({})

    def test_role_and_database_are_fixed(self) -> None:
        for url in (
            safe_test_url(role="other"),
            safe_test_url(database="other"),
            safe_test_url(scheme="https"),
        ):
            with self.subTest(url=url), self.assertRaises(ConfigurationError):
                Settings.from_environment({"DATABASE_URL": url})

    def test_pool_and_timeout_bounds_are_enforced(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings.from_environment(
                {
                    "DATABASE_URL": safe_test_url(),
                    "EFA_MCP_POOL_MIN_SIZE": "5",
                    "EFA_MCP_POOL_MAX_SIZE": "4",
                }
            )
        with self.assertRaises(ConfigurationError):
            Settings.from_environment(
                {
                    "DATABASE_URL": safe_test_url(),
                    "EFA_MCP_STATEMENT_TIMEOUT_MS": "not-an-integer",
                }
            )


if __name__ == "__main__":
    unittest.main()
