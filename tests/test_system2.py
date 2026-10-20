"""
BDD (Behavior-Driven Development) tests for System 2 — Agentic Reasoning.

Each test reads like a scenario:
    GIVEN a loaded environment with seeded data
    WHEN  a REASON event is dispatched (or reason() is called)
    THEN  a grounded response envelope is produced.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from d4.system0 import load_system0
from d4.models import EventType, JEVEvent, MessagePromptEnvelope
from d4.system1 import dispatch
from d4.system2 import reason, clear_response_log, get_response_log
from d4.handlers.lookup import _store, seed_store_with_pk

# Ensure all handlers (including system2's REASON/RESPONSE) are registered
import d4.handlers  # noqa: F401
import d4.system2   # noqa: F401

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"


@pytest.fixture
def env():
    return load_system0(CONTRACTS_DIR)


@pytest.fixture(autouse=True)
def _clean():
    _store.clear()
    clear_response_log()
    yield
    _store.clear()
    clear_response_log()


class TestReasonHighLevelAPI:
    """WHEN reason() is called with a question about an FQTN."""

    def test_reason_with_data(self, env):
        """THEN a response envelope is returned with confidence=1.0."""
        seed_store_with_pk("enrollment.student", "student_id", [
            {
                "student_id": "12345678",
                "last_name": "Heller",
                "first_name": "Peter",
                "email": "peter@qc.cuny.edu",
            }
        ])
        response = reason(
            question="Who is enrolled?",
            fqtn="enrollment.student",
            env=env,
        )
        assert response.confidence == 1.0
        assert "enrollment.student" in response.grounded_in
        assert "12345678" in response.answer

    def test_reason_without_data(self, env):
        """THEN an empty FQTN returns confidence=0.0."""
        response = reason(
            question="Who is enrolled?",
            fqtn="enrollment.student",
            env=env,
        )
        assert response.confidence == 0.0
        assert response.grounded_in == []


class TestReasonDispatch:
    """WHEN a REASON event is dispatched through System 1."""

    def test_reason_event_dispatch(self, env):
        """THEN dispatch returns ok=True with a response dict in data."""
        seed_store_with_pk("enrollment.student", "student_id", [
            {
                "student_id": "12345678",
                "last_name": "Heller",
                "first_name": "Peter",
                "email": "peter@qc.cuny.edu",
            }
        ])
        prompt = MessagePromptEnvelope(
            fqtn="enrollment.student",
            question="How many students?",
        )
        event = prompt.to_jev()
        result = dispatch(event, env)
        assert result.ok is True
        assert "response" in result.data
        assert result.data["response"]["confidence"] == 1.0

    def test_invalid_prompt_envelope(self, env):
        """THEN a malformed REASON payload returns ok=False."""
        event = JEVEvent(
            type=EventType.REASON,
            fqtn="enrollment.student",
            payload={"not_a_question": True},
        )
        result = dispatch(event, env)
        assert result.ok is False


class TestResponseHandler:
    """WHEN a RESPONSE event is dispatched."""

    def test_response_logged(self, env):
        """THEN the response envelope is logged."""
        event = JEVEvent(
            type=EventType.RESPONSE,
            fqtn="enrollment.student",
            payload={
                "fqtn": "enrollment.student",
                "answer": "42 students enrolled",
                "confidence": 0.95,
                "grounded_in": ["enrollment.student"],
            },
        )
        result = dispatch(event, env)
        assert result.ok is True
        log = get_response_log()
        assert len(log) == 1
        assert log[0]["answer"] == "42 students enrolled"
