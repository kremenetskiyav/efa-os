from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "Scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_competitor_daily_cycle_local_v1 as launcher


SENTINEL = "SUPER_SECRET_SENTINEL_VALUE"
APPROVED_ACL = launcher.AclStatus(True, 1, 0)


def database_url(
    *,
    database: str = launcher.EXPECTED_DATABASE,
    user: str = launcher.EXPECTED_USER,
    password: str = SENTINEL,
) -> str:
    scheme = "postgresql+asyncpg"
    return f"{scheme}://{user}:{password}@127.0.0.1:5432/{database}"


def approved_row(**overrides):
    values = {
        "current_user": launcher.EXPECTED_USER,
        "session_user": launcher.EXPECTED_USER,
        "database": launcher.EXPECTED_DATABASE,
        "transaction_read_only": "on",
        "superuser": False,
        "database_owner": False,
        "database_create": False,
        "mcp_read_usage": True,
        "mcp_read_create": False,
        "public_usage": False,
        "public_create": False,
        "approved_reads": True,
    }
    values.update(overrides)
    return tuple(values.values())


class Cursor:
    def __init__(self, row) -> None:
        self.row = row
        self.executed = None

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, query) -> None:
        self.executed = query

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, row=None) -> None:
        self.cursor_value = Cursor(approved_row() if row is None else row)
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self) -> None:
        self.closed = True


class LocalCredentialHandoffTests(unittest.TestCase):
    def write_secret(self, folder: str, content: str) -> Path:
        path = Path(folder) / "read-only.env"
        path.write_text(content, encoding="utf-8")
        return path

    def test_01_missing_secret_file_fails_closed(self) -> None:
        with TemporaryDirectory() as folder:
            missing = Path(folder) / "missing.env"
            with self.assertRaisesRegex(launcher.HandoffError, "SECRET_FILE_MISSING"):
                launcher.read_secret_file(missing, acl_inspector=lambda _path: APPROVED_ACL)

    def test_02_unreadable_secret_file_fails_closed(self) -> None:
        with TemporaryDirectory() as folder:
            path = self.write_secret(folder, "DATABASE_URL=dummy")
            with patch.object(Path, "read_bytes", side_effect=OSError):
                with self.assertRaisesRegex(
                    launcher.HandoffError, "SECRET_FILE_UNREADABLE"
                ):
                    launcher.read_secret_file(
                        path, acl_inspector=lambda _path: APPROVED_ACL
                    )

    def test_03_wrong_acl_metadata_fails_closed(self) -> None:
        with TemporaryDirectory() as folder:
            path = self.write_secret(folder, "DATABASE_URL=dummy")
            invalid = launcher.AclStatus(False, 1, 1)
            with self.assertRaisesRegex(
                launcher.HandoffError, "SECRET_FILE_ACL_INVALID"
            ):
                launcher.read_secret_file(path, acl_inspector=lambda _path: invalid)

    def test_04_missing_database_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(launcher.HandoffError, "DATABASE_URL_MISSING"):
            launcher.parse_env_file("# no variables\n")

    def test_05_extra_variable_is_rejected(self) -> None:
        text = f"DATABASE_URL={database_url()}\nEXTRA=value\n"
        with self.assertRaisesRegex(
            launcher.HandoffError, "UNEXPECTED_SECRET_VARIABLE"
        ):
            launcher.parse_env_file(text)

    def test_06_malformed_database_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(launcher.HandoffError, "DATABASE_URL_MALFORMED"):
            launcher.parse_database_url("not-a-database-url")

    def test_07_wrong_database_is_rejected(self) -> None:
        with self.assertRaisesRegex(launcher.HandoffError, "WRONG_DATABASE"):
            launcher.parse_database_url(database_url(database="other"))

    def test_08_wrong_user_is_rejected(self) -> None:
        with self.assertRaisesRegex(launcher.HandoffError, "WRONG_DATABASE_USER"):
            launcher.parse_database_url(database_url(user="efa"))

    def test_09_authentication_failure_is_sanitized_as_stale(self) -> None:
        class AuthenticationError(Exception):
            pgcode = "28P01"

        fake_psycopg = SimpleNamespace(
            connect=lambda **_kwargs: (_ for _ in ()).throw(AuthenticationError(SENTINEL))
        )
        credential = launcher.parse_database_url(database_url())
        with patch.dict(sys.modules, {"psycopg2": fake_psycopg}):
            with self.assertRaisesRegex(launcher.HandoffError, "CREDENTIAL_STALE") as caught:
                launcher.connect_read_only(credential)
        self.assertNotIn(SENTINEL, str(caught.exception))

    def test_10_read_write_transaction_identity_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            launcher.HandoffError, "READ_WRITE_TRANSACTION_REJECTED"
        ):
            launcher.run_role_preflight(
                Connection(approved_row(transaction_read_only="off"))
            )

    def test_11_superuser_identity_is_rejected(self) -> None:
        with self.assertRaisesRegex(launcher.HandoffError, "SUPERUSER_REJECTED"):
            launcher.run_role_preflight(Connection(approved_row(superuser=True)))

    def test_12_public_schema_privilege_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            launcher.HandoffError, "PUBLIC_SCHEMA_PRIVILEGE_REJECTED"
        ):
            launcher.run_role_preflight(Connection(approved_row(public_usage=True)))

    def test_13_missing_approved_mcp_read_access_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            launcher.HandoffError, "APPROVED_MCP_READ_ACCESS_REJECTED"
        ):
            launcher.run_role_preflight(Connection(approved_row(approved_reads=False)))

    def test_14_database_owner_is_rejected(self) -> None:
        with self.assertRaisesRegex(launcher.HandoffError, "DATABASE_OWNER_REJECTED"):
            launcher.run_role_preflight(Connection(approved_row(database_owner=True)))

    def test_15_mcp_read_schema_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            launcher.HandoffError, "MCP_READ_SCHEMA_PRIVILEGE_REJECTED"
        ):
            launcher.run_role_preflight(Connection(approved_row(mcp_read_usage=False)))

    def test_16_successful_preflight_result_is_sanitized(self) -> None:
        with TemporaryDirectory() as folder:
            path = self.write_secret(folder, f"DATABASE_URL={database_url()}\n")
            connection = Connection()
            output = io.StringIO()
            exit_code = launcher.run_handoff(
                secret_file=path,
                preflight_only=True,
                daily_cycle_args=(),
                parent_environment={},
                output=output,
                acl_inspector=lambda _path: APPROVED_ACL,
                connector=lambda _credential: connection,
            )
        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "PREFLIGHT_PASS")
        self.assertEqual(result["role"], launcher.EXPECTED_USER)
        self.assertEqual(result["database"], launcher.EXPECTED_DATABASE)
        self.assertTrue(result["transaction_read_only"])
        self.assertFalse(result["public_usage"])
        self.assertTrue(connection.closed)
        self.assertNotIn(SENTINEL, output.getvalue())

    def test_17_child_environment_mapping_is_process_local(self) -> None:
        credential = launcher.parse_database_url(database_url())
        parent = {
            "PATH": "fixture-path",
            "DATABASE_URL": "must-be-removed",
            "EFA_DB_USER": "must-be-replaced",
            "PGPASSWORD": "must-be-removed",
        }
        child = launcher.child_environment(parent, credential)
        self.assertEqual(parent["EFA_DB_USER"], "must-be-replaced")
        self.assertNotIn("DATABASE_URL", child)
        self.assertNotIn("PGPASSWORD", child)
        self.assertEqual(child["EFA_DB_HOST"], "127.0.0.1")
        self.assertEqual(child["EFA_DB_PORT"], "5432")
        self.assertEqual(child["EFA_DB_NAME"], launcher.EXPECTED_DATABASE)
        self.assertEqual(child["EFA_DB_USER"], launcher.EXPECTED_USER)
        self.assertEqual(child["EFA_DB_PASSWORD"], SENTINEL)

    def test_18_child_exit_code_is_propagated_without_secret_output(self) -> None:
        with TemporaryDirectory() as folder:
            path = self.write_secret(folder, f"DATABASE_URL={database_url()}\n")
            output = io.StringIO()
            captured_environment = {}

            def process_runner(_args, **kwargs):
                captured_environment.update(kwargs["env"])
                return SimpleNamespace(returncode=7)

            exit_code = launcher.run_handoff(
                secret_file=path,
                preflight_only=False,
                daily_cycle_args=("--", "--evidence", "fixture.json"),
                parent_environment={"PATH": "fixture-path"},
                output=output,
                acl_inspector=lambda _path: APPROVED_ACL,
                connector=lambda _credential: Connection(),
                process_runner=process_runner,
            )
        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 7)
        self.assertEqual(result["status"], "CHILD_FAILED")
        self.assertEqual(result["child_exit_code"], 7)
        self.assertEqual(captured_environment["EFA_DB_PASSWORD"], SENTINEL)
        self.assertNotIn(SENTINEL, output.getvalue())

    def test_19_unexpected_child_error_is_sanitized(self) -> None:
        with TemporaryDirectory() as folder:
            path = self.write_secret(folder, f"DATABASE_URL={database_url()}\n")
            output = io.StringIO()

            def process_runner(_args, **_kwargs):
                raise RuntimeError(SENTINEL)

            exit_code = launcher.run_handoff(
                secret_file=path,
                preflight_only=False,
                daily_cycle_args=("--", "--evidence", "fixture.json"),
                parent_environment={},
                output=output,
                acl_inspector=lambda _path: APPROVED_ACL,
                connector=lambda _credential: Connection(),
                process_runner=process_runner,
            )
        self.assertEqual(exit_code, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "INTERNAL_ERROR")
        self.assertNotIn(SENTINEL, output.getvalue())

    def test_20_sentinel_is_absent_from_repr_result_and_documentation(self) -> None:
        credential = launcher.parse_database_url(database_url())
        self.assertNotIn(SENTINEL, repr(credential))
        result = launcher.sanitized_result("CONNECTION_FAILED", credential)
        rendered = json.dumps(result, sort_keys=True)
        documentation = (
            ROOT / "docs" / "architecture" / "COMPETITOR_DAILY_CYCLE_V1.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn(SENTINEL, rendered)
        self.assertNotIn(SENTINEL, documentation)

    def test_21_launcher_has_no_business_or_write_sql(self) -> None:
        source = (
            SCRIPTS / "run_competitor_daily_cycle_local_v1.py"
        ).read_text(encoding="utf-8")
        self.assertNotRegex(
            source,
            r"(?i)\b(?:INSERT\s+INTO|UPDATE\s+(?:public\.)?|DELETE\s+FROM|TRUNCATE\s+(?:TABLE\s+)?)",
        )
        self.assertNotRegex(source, r"(?i)\b(?:FROM|JOIN)\s+public\.competitor_")
        self.assertNotIn("setx", source.lower())


if __name__ == "__main__":
    unittest.main()
