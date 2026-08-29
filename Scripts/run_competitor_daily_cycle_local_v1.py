"""Fail-closed local credential handoff for Competitor Daily Cycle v1."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, TextIO
from urllib.parse import unquote, urlsplit


CONTRACT_VERSION = "competitor_daily_cycle_local_handoff.v1"
EXPECTED_DATABASE = "efa"
EXPECTED_USER = "efa_mcp_readonly"
ALLOWED_VARIABLES = frozenset({"DATABASE_URL"})
CHILD_DATABASE_VARIABLES = (
    "EFA_DB_HOST",
    "EFA_DB_PORT",
    "EFA_DB_NAME",
    "EFA_DB_USER",
    "EFA_DB_PASSWORD",
)
INHERITED_POSTGRES_IDENTITY_VARIABLES = (
    "PGHOST",
    "PGPORT",
    "PGDATABASE",
    "PGUSER",
    "PGPASSWORD",
    "PGSERVICE",
    "PGSERVICEFILE",
)
SUPPORTED_SCHEMES = frozenset({"postgres", "postgresql", "postgresql+asyncpg"})
ROOT = Path(__file__).resolve().parents[1]
DAILY_CYCLE = ROOT / "Scripts" / "run_competitor_daily_cycle_v1.py"
DEFAULT_SECRET_FILE = (
    Path.home() / ".efa-os" / "secrets" / "efa-read-mcp.env"
)


class HandoffError(RuntimeError):
    """A sanitized fail-closed handoff failure."""

    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


@dataclass(frozen=True)
class AclStatus:
    inheritance_protected: bool
    current_user_allow_rules: int
    unexpected_principals: int

    @property
    def approved(self) -> bool:
        return (
            self.inheritance_protected
            and self.current_user_allow_rules > 0
            and self.unexpected_principals == 0
        )


@dataclass(frozen=True)
class DatabaseCredential:
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)
    host_category: str
    port_present: bool


@dataclass(frozen=True)
class RolePreflight:
    role: str
    database: str
    transaction_read_only: bool
    public_usage: bool
    public_create: bool
    mcp_read_usage: bool
    mcp_read_create: bool
    approved_reads: bool


ACL_INSPECTION_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Import-Module (
    Join-Path $env:WINDIR (
        'System32\WindowsPowerShell\v1.0\Modules\' +
        'Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1'
    )
) -ErrorAction Stop
$acl = Get-Acl -LiteralPath $env:EFA_SECRET_ACL_TARGET
$currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$unexpected = 0
$currentAllow = 0
foreach ($rule in @($acl.Access)) {
    try {
        $sid = $rule.IdentityReference.Translate(
            [System.Security.Principal.SecurityIdentifier]
        ).Value
    } catch {
        $unexpected++
        continue
    }
    if ($sid -ne $currentSid) {
        $unexpected++
    }
    if ($sid -eq $currentSid -and $rule.AccessControlType -eq 'Allow') {
        $currentAllow++
    }
}
[pscustomobject]@{
    inheritance_protected = [bool]$acl.AreAccessRulesProtected
    current_user_allow_rules = [int]$currentAllow
    unexpected_principals = [int]$unexpected
} | ConvertTo-Json -Compress
""".strip()


PREFLIGHT_SQL = """
SELECT
    current_user,
    session_user,
    current_database(),
    current_setting('transaction_read_only'),
    role.rolsuper,
    database.datdba = role.oid AS database_owner,
    has_database_privilege(current_user, current_database(), 'CREATE') AS database_create,
    has_schema_privilege(current_user, 'mcp_read', 'USAGE') AS mcp_read_usage,
    has_schema_privilege(current_user, 'mcp_read', 'CREATE') AS mcp_read_create,
    has_schema_privilege(current_user, 'public', 'USAGE') AS public_usage,
    has_schema_privilege(current_user, 'public', 'CREATE') AS public_create,
    has_table_privilege(
        current_user,
        'mcp_read.competitor_reference_plan_source',
        'SELECT'
    )
    AND has_table_privilege(
        current_user,
        'mcp_read.competitor_snapshot_runs',
        'SELECT'
    )
    AND has_table_privilege(
        current_user,
        'mcp_read.competitor_snapshot_observations',
        'SELECT'
    )
    AND has_table_privilege(
        current_user,
        'mcp_read.competitor_findings',
        'SELECT'
    )
    AND has_table_privilege(
        current_user,
        'mcp_read.competitor_finding_sets_reconciliation',
        'SELECT'
    ) AS approved_reads
FROM pg_catalog.pg_roles AS role
JOIN pg_catalog.pg_database AS database
  ON database.datname = current_database()
WHERE role.rolname = current_user
"""


def inspect_windows_acl(path: Path) -> AclStatus:
    if os.name != "nt":
        raise HandoffError("SECRET_FILE_ACL_UNSUPPORTED")
    inspection_environment = dict(os.environ)
    inspection_environment["EFA_SECRET_ACL_TARGET"] = str(path)
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                ACL_INSPECTION_SCRIPT,
            ],
            check=False,
            capture_output=True,
            env=inspection_environment,
            text=True,
            timeout=10,
        )
        if completed.returncode != 0:
            raise HandoffError("SECRET_FILE_ACL_UNREADABLE")
        payload = json.loads(completed.stdout)
        return AclStatus(
            inheritance_protected=payload["inheritance_protected"] is True,
            current_user_allow_rules=int(payload["current_user_allow_rules"]),
            unexpected_principals=int(payload["unexpected_principals"]),
        )
    except HandoffError:
        raise
    except Exception:
        raise HandoffError("SECRET_FILE_ACL_UNREADABLE") from None
    finally:
        inspection_environment.pop("EFA_SECRET_ACL_TARGET", None)


def read_secret_file(
    path: Path,
    *,
    acl_inspector: Callable[[Path], AclStatus] = inspect_windows_acl,
) -> str:
    if not path.is_file():
        raise HandoffError("SECRET_FILE_MISSING")
    acl = acl_inspector(path)
    if not acl.approved:
        raise HandoffError("SECRET_FILE_ACL_INVALID")
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeError):
        raise HandoffError("SECRET_FILE_UNREADABLE") from None


def parse_env_file(text: str) -> str:
    variables: dict[str, str] = {}
    for source_line in text.splitlines():
        line = source_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise HandoffError("SECRET_FORMAT_INVALID")
        name, value = line.split("=", 1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise HandoffError("SECRET_FORMAT_INVALID")
        if name in variables:
            raise HandoffError("SECRET_FORMAT_INVALID")
        if name not in ALLOWED_VARIABLES:
            raise HandoffError("UNEXPECTED_SECRET_VARIABLE")
        if not value:
            raise HandoffError("DATABASE_URL_MISSING")
        variables[name] = value
    if set(variables) != ALLOWED_VARIABLES:
        raise HandoffError("DATABASE_URL_MISSING")
    return variables["DATABASE_URL"]


def classify_host(host: str) -> str:
    if host.lower() == "localhost":
        return "LOOPBACK"
    try:
        return "LOOPBACK" if ipaddress.ip_address(host).is_loopback else "REMOTE"
    except ValueError:
        return "REMOTE"


def parse_database_url(database_url: str) -> DatabaseCredential:
    try:
        parsed = urlsplit(database_url)
        if parsed.scheme.lower() not in SUPPORTED_SCHEMES:
            raise ValueError
        if parsed.query or parsed.fragment:
            raise ValueError
        host = parsed.hostname
        port_present = parsed.port is not None
        port = parsed.port or 5432
        user = unquote(parsed.username or "")
        password = unquote(parsed.password or "")
        database = unquote(parsed.path[1:]) if parsed.path.startswith("/") else ""
        if not host or not password or not 1 <= port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        raise HandoffError("DATABASE_URL_MALFORMED") from None
    if database != EXPECTED_DATABASE:
        raise HandoffError("WRONG_DATABASE")
    if user != EXPECTED_USER:
        raise HandoffError("WRONG_DATABASE_USER")
    return DatabaseCredential(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        host_category=classify_host(host),
        port_present=port_present,
    )


def connect_read_only(credential: DatabaseCredential) -> Any:
    try:
        import psycopg2

        return psycopg2.connect(
            host=credential.host,
            port=credential.port,
            dbname=credential.database,
            user=credential.user,
            password=credential.password,
            connect_timeout=10,
            options="-c default_transaction_read_only=on -c statement_timeout=15000",
        )
    except Exception as error:
        sqlstate = getattr(error, "pgcode", None) or getattr(error, "sqlstate", None)
        message = str(error).lower()
        if sqlstate == "28P01" or "password authentication failed" in message:
            raise HandoffError("CREDENTIAL_STALE") from None
        raise HandoffError("CONNECTION_FAILED") from None


def run_role_preflight(connection: Any) -> RolePreflight:
    try:
        with connection.cursor() as cursor:
            cursor.execute(PREFLIGHT_SQL)
            row = cursor.fetchone()
    except Exception:
        raise HandoffError("ROLE_PREFLIGHT_QUERY_FAILED") from None
    if not row or len(row) != 12:
        raise HandoffError("ROLE_PREFLIGHT_QUERY_FAILED")
    (
        current_user,
        session_user,
        database,
        transaction_read_only,
        superuser,
        database_owner,
        database_create,
        mcp_read_usage,
        mcp_read_create,
        public_usage,
        public_create,
        approved_reads,
    ) = row
    if current_user != EXPECTED_USER or session_user != EXPECTED_USER:
        raise HandoffError("WRONG_RUNTIME_ROLE")
    if database != EXPECTED_DATABASE:
        raise HandoffError("WRONG_DATABASE")
    if bool(superuser):
        raise HandoffError("SUPERUSER_REJECTED")
    if bool(database_owner):
        raise HandoffError("DATABASE_OWNER_REJECTED")
    if bool(database_create):
        raise HandoffError("DATABASE_CREATE_PRIVILEGE_REJECTED")
    if str(transaction_read_only).lower() != "on":
        raise HandoffError("READ_WRITE_TRANSACTION_REJECTED")
    if not bool(mcp_read_usage) or bool(mcp_read_create):
        raise HandoffError("MCP_READ_SCHEMA_PRIVILEGE_REJECTED")
    if bool(public_usage) or bool(public_create):
        raise HandoffError("PUBLIC_SCHEMA_PRIVILEGE_REJECTED")
    if not bool(approved_reads):
        raise HandoffError("APPROVED_MCP_READ_ACCESS_REJECTED")
    return RolePreflight(
        role=current_user,
        database=database,
        transaction_read_only=True,
        public_usage=False,
        public_create=False,
        mcp_read_usage=True,
        mcp_read_create=False,
        approved_reads=True,
    )


def child_environment(
    parent_environment: Mapping[str, str],
    credential: DatabaseCredential,
) -> dict[str, str]:
    environment = dict(parent_environment)
    environment.pop("DATABASE_URL", None)
    for name in (*CHILD_DATABASE_VARIABLES, *INHERITED_POSTGRES_IDENTITY_VARIABLES):
        environment.pop(name, None)
    environment.update(
        {
            "EFA_DB_HOST": credential.host,
            "EFA_DB_PORT": str(credential.port),
            "EFA_DB_NAME": credential.database,
            "EFA_DB_USER": credential.user,
            "EFA_DB_PASSWORD": credential.password,
        }
    )
    return environment


def sanitized_result(
    status: str,
    credential: DatabaseCredential | None = None,
    preflight: RolePreflight | None = None,
    child_exit_code: int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "status": status,
        "role": preflight.role if preflight else None,
        "database": preflight.database if preflight else None,
        "host_category": credential.host_category if credential else None,
        "port_present": credential.port_present if credential else None,
        "transaction_read_only": preflight.transaction_read_only if preflight else None,
        "mcp_read_usage": preflight.mcp_read_usage if preflight else None,
        "mcp_read_create": preflight.mcp_read_create if preflight else None,
        "public_usage": preflight.public_usage if preflight else None,
        "public_create": preflight.public_create if preflight else None,
        "approved_mcp_read_access": preflight.approved_reads if preflight else None,
        "child_exit_code": child_exit_code,
        "db_writes": {"insert": 0, "update": 0, "delete": 0},
    }
    return result


def emit_result(result: Mapping[str, Any], stream: TextIO) -> None:
    stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")


def run_handoff(
    *,
    secret_file: Path,
    preflight_only: bool,
    daily_cycle_args: Sequence[str],
    parent_environment: Mapping[str, str],
    output: TextIO,
    acl_inspector: Callable[[Path], AclStatus] = inspect_windows_acl,
    connector: Callable[[DatabaseCredential], Any] = connect_read_only,
    process_runner: Callable[..., Any] = subprocess.run,
) -> int:
    credential: DatabaseCredential | None = None
    connection = None
    child_env: dict[str, str] | None = None
    try:
        text = read_secret_file(secret_file, acl_inspector=acl_inspector)
        database_url = parse_env_file(text)
        credential = parse_database_url(database_url)
        database_url = ""
        text = ""
        connection = connector(credential)
        preflight = run_role_preflight(connection)
        if preflight_only:
            emit_result(sanitized_result("PREFLIGHT_PASS", credential, preflight), output)
            return 0
        if not daily_cycle_args:
            raise HandoffError("DAILY_CYCLE_ARGUMENTS_REQUIRED")
        child_args = list(daily_cycle_args)
        if child_args and child_args[0] == "--":
            child_args.pop(0)
        if not child_args:
            raise HandoffError("DAILY_CYCLE_ARGUMENTS_REQUIRED")
        child_env = child_environment(parent_environment, credential)
        completed = process_runner(
            [sys.executable, str(DAILY_CYCLE), *child_args],
            cwd=str(ROOT),
            env=child_env,
            check=False,
        )
        child_exit_code = int(completed.returncode)
        status = "CHILD_SUCCESS" if child_exit_code == 0 else "CHILD_FAILED"
        emit_result(
            sanitized_result(status, credential, preflight, child_exit_code),
            output,
        )
        return child_exit_code
    except HandoffError as error:
        emit_result(sanitized_result(error.status, credential), output)
        return 2
    except Exception:
        emit_result(sanitized_result("INTERNAL_ERROR", credential), output)
        return 2
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        if child_env is not None:
            child_env.pop("EFA_DB_PASSWORD", None)
        credential = None


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed local credential handoff for Competitor Daily Cycle v1"
    )
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("daily_cycle_args", nargs=argparse.REMAINDER)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(argv)
    return run_handoff(
        secret_file=DEFAULT_SECRET_FILE,
        preflight_only=args.preflight_only,
        daily_cycle_args=args.daily_cycle_args,
        parent_environment=os.environ,
        output=sys.stdout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
