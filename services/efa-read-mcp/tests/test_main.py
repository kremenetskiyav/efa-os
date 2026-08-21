from __future__ import annotations

import unittest
from unittest.mock import patch

from efa_read_mcp import __main__
from efa_read_mcp.config import Settings

from tests.test_config import safe_test_url


class MainTests(unittest.TestCase):
    def test_runs_streamable_http_with_configured_endpoint(self) -> None:
        settings = Settings.from_environment(
            {
                "DATABASE_URL": safe_test_url(),
                "EFA_MCP_HTTP_HOST": "127.0.0.1",
                "EFA_MCP_HTTP_PORT": "9000",
                "EFA_MCP_HTTP_PATH": "/efa/mcp",
            }
        )
        with (
            patch.object(__main__.Settings, "from_environment", return_value=settings),
            patch.object(__main__.mcp, "run") as run,
        ):
            __main__.main()

        run.assert_called_once_with(
            transport="streamable-http",
            host="127.0.0.1",
            port=9000,
            streamable_http_path="/efa/mcp",
            stateless_http=True,
            json_response=True,
        )


if __name__ == "__main__":
    unittest.main()
