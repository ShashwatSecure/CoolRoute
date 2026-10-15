"""Guardrails for SQL written by the model.

Defence in depth: this module parses and filters the SQL text, the database
role ``agent_ro`` (migration 0003) limits what the connection may read, and
``sql_tool.run_sql`` runs everything in a read-only transaction with a timeout.
No single layer is trusted on its own.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

READABLE_TABLES = frozenset(
    {
        "vehicles",
        "shipments",
        "telemetry_readings",
        "routes",
        "maintenance_log",
        "cargo_profiles",
    }
)
ALLOWED_SCHEMAS = frozenset({"", "public"})
ROW_CAP = 200

# Any of these nodes anywhere in the tree (including inside a CTE) is rejected.
FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Copy,
    exp.Command,
    exp.Set,
    exp.Transaction,
    exp.Into,
    exp.Lock,
)
FORBIDDEN_FUNCTION_PREFIXES = ("pg_", "lo_", "dblink")
FORBIDDEN_FUNCTIONS = frozenset({"set_config"})


class UnsafeSQLError(ValueError):
    """Raised when model-written SQL breaks a guard rule."""


def guard_select(sql: str) -> str:
    """Return the cleaned SQL if it is one read-only SELECT, otherwise raise."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeSQLError("empty query")

    try:
        statements = [s for s in sqlglot.parse(cleaned, read="postgres") if s is not None]
    except ParseError as exc:
        raise UnsafeSQLError(f"could not parse SQL: {exc}") from exc

    if len(statements) != 1:
        raise UnsafeSQLError("exactly one statement is allowed")

    root = statements[0]
    if not isinstance(root, exp.Query):
        raise UnsafeSQLError("only SELECT queries are allowed")

    for node in root.find_all(exp.Expression):
        if isinstance(node, FORBIDDEN_NODES):
            raise UnsafeSQLError(f"{type(node).__name__} is not allowed")
        if isinstance(node, exp.Func):
            name = node.name.lower() if isinstance(node, exp.Anonymous) else node.sql_name().lower()
            if name.startswith(FORBIDDEN_FUNCTION_PREFIXES) or name in FORBIDDEN_FUNCTIONS:
                raise UnsafeSQLError(f"function {name}() is not allowed")

    cte_names = {cte.alias_or_name for cte in root.find_all(exp.CTE)}
    for table in root.find_all(exp.Table):
        if table.name in cte_names:
            continue
        if table.name not in READABLE_TABLES:
            raise UnsafeSQLError(f"table '{table.name}' is not readable by the agent")
        if (table.db or "") not in ALLOWED_SCHEMAS:
            raise UnsafeSQLError(f"schema '{table.db}' is not readable by the agent")

    return cleaned


def cap_rows(sql: str, cap: int = ROW_CAP) -> str:
    """Wrap a guarded SELECT so the database returns at most ``cap`` rows.

    The newline before the closing parenthesis stops a trailing ``--`` comment
    in the model's SQL from swallowing the wrapper.
    """
    return f"SELECT * FROM (\n{sql}\n) AS capped_result LIMIT {int(cap)}"
