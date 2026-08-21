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
        self.assertEqual("0.0.0.0", settings.http_host)
        self.assertEqual(8000, settings.http_port)
        self.assertEqual("/mcp", settings.http_path)

    def test_http_endpoint_can_be_configured(self) -> None:
        settings = Settings.from_environment(
            {
                "DATABASE_URL": safe_test_url(),
                "EFA_MCP_HTTP_HOST": "127.0.0.1",
                "EFA_MCP_HTTP_PORT": "9000",
                "EFA_MCP_HTTP_PATH": "/efa/mcp",
            }
        )
        self.assertEqual("127.0.0.1", settings.http_host)
        self.assertEqual(9000, settings.http_port)
        self.assertEqual("/efa/mcp", settings.http_path)

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

    def test_http_endpoint_validation(self) -> None:
        for name, value in (
            ("EFA_MCP_HTTP_HOST", ""),
            ("EFA_MCP_HTTP_PORT", "0"),
            ("EFA_MCP_HTTP_PORT", "65536"),
            ("EFA_MCP_HTTP_PATH", "mcp"),
            ("EFA_MCP_HTTP_PATH", "/mcp?token=unsafe"),
        ):
            with self.subTest(name=name, value=value), self.assertRaises(ConfigurationError):
                Settings.from_environment({"DATABASE_URL": safe_test_url(), name: value})


if __name__ == "__main__":
    unittest.main()
