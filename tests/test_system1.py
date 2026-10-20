"""
BDD (Behavior-Driven Development) tests for System 1 — JEV Dispatch.

Each test reads like a scenario:
    GIVEN a loaded System 0 environment and registered handlers
    WHEN  a JEV event is dispatched
    THEN  the correct handler runs and returns the expected DispatchResult.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from d4.system0 import load_system0
from d4.models import EventType, JEVEvent, DispatchResult
from d4.system1 import dispatch, get_registry
from d4.handlers.lookup import _store, seed_store_with_pk
from d4.handlers.notify import clear_notification_log, get_notification_log

# Importing handlers registers them with the dispatch registry
import d4.handlers  # noqa: F401

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"


@pytest.fixture
def env():
    return load_system0(CONTRACTS_DIR)


@pytest.fixture(autouse=True)
def _clean_store():
    """Clear in-memory store before each test."""
    _store.clear()
    clear_notification_log()
    yield
    _store.clear()
    clear_notification_log()


class TestHandlerRegistry:
    """WHEN the handler modules are imported."""

    def test_all_four_base_handlers_registered(self):
        """THEN validate, lookup, mutate, notify handlers are in the registry."""
        registry = get_registry()
        for et in ("validate", "lookup", "mutate", "notify"):
            assert et in registry, f"Handler for '{et}' not registered"


class TestValidateDispatch:
    """WHEN a VALIDATE event is dispatched."""

    def test_valid_payload_succeeds(self, env):
        """THEN a valid payload returns ok=True."""
        event = JEVEvent(
            type=EventType.VALIDATE,
            fqtn="enrollment.student",
            payload={
                "student_id": "12345678",
                "last_name": "Heller",
                "first_name": "Peter",
                "email": "peter@qc.cuny.edu",
            },
        )
        result = dispatch(event, env)
        assert result.ok is True
        assert result.event_type == "validate"

    def test_invalid_payload_fails(self, env):
        """THEN an invalid payload returns ok=False with errors."""
        event = JEVEvent(
            type=EventType.VALIDATE,
            fqtn="enrollment.student",
            payload={"student_id": "BAD"},
        )
        result = dispatch(event, env)
        assert result.ok is False
        assert len(result.errors) > 0


class TestLookupDispatch:
    """WHEN a LOOKUP event is dispatched."""

    def test_lookup_existing_record(self, env):
        """THEN a seeded record is found by primary key."""
        seed_store_with_pk("enrollment.student", "student_id", [
            {
                "student_id": "12345678",
                "last_name": "Heller",
                "first_name": "Peter",
                "email": "peter@qc.cuny.edu",
            }
        ])
        event = JEVEvent(
            type=EventType.LOOKUP,
            fqtn="enrollment.student",
            payload={"student_id": "12345678"},
        )
        result = dispatch(event, env)
        assert result.ok is True
        assert result.data["record"]["last_name"] == "Heller"

    def test_lookup_missing_record(self, env):
        """THEN a missing PK returns ok=False."""
        event = JEVEvent(
            type=EventType.LOOKUP,
            fqtn="enrollment.student",
            payload={"student_id": "99999999"},
        )
        result = dispatch(event, env)
        assert result.ok is False


class TestMutateDispatch:
    """WHEN a MUTATE event is dispatched."""

    def test_mutate_creates_record(self, env):
        """THEN a valid payload creates a new record (action='created')."""
        event = JEVEvent(
            type=EventType.MUTATE,
            fqtn="enrollment.student",
            payload={
                "student_id": "12345678",
                "last_name": "Heller",
                "first_name": "Peter",
                "email": "peter@qc.cuny.edu",
            },
        )
        result = dispatch(event, env)
        assert result.ok is True
        assert result.data["action"] == "created"

    def test_mutate_updates_record(self, env):
        """THEN a second mutate on the same PK returns action='updated'."""
        payload = {
            "student_id": "12345678",
            "last_name": "Heller",
            "first_name": "Peter",
            "email": "peter@qc.cuny.edu",
        }
        event1 = JEVEvent(type=EventType.MUTATE, fqtn="enrollment.student", payload=payload)
        dispatch(event1, env)

        payload["email"] = "p.heller@qc.cuny.edu"
        event2 = JEVEvent(type=EventType.MUTATE, fqtn="enrollment.student", payload=payload)
        result = dispatch(event2, env)
        assert result.ok is True
        assert result.data["action"] == "updated"

    def test_mutate_rejects_invalid_payload(self, env):
        """THEN an invalid payload is rejected before storage."""
        event = JEVEvent(
            type=EventType.MUTATE,
            fqtn="enrollment.student",
            payload={"student_id": "BAD"},
        )
        result = dispatch(event, env)
        assert result.ok is False
        assert "enrollment.student" not in _store


class TestNotifyDispatch:
    """WHEN a NOTIFY event is dispatched."""

    def test_notify_logs_entry(self, env):
        """THEN a notification entry is appended to the log."""
        event = JEVEvent(
            type=EventType.NOTIFY,
            fqtn="enrollment.student",
            payload={"student_id": "12345678", "action": "created"},
        )
        result = dispatch(event, env)
        assert result.ok is True
        log = get_notification_log()
        assert len(log) == 1
        assert log[0]["fqtn"] == "enrollment.student"


class TestUnknownFQTN:
    """WHEN an event references an unknown FQTN."""

    def test_unknown_fqtn_returns_error(self, env):
        """THEN every handler returns ok=False with an unknown_fqtn error."""
        event = JEVEvent(
            type=EventType.VALIDATE,
            fqtn="bogus.table",
            payload={"x": 1},
        )
        result = dispatch(event, env)
        assert result.ok is False
        assert any(e["type"] == "unknown_fqtn" for e in result.errors)
