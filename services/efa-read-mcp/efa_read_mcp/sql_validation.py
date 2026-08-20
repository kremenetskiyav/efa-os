"""PostgreSQL AST validation for the bounded analytics tool."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pglast import ast, parse_sql
from pglast.parser import ParseError
from pglast.stream import RawStream


ALLOWED_SCHEMA = "mcp_read"

_FORBIDDEN_NODE_TYPES = frozenset(
    {
        "AlterRoleSetStmt",
        "AlterTableStmt",
        "CallStmt",
        "CopyStmt",
        "CreateSchemaStmt",
        "CreateStmt",
        "DeleteStmt",
        "DoStmt",
        "DropStmt",
        "GrantStmt",
        "InsertStmt",
        "LockStmt",
        "MergeStmt",
        "TransactionStmt",
        "TruncateStmt",
        "UpdateStmt",
        "VariableSetStmt",
    }
)


class AnalyticsQueryRejected(ValueError):
    """A client-safe rejection that never contains the submitted SQL."""


@dataclass(frozen=True)
class ValidatedAnalyticsQuery:
    sql: str


def validate_analytics_query(query: str) -> ValidatedAnalyticsQuery:
    """Parse and validate exactly one read-only query over ``mcp_read`` relations."""
    try:
        statements = parse_sql(query)
    except (ParseError, UnicodeError, ValueError):
        raise AnalyticsQueryRejected("Analytics query is not valid PostgreSQL SQL") from None

    if len(statements) != 1:
        raise AnalyticsQueryRejected("Exactly one SQL statement is required")

    statement = statements[0].stmt
    if not isinstance(statement, ast.SelectStmt):
        raise AnalyticsQueryRejected("Only SELECT or WITH ... SELECT is allowed")

    tree = statement(skip_none=True)
    node_types = _node_types(tree)
    if node_types.intersection(_FORBIDDEN_NODE_TYPES):
        raise AnalyticsQueryRejected("The query contains a write or control operation")
    if "LockingClause" in node_types:
        raise AnalyticsQueryRejected("Row-locking SELECT clauses are not allowed")
    if "ParamRef" in node_types:
        raise AnalyticsQueryRejected("SQL parameters are not supported")
    if _select_into_is_present(tree):
        raise AnalyticsQueryRejected("SELECT INTO is not allowed")
    if node_types.intersection({"RangeFunction", "RangeTableFunc"}):
        raise AnalyticsQueryRejected("Table functions are not allowed")

    relation_count = _validate_relation_scopes(tree, frozenset())
    if relation_count == 0:
        raise AnalyticsQueryRejected("At least one mcp_read relation is required")

    for function in _nodes_named(tree, "FuncCall"):
        parts = _string_parts(function.get("funcname"))
        if len(parts) > 1 and parts[0] != "pg_catalog":
            raise AnalyticsQueryRejected("Only built-in SQL functions are allowed")

    normalized = RawStream()(statement)
    leading_keyword = normalized.lstrip().split(None, 1)[0].upper() if normalized.strip() else ""
    if leading_keyword not in {"SELECT", "WITH"}:
        raise AnalyticsQueryRejected("Only SELECT or WITH ... SELECT is allowed")
    return ValidatedAnalyticsQuery(sql=normalized)


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk(child)


def _node_types(tree: Any) -> set[str]:
    return {
        node_type
        for node in _walk(tree)
        if isinstance((node_type := node.get("@")), str)
    }


def _nodes_named(tree: Any, node_type: str):
    for node in _walk(tree):
        if node.get("@") == node_type:
            yield node


def _validate_relation_scopes(value: Any, visible_ctes: frozenset[str]) -> int:
    if isinstance(value, (list, tuple)):
        return sum(_validate_relation_scopes(item, visible_ctes) for item in value)
    if not isinstance(value, dict):
        return 0

    if value.get("@") == "RangeVar":
        schema = value.get("schemaname")
        catalog = value.get("catalogname")
        name = value.get("relname")
        if catalog is not None:
            raise AnalyticsQueryRejected("Cross-database relation references are not allowed")
        if schema == ALLOWED_SCHEMA:
            return 1
        if schema is None and isinstance(name, str) and name in visible_ctes:
            return 0
        if schema is None:
            raise AnalyticsQueryRejected("Every base relation must be schema-qualified")
        raise AnalyticsQueryRejected("Only mcp_read relations are allowed")

    if value.get("@") == "SelectStmt":
        count = 0
        local_ctes = set(visible_ctes)
        with_clause = value.get("withClause")
        ctes = ()
        recursive = False
        if isinstance(with_clause, dict):
            raw_ctes = with_clause.get("ctes")
            if isinstance(raw_ctes, (list, tuple)):
                ctes = raw_ctes
            recursive = bool(with_clause.get("recursive"))

        all_local_names = {
            name
            for cte in ctes
            if isinstance(cte, dict)
            and isinstance((name := cte.get("ctename")), str)
        }
        if recursive:
            local_ctes.update(all_local_names)

        for cte in ctes:
            if not isinstance(cte, dict):
                continue
            cte_query = cte.get("ctequery")
            count += _validate_relation_scopes(cte_query, frozenset(local_ctes))
            name = cte.get("ctename")
            if isinstance(name, str):
                local_ctes.add(name)

        for key, child in value.items():
            if key not in {"@", "withClause"}:
                count += _validate_relation_scopes(child, frozenset(local_ctes))
        return count

    return sum(
        _validate_relation_scopes(child, visible_ctes)
        for key, child in value.items()
        if key != "@"
    )


def _select_into_is_present(tree: Any) -> bool:
    return any("intoClause" in node for node in _nodes_named(tree, "SelectStmt"))


def _string_parts(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    parts: list[str] = []
    for item in value:
        if not isinstance(item, dict) or item.get("@") != "String":
            return ()
        text = item.get("sval")
        if not isinstance(text, str):
            return ()
        parts.append(text)
    return tuple(parts)
