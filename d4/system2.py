"""
System 2 — Agentic Reasoning via bounded prompt graphs.

Governing claim: System 2 rides the same JEV (JSON Event Vocabulary) bus
as System 1.  A REASON event carries a MessagePromptEnvelope; a RESPONSE
event carries a MessageResponseEnvelope.  The agentic layer never
bypasses the dispatch grammar — it simply adds two more event types.

In the PoC (Proof of Concept), the "agent" is a deterministic stub that
answers from the in-memory store.  In production this would delegate to
a bounded prompt graph (an LLM with retrieval-augmented grounding
constrained by the FQTN contracts).

High-level API:
    reason(question, fqtn, env, source) → MessageResponseEnvelope
"""

from __future__ import annotations

from typing import Any

from .handlers.lookup import _store
from .models import (
    DispatchResult,
    EventType,
    JEVEvent,
    MessagePromptEnvelope,
    MessageResponseEnvelope,
    System0Env,
)
from .system1 import dispatch, event_handler


# ---------------------------------------------------------------------------
# REASON handler — receives the prompt envelope, produces a response
# ---------------------------------------------------------------------------

@event_handler(EventType.REASON)
def handle_reason(event: JEVEvent, env: System0Env) -> DispatchResult:
    """
    Process a REASON event whose payload is a MessagePromptEnvelope.

    The PoC agent answers by looking up the FQTN's in-memory store
    and summarising what it finds.  A production agent would run a
    bounded prompt graph here.
    """
    try:
        prompt = MessagePromptEnvelope.model_validate(event.payload)
    except Exception as exc:
        return DispatchResult(
            ok=False,
            event_type=event.type,
            message=f"Invalid REASON payload: {exc}",
            errors=[{"type": "invalid_prompt_envelope", "detail": str(exc)}],
        )

    # --- Deterministic stub agent ---
    fqtn = prompt.fqtn
    question = prompt.question
    records = _store.get(fqtn, {})

    if not records:
        answer = f"No records found for '{fqtn}'."
        confidence = 0.0
        grounded_in = []
    else:
        record_summaries = [
            f"  • {pk}: {rec}" for pk, rec in list(records.items())[:10]
        ]
        answer = (
            f"Found {len(records)} record(s) for '{fqtn}'.\n"
            + "\n".join(record_summaries)
        )
        confidence = 1.0
        grounded_in = [fqtn]

    response_envelope = MessageResponseEnvelope(
        fqtn=fqtn,
        answer=answer,
        confidence=confidence,
        grounded_in=grounded_in,
    )

    return DispatchResult(
        ok=True,
        event_type=event.type,
        message=f"Agentic reasoning complete for '{fqtn}'",
        data={"response": response_envelope.model_dump()},
    )


# ---------------------------------------------------------------------------
# RESPONSE handler — receives and logs the response envelope
# ---------------------------------------------------------------------------

_response_log: list[dict] = []


def get_response_log() -> list[dict]:
    """Return a copy of the response log (for testing and demo)."""
    return list(_response_log)


def clear_response_log() -> None:
    """Reset the log between test runs."""
    _response_log.clear()


@event_handler(EventType.RESPONSE)
def handle_response(event: JEVEvent, env: System0Env) -> DispatchResult:
    """Receive and log a RESPONSE event (the agent's answer)."""
    try:
        response = MessageResponseEnvelope.model_validate(event.payload)
    except Exception as exc:
        return DispatchResult(
            ok=False,
            event_type=event.type,
            message=f"Invalid RESPONSE payload: {exc}",
            errors=[{"type": "invalid_response_envelope", "detail": str(exc)}],
        )

    _response_log.append(response.model_dump())

    return DispatchResult(
        ok=True,
        event_type=event.type,
        message=f"Response logged for '{response.fqtn}' (confidence={response.confidence})",
        data={"response": response.model_dump()},
    )


# ---------------------------------------------------------------------------
# High-level API — reason()
# ---------------------------------------------------------------------------

def reason(
    question: str,
    fqtn: str,
    env: System0Env,
    source: str = "system2.reason",
    context: dict[str, Any] | None = None,
) -> MessageResponseEnvelope:
    """
    High-level convenience: ask a question about an FQTN and get an answer.

    Composes:
      1. Build a MessagePromptEnvelope
      2. Wrap it in a JEV REASON event
      3. Dispatch through System 1
      4. Extract the MessageResponseEnvelope from the result

    Returns the response envelope, or raises ValueError on dispatch failure.
    """
    prompt = MessagePromptEnvelope(
        fqtn=fqtn,
        question=question,
        context=context or {},
    )

    event = prompt.to_jev(source=source)
    result = dispatch(event, env)

    if not result.ok:
        raise ValueError(
            f"REASON dispatch failed for '{fqtn}': {result.message}"
        )

    return MessageResponseEnvelope.model_validate(result.data["response"])
