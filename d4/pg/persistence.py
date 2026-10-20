"""
PostgreSQL 18 persistence layer — connects the in-memory PoC store to a
real database when one is available.

Governing claim: the persistence layer is optional.  The PoC runs entirely
in-memory; this module provides the bridge for when a PostgreSQL 18
instance is reachable.  It uses psycopg (v3) — the modern, async-capable
PostgreSQL adapter.

Usage in the PoC demo:
    If PostgreSQL is available → tables are created and records are persisted.
    If PostgreSQL is not available → the demo continues in-memory only.
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import FQTNContract, System0Env
from .ddl import env_to_ddl

logger = logging.getLogger(__name__)


class PgPersistence:
    """
    Thin persistence wrapper around a psycopg connection.

    Methods mirror the in-memory store operations (upsert, lookup)
    so the demo runner can optionally delegate to PostgreSQL.
    """

    def __init__(self, conninfo: str):
        """
        Initialize with a PostgreSQL connection string.

        Args:
            conninfo: libpq-style connection string, e.g.
                      "host=localhost dbname=d4_poc user=d4"
        """
        self._conninfo = conninfo
        self._conn = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """
        Attempt to connect to PostgreSQL.

        Returns True on success, False if psycopg is not installed
        or the connection fails.
        """
        try:
            import psycopg  # noqa: F401 — optional dependency

            self._conn = psycopg.connect(self._conninfo)
            logger.info("Connected to PostgreSQL: %s", self._conninfo)
            return True
        except ImportError:
            logger.warning(
                "psycopg not installed — running in-memory only.  "
                "Install with: pip install psycopg[binary]"
            )
            return False
        except Exception as exc:
            logger.warning("PostgreSQL connection failed: %s", exc)
            return False

    def close(self) -> None:
        """Close the connection if open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    # ------------------------------------------------------------------
    # Schema bootstrap
    # ------------------------------------------------------------------

    def bootstrap(self, env: System0Env) -> str:
        """
        Generate and execute the full DDL for the environment.

        Returns the DDL string that was executed.
        """
        ddl = env_to_ddl(env)
        if self._conn is not None:
            with self._conn.cursor() as cur:
                cur.execute(ddl)
            self._conn.commit()
            logger.info("DDL executed — %d contracts bootstrapped", len(env.contracts))
        return ddl

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def upsert(self, contract: FQTNContract, record: dict[str, Any]) -> None:
        """
        Insert or update a record in the contract's table.

        Uses PostgreSQL's INSERT … ON CONFLICT … DO UPDATE (upsert).
        """
        if self._conn is None:
            return

        schema = contract.schema_name
        table = contract.table_name
        pk = contract.primary_key
        columns = list(record.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        col_list = ", ".join(columns)
        update_set = ", ".join(
            f"{c} = EXCLUDED.{c}" for c in columns if c != pk
        )

        sql = (
            f"INSERT INTO {schema}.{table} ({col_list}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT ({pk}) DO UPDATE SET {update_set}"
        )

        with self._conn.cursor() as cur:
            cur.execute(sql, [record[c] for c in columns])
        self._conn.commit()

    def lookup(self, contract: FQTNContract, pk_value: Any) -> dict[str, Any] | None:
        """
        Look up a single record by primary key.

        Returns the record as a dict, or None if not found.
        """
        if self._conn is None:
            return None

        schema = contract.schema_name
        table = contract.table_name
        pk = contract.primary_key

        sql = f"SELECT * FROM {schema}.{table} WHERE {pk} = %s"

        with self._conn.cursor() as cur:
            cur.execute(sql, [pk_value])
            row = cur.fetchone()
            if row is None:
                return None
            col_names = [desc[0] for desc in cur.description]
            return dict(zip(col_names, row))

    def count(self, contract: FQTNContract) -> int:
        """Return the row count for the contract's table."""
        if self._conn is None:
            return 0

        schema = contract.schema_name
        table = contract.table_name

        sql = f"SELECT COUNT(*) FROM {schema}.{table}"

        with self._conn.cursor() as cur:
            cur.execute(sql, [])
            return cur.fetchone()[0]


def try_connect(conninfo: str | None) -> PgPersistence | None:
    """
    Convenience: attempt a connection, return None if unavailable.

    The PoC demo runner calls this with an optional conninfo string.
    When None is passed, PostgreSQL is skipped entirely.
    """
    if conninfo is None:
        logger.info("No PostgreSQL conninfo provided — in-memory only")
        return None

    pg = PgPersistence(conninfo)
    if pg.connect():
        return pg
    return None
