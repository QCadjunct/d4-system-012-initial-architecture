"""
BDD (Behavior-Driven Development) tests for PostgreSQL DDL generation.

Each test reads like a scenario:
    GIVEN FQTN contracts loaded from YAML
    WHEN  DDL is generated
    THEN  the output is valid PostgreSQL 18 syntax.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from d4.system0 import load_system0
from d4.pg.ddl import contract_to_ddl, env_to_ddl, schema_ddl

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"


@pytest.fixture
def env():
    return load_system0(CONTRACTS_DIR)


class TestSchemaDDL:
    """WHEN schema DDL is generated for a contract."""

    def test_schema_statement(self, env):
        """THEN the CREATE SCHEMA statement uses the FQTN domain prefix."""
        contract = env.get_contract("enrollment.student")
        ddl = schema_ddl(contract)
        assert "CREATE SCHEMA IF NOT EXISTS enrollment;" in ddl


class TestTableDDL:
    """WHEN table DDL is generated for the student contract."""

    def test_table_name(self, env):
        """THEN the table is schema-qualified as enrollment.student."""
        contract = env.get_contract("enrollment.student")
        ddl = contract_to_ddl(contract)
        assert "CREATE TABLE IF NOT EXISTS enrollment.student" in ddl

    def test_primary_key(self, env):
        """THEN student_id is marked PRIMARY KEY."""
        contract = env.get_contract("enrollment.student")
        ddl = contract_to_ddl(contract)
        assert "student_id TEXT NOT NULL PRIMARY KEY" in ddl

    def test_not_null_on_required(self, env):
        """THEN required fields have NOT NULL."""
        contract = env.get_contract("enrollment.student")
        ddl = contract_to_ddl(contract)
        assert "last_name TEXT NOT NULL" in ddl
        assert "first_name TEXT NOT NULL" in ddl
        assert "email TEXT NOT NULL" in ddl

    def test_optional_field_nullable(self, env):
        """THEN optional fields do NOT have NOT NULL."""
        contract = env.get_contract("enrollment.student")
        ddl = contract_to_ddl(contract)
        # gpa should be NUMERIC without NOT NULL
        assert "gpa NUMERIC" in ddl
        assert "gpa NUMERIC NOT NULL" not in ddl

    def test_check_constraint_for_regex(self, env):
        """THEN fields with a 'rule' get a CHECK constraint."""
        contract = env.get_contract("enrollment.student")
        ddl = contract_to_ddl(contract)
        assert "CONSTRAINT chk_student_student_id CHECK" in ddl
        assert "student_id ~ " in ddl

    def test_fqtn_comment(self, env):
        """THEN the DDL includes the FQTN and owner as a comment."""
        contract = env.get_contract("enrollment.student")
        ddl = contract_to_ddl(contract)
        assert "-- FQTN: enrollment.student  owner: registrar" in ddl


class TestFullEnvironmentDDL:
    """WHEN DDL is generated for the entire System 0 environment."""

    def test_header_present(self, env):
        """THEN the output starts with the D⁴ header comment."""
        ddl = env_to_ddl(env)
        assert "D⁴ DDL" in ddl
        assert "PostgreSQL 18" in ddl

    def test_all_three_tables(self, env):
        """THEN all three enrollment tables appear."""
        ddl = env_to_ddl(env)
        assert "enrollment.student" in ddl
        assert "enrollment.section" in ddl
        assert "enrollment.registration" in ddl

    def test_schema_created_once(self, env):
        """THEN CREATE SCHEMA enrollment appears exactly once."""
        ddl = env_to_ddl(env)
        assert ddl.count("CREATE SCHEMA IF NOT EXISTS enrollment;") == 1
