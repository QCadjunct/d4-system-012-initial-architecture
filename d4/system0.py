"""
System 0 — Domain Declaration (YAML Dependency Injection).

Re-exports the environment loader and provides a single
validate_payload() function that delegates entirely to
contract.to_payload_model() + PayloadModel.model_validate().

This file is deliberately small — ~40 lines.  The models own
their own I/O; System 0 is a thin convenience layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import FQTNContract, System0Env


def load_system0(contracts_dir: str | Path) -> System0Env:
    """
    Load the System 0 environment from a directory of YAML contracts.

    Each .yaml file becomes an FQTNContract; the collection becomes
    the DI (Dependency Injection) container for the domain.
    """
    return System0Env.from_yaml_dir(Path(contracts_dir))


def validate_payload(
    contract: FQTNContract,
    raw_payload: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None, list[dict[str, Any]]]:
    """
    Validate a raw payload against an FQTN contract.

    Returns:
        (ok, validated_dict_or_None, errors_list)

    Delegates entirely to the compiled Pydantic model.
    """
    PayloadModel = contract.to_payload_model()
    try:
        validated = PayloadModel.model_validate(raw_payload)
        return True, validated.model_dump(exclude_none=True), []
    except ValidationError as exc:
        errors = [
            {
                "field": ".".join(str(loc) for loc in e["loc"]),
                "type": e["type"],
                "message": e["msg"],
            }
            for e in exc.errors()
        ]
        return False, None, errors
