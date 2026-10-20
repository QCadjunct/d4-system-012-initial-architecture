"""
BDD (Behavior-Driven Development) tests for System 0 — Domain Declaration.

Each test reads like a scenario:
    GIVEN a YAML contract directory
    WHEN  the environment is loaded
    THEN  contracts, field declarations, and payload models behave correctly.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from pydantic import ValidationError

from d4.system0 import load_system0, validate_payload

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"


# -----------------------------------------------------------------------
# GIVEN: a YAML contracts directory with three enrollment FQTNs
# -----------------------------------------------------------------------

@pytest.fixture
def env():
    """Load the System 0 environment from the contracts directory."""
    return load_system0(CONTRACTS_DIR)


class TestContractLoading:
    """WHEN the contracts directory is loaded into System 0."""

    def test_three_contracts_loaded(self, env):
        """THEN three FQTN contracts are present."""
        assert len(env.contracts) == 3

    def test_student_contract_exists(self, env):
        """THEN enrollment.student is among the loaded contracts."""
        assert "enrollment.student" in env.contracts

    def test_section_contract_exists(self, env):
        """THEN enrollment.section is among the loaded contracts."""
        assert "enrollment.section" in env.contracts

    def test_registration_contract_exists(self, env):
        """THEN enrollment.registration is among the loaded contracts."""
        assert "enrollment.registration" in env.contracts

    def test_student_owner(self, env):
        """THEN enrollment.student is owned by 'registrar'."""
        assert env.contracts["enrollment.student"].owner == "registrar"

    def test_student_primary_key(self, env):
        """THEN enrollment.student's primary key is 'student_id'."""
        assert env.contracts["enrollment.student"].primary_key == "student_id"

    def test_event_types_collected(self, env):
        """THEN the event_types set contains at least validate, lookup, mutate, notify."""
        for et in ("validate", "lookup", "mutate", "notify"):
            assert et in env.event_types


class TestPayloadValidation:
    """WHEN payloads are validated against the student contract."""

    def test_valid_student_payload(self, env):
        """THEN a complete, well-formed payload passes validation."""
        contract = env.get_contract("enrollment.student")
        ok, validated, errors = validate_payload(contract, {
            "student_id": "12345678",
            "last_name": "Heller",
            "first_name": "Peter",
            "email": "peter@qc.cuny.edu",
        })
        assert ok is True
        assert validated["student_id"] == "12345678"
        assert errors == []

    def test_missing_required_field(self, env):
        """THEN a payload missing 'email' (required) fails validation."""
        contract = env.get_contract("enrollment.student")
        ok, validated, errors = validate_payload(contract, {
            "student_id": "12345678",
            "last_name": "Heller",
            "first_name": "Peter",
        })
        assert ok is False
        assert validated is None
        assert any(e["field"] == "email" for e in errors)

    def test_invalid_student_id_pattern(self, env):
        """THEN a student_id not matching ^\\d{8}$ fails validation."""
        contract = env.get_contract("enrollment.student")
        ok, validated, errors = validate_payload(contract, {
            "student_id": "ABCD",
            "last_name": "Heller",
            "first_name": "Peter",
            "email": "peter@qc.cuny.edu",
        })
        assert ok is False
        assert any(e["field"] == "student_id" for e in errors)

    def test_optional_fields_omitted(self, env):
        """THEN optional fields (gpa, is_active) may be omitted."""
        contract = env.get_contract("enrollment.student")
        ok, validated, errors = validate_payload(contract, {
            "student_id": "12345678",
            "last_name": "Doe",
            "first_name": "Jane",
            "email": "jane@example.com",
        })
        assert ok is True
        # Optional fields should not appear in validated dict when omitted
        assert "gpa" not in validated
        assert "is_active" not in validated

    def test_optional_fields_included(self, env):
        """THEN optional fields with valid values pass through."""
        contract = env.get_contract("enrollment.student")
        ok, validated, errors = validate_payload(contract, {
            "student_id": "12345678",
            "last_name": "Doe",
            "first_name": "Jane",
            "email": "jane@example.com",
            "gpa": 3.75,
            "is_active": True,
        })
        assert ok is True
        assert validated["gpa"] == 3.75
        assert validated["is_active"] is True
