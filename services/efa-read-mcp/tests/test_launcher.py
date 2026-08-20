from __future__ import annotations

import unittest
from pathlib import Path


class LocalLauncherContractTests(unittest.TestCase):
    def test_launcher_uses_only_fixed_secret_source_and_local_venv(self) -> None:
        launcher = (
            Path(__file__).resolve().parents[1] / "run-local.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn(".efa-os\\secrets\\efa-read-mcp.env", launcher)
        self.assertIn(".venv\\Scripts\\python.exe", launcher)
        self.assertIn("$PSScriptRoot", launcher)
        self.assertIn("-m efa_read_mcp", launcher)
        self.assertIn("exit $processExitCode", launcher)
        self.assertNotIn("postgresql://", launcher)
        self.assertNotIn("postgresql+asyncpg://", launcher)


if __name__ == "__main__":
    unittest.main()
