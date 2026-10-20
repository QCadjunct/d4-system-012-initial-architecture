"""
DDL (Data Definition Language) generation from FQTN contracts → PostgreSQL 18.

Governing claim: the YAML contract is the single source of truth.  This
module reads FQTNContract objects and emits standards-compliant DDL.
Every table lives in a schema named after the FQTN's domain prefix
(e.g., enrollment.student → schema "enrollment", table "student").

Type mapping:
    YAML type     → PostgreSQL type
    ─────────────────────────────────
    string (default) → TEXT
    number           → NUMERIC
    integer          → INTEGER
    boolean          → BOOLEAN

Constraints:
    - required: true          → NOT NULL
    - primary_key              → PRIMARY KEY
    - rule (regex pattern)     → CHECK (col ~ 'pattern')
"""

from __future__ import annotations

from ..models import FQTNContract, System0Env

# ---------------------------------------------------------------------------
# YAML → PostgreSQL type map
# ---------------------------------------------------------------------------

_PG_TYPE_MAP: dict[str, str] = {
    "string": "TEXT",
    "number": "NUMERIC",
    "integer": "INTEGER",
    "boolean": "BOOLEAN",
}


def _pg_type(yaml_type: str | None) -> str:
    """Map a YAML field type to its PostgreSQL equivalent."""
    return _PG_TYPE_MAP.get(yaml_type or "string", "TEXT")


# ---------------------------------------------------------------------------
# Single-contract DDL
# ---------------------------------------------------------------------------

def contract_to_ddl(contract: FQTNContract) -> str:
    """
    Generate CREATE TABLE DDL for one FQTN contract.

    Returns a complete, runnable SQL statement including:
      - Schema-qualified table name (domain.table)
      - Column definitions with types and NOT NULL
      - PRIMARY KEY constraint
      - CHECK constraints for regex-validated fields
    """
    schema = contract.schema_name
    table = contract.table_name
    pk = contract.primary_key
    lines: list[str] = []

    for field_name, decl in contract.fields.items():
        col_type = _pg_type(decl.type)
        nullable = "" if decl.required else ""
        not_null = " NOT NULL" if decl.required else ""
        pk_marker = " PRIMARY KEY" if field_name == pk else ""

        col_def = f"    {field_name} {col_type}{not_null}{pk_marker}"
        lines.append(col_def)

        # Regex rule → CHECK constraint
        if decl.rule:
            # Escape single quotes for SQL
            pattern = decl.rule.replace("'", "''")
            lines.append(
                f"        CONSTRAINT chk_{table}_{field_name} "
                f"CHECK ({field_name} ~ '{pattern}')"
            )

    body = ",\n".join(lines)

    return (
        f"-- FQTN: {contract.fqtn}  owner: {contract.owner}\n"
        f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n"
        f"{body}\n"
        f");\n"
    )


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

def schema_ddl(contract: FQTNContract) -> str:
    """Generate CREATE SCHEMA IF NOT EXISTS for the contract's domain."""
    return f"CREATE SCHEMA IF NOT EXISTS {contract.schema_name};\n"


# ---------------------------------------------------------------------------
# Full environment DDL
# ---------------------------------------------------------------------------

def env_to_ddl(env: System0Env) -> str:
    """
    Generate the complete DDL for all contracts in a System 0 environment.

    Output order:
      1. CREATE SCHEMA statements (deduplicated)
      2. CREATE TABLE statements (one per FQTN)
    """
    schemas_seen: set[str] = set()
    schema_stmts: list[str] = []
    table_stmts: list[str] = []

    for fqtn, contract in sorted(env.contracts.items()):
        s = contract.schema_name
        if s not in schemas_seen:
            schemas_seen.add(s)
            schema_stmts.append(schema_ddl(contract))
        table_stmts.append(contract_to_ddl(contract))

    header = (
        "-- ============================================================\n"
        "-- D⁴ DDL — auto-generated from YAML FQTN contracts\n"
        "-- Target: PostgreSQL 18\n"
        "-- ============================================================\n\n"
    )

    return header + "\n".join(schema_stmts) + "\n" + "\n".join(table_stmts)
