"""
VALIDATE handler — validates a payload against its FQTN contract.

Pydantic does the heavy lifting.  This handler:
  1. Looks up the contract by FQTN
  2. Calls validate_payload() (which delegates to Pydantic)
  3. Returns a DispatchResult with ok/errors
"""

from __future__ import annotations

from ..models import DispatchResult, EventType, JEVEvent, System0Env
from ..system0 import validate_payload
from ..system1 import event_handler


@event_handler(EventType.VALIDATE)
def handle_validate(event: JEVEvent, env: System0Env) -> DispatchResult:
    """Validate the event's payload against its FQTN contract."""
    try:
        contract = env.get_contract(event.fqtn)
    except KeyError:
        return DispatchResult(
            ok=False,
            event_type=event.type,
            message=f"No contract found for FQTN '{event.fqtn}'",
            errors=[{"type": "unknown_fqtn", "fqtn": event.fqtn}],
        )

    ok, validated, errors = validate_payload(contract, event.payload)

    if ok:
        return DispatchResult(
            ok=True,
            event_type=event.type,
            message=f"Payload for '{event.fqtn}' is valid",
            data={"validated_payload": validated},
        )
    else:
        return DispatchResult(
            ok=False,
            event_type=event.type,
            message=f"Validation failed for '{event.fqtn}'",
            errors=errors,
        )
