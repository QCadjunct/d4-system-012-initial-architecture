"""
LOOKUP handler — retrieves a record by primary key from the in-memory store.

In the PoC (Proof of Concept), the store is a simple dict keyed by FQTN,
each value a dict of records keyed by primary key.  In production this
would delegate to the PostgreSQL persistence layer.
"""

from __future__ import annotations

from ..models import DispatchResult, EventType, JEVEvent, System0Env
from ..system1 import event_handler

# In-memory store for the PoC — maps FQTN → {pk_value → record}
_store: dict[str, dict[str, dict]] = {}


def get_store() -> dict[str, dict[str, dict]]:
    """Access the in-memory store (for testing and demo)."""
    return _store


def seed_store(fqtn: str, records: list[dict]) -> None:
    """Pre-populate the store with records for a given FQTN."""
    if fqtn not in _store:
        _store[fqtn] = {}
    for rec in records:
        # We need the contract to know the PK, but for simplicity
        # we use the first field as the key identifier
        _store[fqtn][str(list(rec.values())[0])] = rec


def seed_store_with_pk(fqtn: str, pk_field: str, records: list[dict]) -> None:
    """Pre-populate the store with records, using the named PK field."""
    if fqtn not in _store:
        _store[fqtn] = {}
    for rec in records:
        _store[fqtn][str(rec[pk_field])] = rec


@event_handler(EventType.LOOKUP)
def handle_lookup(event: JEVEvent, env: System0Env) -> DispatchResult:
    """Look up a record by primary key value in the payload."""
    try:
        contract = env.get_contract(event.fqtn)
    except KeyError:
        return DispatchResult(
            ok=False,
            event_type=event.type,
            message=f"No contract found for FQTN '{event.fqtn}'",
            errors=[{"type": "unknown_fqtn", "fqtn": event.fqtn}],
        )

    pk_field = contract.primary_key
    pk_value = event.payload.get(pk_field)

    if pk_value is None:
        return DispatchResult(
            ok=False,
            event_type=event.type,
            message=f"Primary key field '{pk_field}' missing from payload",
            errors=[{"type": "missing_pk", "field": pk_field}],
        )

    fqtn_store = _store.get(event.fqtn, {})
    record = fqtn_store.get(str(pk_value))

    if record is None:
        return DispatchResult(
            ok=False,
            event_type=event.type,
            message=f"No record found for {pk_field}='{pk_value}' in '{event.fqtn}'",
            data={"pk_field": pk_field, "pk_value": str(pk_value)},
        )

    return DispatchResult(
        ok=True,
        event_type=event.type,
        message=f"Record found for {pk_field}='{pk_value}'",
        data={"record": record},
    )
