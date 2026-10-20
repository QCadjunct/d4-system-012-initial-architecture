"""
System 1 — JEV (JSON Event Vocabulary) Dispatch.

The evaluator layer.  A JEV event enters, dispatch() looks up its type
in the handler registry, and the matching handler runs the domain logic.

Key patterns:
  - @event_handler decorator stores handlers in _registry
  - EventType StrEnum forces dotted-name comparison in match/case
  - The wildcard case catches unregistered event types gracefully
  - Adding a new event type = registering a handler, not editing a chain

Tihomir Manushev's interpreter pattern: bare names capture,
dotted names compare.
"""

from __future__ import annotations

from typing import Any, Callable

from .models import (
    DispatchResult,
    EventType,
    JEVEvent,
    System0Env,
)

# ---------------------------------------------------------------------------
# Handler registry — the decorator pattern
# ---------------------------------------------------------------------------

_registry: dict[str, Callable[..., DispatchResult]] = {}


def event_handler(event_type: EventType):
    """
    Register a function as the handler for a JEV event type.

    Usage:
        @event_handler(EventType.VALIDATE)
        def handle_validate(event: JEVEvent, env: System0Env) -> DispatchResult:
            ...

    No central file lists every handler.  Importing a module that defines
    one is enough to register it.
    """
    def decorator(func: Callable[..., DispatchResult]) -> Callable[..., DispatchResult]:
        _registry[event_type.value] = func
        return func
    return decorator


def get_registry() -> dict[str, Callable[..., DispatchResult]]:
    """Return a copy of the current handler registry (for inspection/testing)."""
    return dict(_registry)


# ---------------------------------------------------------------------------
# dispatch() — the match/case interpreter
# ---------------------------------------------------------------------------

def dispatch(event: JEVEvent, env: System0Env) -> DispatchResult:
    """
    Route a JEV event to its registered handler.

    Uses the StrEnum-forced dotted-name comparison pattern:
      case EventType.VALIDATE:  → value comparison (correct)
      case x:                   → capture pattern (bug — avoided by StrEnum)

    The wildcard catches any event type without a registered handler.
    """
    match event.type:
        case EventType.VALIDATE:
            handler = _registry.get(EventType.VALIDATE.value)
        case EventType.LOOKUP:
            handler = _registry.get(EventType.LOOKUP.value)
        case EventType.MUTATE:
            handler = _registry.get(EventType.MUTATE.value)
        case EventType.NOTIFY:
            handler = _registry.get(EventType.NOTIFY.value)
        case EventType.REASON:
            handler = _registry.get(EventType.REASON.value)
        case EventType.RESPONSE:
            handler = _registry.get(EventType.RESPONSE.value)
        case str() as unknown_type:
            return DispatchResult(
                ok=False,
                event_type=unknown_type,
                message=f"No handler registered for event type '{unknown_type}'",
                errors=[{"type": "unknown_event_type", "detail": unknown_type}],
            )

    if handler is None:
        return DispatchResult(
            ok=False,
            event_type=event.type,
            message=f"Handler for '{event.type}' is registered but resolved to None",
        )

    return handler(event, env)
