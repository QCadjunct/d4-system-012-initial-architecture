"""
MUTATE handler — validates then upserts a record into the in-memory store.

Governing claim: every mutation passes through VALIDATE first, so the
handler composes validation + storage in a single dispatch cycle.
"""

from __future__ import annotations

from ..models import DispatchResult, EventType, JEVEvent, System0Env
from ..system0 import validate_payload
from ..system1 import event_handler
from .lookup import _store, seed_store_with_pk


@event_handler(EventType.MUTATE)
def handle_mutate(event: JEVEvent, env: System0Env) -> DispatchResult:
    """Validate the payload, then upsert the record keyed by primary key."""
    try:
        contract = env.get_contract(event.fqtn)
    except KeyError:
        return DispatchResult(
            ok=False,
            event_type=event.type,
            message=f"No contract found for FQTN '{event.fqtn}'",
            errors=[{"type": "unknown_fqtn", "fqtn": event.fqtn}],
        )

    # --- Step 1: validate against the YAML contract ---
    ok, validated, errors = validate_payload(contract, event.payload)
    if not ok:
        return DispatchResult(
            ok=False,
            event_type=event.type,
            message=f"Mutation rejected — validation failed for '{event.fqtn}'",
            errors=errors,
        )

    # --- Step 2: upsert into the in-memory store ---
    pk_field = contract.primary_key
    pk_value = str(validated[pk_field])

    if event.fqtn not in _store:
        _store[event.fqtn] = {}

    is_update = pk_value in _store[event.fqtn]
    _store[event.fqtn][pk_value] = validated

    verb = "updated" if is_update else "created"

    return DispatchResult(
        ok=True,
        event_type=event.type,
        message=f"Record {verb} for {pk_field}='{pk_value}' in '{event.fqtn}'",
        data={"record": validated, "action": verb},
    )
