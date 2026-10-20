"""
NOTIFY handler — emits a domain notification to subscribers.

In the PoC (Proof of Concept), "emit" means appending to an in-memory
log list.  In production this would publish to a message bus, webhook,
or PostgreSQL LISTEN/NOTIFY channel.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import DispatchResult, EventType, JEVEvent, System0Env
from ..system1 import event_handler

# In-memory notification log for the PoC
_notification_log: list[dict] = []


def get_notification_log() -> list[dict]:
    """Return a copy of the notification log (for testing and demo)."""
    return list(_notification_log)


def clear_notification_log() -> None:
    """Reset the log between test runs."""
    _notification_log.clear()


@event_handler(EventType.NOTIFY)
def handle_notify(event: JEVEvent, env: System0Env) -> DispatchResult:
    """Log a domain notification derived from the event payload."""
    try:
        contract = env.get_contract(event.fqtn)
    except KeyError:
        return DispatchResult(
            ok=False,
            event_type=event.type,
            message=f"No contract found for FQTN '{event.fqtn}'",
            errors=[{"type": "unknown_fqtn", "fqtn": event.fqtn}],
        )

    entry = {
        "fqtn": event.fqtn,
        "source": event.source,
        "correlation_id": event.correlation_id,
        "payload": event.payload,
        "notified_at": datetime.now(timezone.utc).isoformat(),
    }
    _notification_log.append(entry)

    return DispatchResult(
        ok=True,
        event_type=event.type,
        message=f"Notification emitted for '{event.fqtn}' (log entry #{len(_notification_log)})",
        data={"log_entry": entry},
    )
