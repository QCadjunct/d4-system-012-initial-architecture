"""
D⁴ core models — the Pydantic v2 backbone.

Every model owns its own I/O:
  FQTNContract  — from_yaml / to_yaml / to_payload_model
  JEVEvent      — from_validated_payload / model_dump
  DispatchResult — returned by every handler
  MessagePromptEnvelope  — to_jev
  MessageResponseEnvelope — to_jev / from_jev

No standalone utility functions know about field shapes.
The contract is the source of truth, not the code.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, create_model


# ---------------------------------------------------------------------------
# EventType — the StrEnum that forces dotted-name comparison in match/case.
# Bare names capture; dotted names compare.  Tihomir's interpreter pattern.
# ---------------------------------------------------------------------------

class EventType(StrEnum):
    """JEV (JSON Event Vocabulary) event types recognized by the D⁴ stack."""
    VALIDATE = "validate"
    LOOKUP   = "lookup"
    MUTATE   = "mutate"
    NOTIFY   = "notify"
    REASON   = "reason"      # System 2 prompt
    RESPONSE = "response"    # System 2 answer


# ---------------------------------------------------------------------------
# FieldDeclaration — one field inside an FQTN (Fully Qualified Table Name) contract.
# ---------------------------------------------------------------------------

class FieldDeclaration(BaseModel):
    """A single field declaration within an FQTN contract."""
    required: bool = False
    rule: Optional[str] = None
    type: str = "string"     # string | number | integer | boolean


# ---------------------------------------------------------------------------
# FQTNContract — the normative layer.  YAML is the DI container.
# ---------------------------------------------------------------------------

class FQTNContract(BaseModel):
    """
    A Fully Qualified Table Name (FQTN) contract.

    Declares a domain concept: its fields, types, required flags,
    validation rules, primary key, and the events it participates in.
    The YAML file IS the Dependency Injection (DI) container —
    the runtime reads it, not code.
    """
    fqtn: str = Field(..., pattern=r"^[a-z_]+\.[a-z_]+$")
    owner: str
    fields: dict[str, FieldDeclaration]
    primary_key: str
    events: list[str]

    # --- Read path ---
    @classmethod
    def from_yaml(cls, path: Path) -> "FQTNContract":
        """Load a contract from a YAML file.  Pydantic validates structure at load time."""
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return cls.model_validate(raw)

    # --- Write path ---
    def to_yaml(self, directory: Path) -> Path:
        """Serialize to clean YAML.  Filename derived from FQTN."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{self.fqtn}.yaml"
        path = directory / filename
        data = self.model_dump()
        # Convert FieldDeclaration dicts back to clean YAML
        fields_clean = {}
        for fname, fdecl in data["fields"].items():
            entry: dict[str, Any] = {}
            if fdecl["required"]:
                entry["required"] = True
            if fdecl["rule"]:
                entry["rule"] = fdecl["rule"]
            if fdecl["type"] != "string":
                entry["type"] = fdecl["type"]
            fields_clean[fname] = entry if entry else {"required": False}
        data["fields"] = fields_clean
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        return path

    # --- Compilation: YAML → Pydantic model ---
    def to_payload_model(self) -> type[BaseModel]:
        """
        Compile YAML field declarations into a dynamic Pydantic v2 model
        via create_model().  The translation rules:

          required: true   → mandatory field (no default)
          required: false  → Optional[type], default=None
          rule: "^\\d{8}$" → Field(pattern=...)
          type: number     → float annotation
          type: integer    → int annotation
          type: boolean    → bool annotation
          type: string     → str annotation (default)
        """
        type_map = {
            "string":  str,
            "number":  float,
            "integer": int,
            "boolean": bool,
        }

        field_definitions: dict[str, Any] = {}

        for fname, fdecl in self.fields.items():
            py_type = type_map.get(fdecl.type, str)
            kwargs: dict[str, Any] = {}

            if fdecl.rule:
                kwargs["pattern"] = fdecl.rule

            if fdecl.required:
                field_definitions[fname] = (py_type, Field(**kwargs))
            else:
                field_definitions[fname] = (
                    Optional[py_type],
                    Field(default=None, **kwargs),
                )

        model_name = self.fqtn.replace(".", "_").title().replace("_", "")
        return create_model(model_name, **field_definitions)

    @property
    def schema_name(self) -> str:
        """Extract the schema portion of the FQTN (left of the dot)."""
        return self.fqtn.split(".")[0]

    @property
    def table_name(self) -> str:
        """Extract the table portion of the FQTN (right of the dot)."""
        return self.fqtn.split(".")[1]


# ---------------------------------------------------------------------------
# System0Env — the loaded environment (all contracts in a directory).
# ---------------------------------------------------------------------------

class System0Env(BaseModel):
    """
    System 0 environment — all FQTN contracts loaded from a directory.
    The DI (Dependency Injection) container for the entire domain.
    """
    contracts: dict[str, FQTNContract] = Field(default_factory=dict)
    event_types: set[str] = Field(default_factory=set)

    @classmethod
    def from_yaml_dir(cls, contracts_dir: Path) -> "System0Env":
        """Load every .yaml contract in a directory."""
        contracts_dir = Path(contracts_dir)
        contracts: dict[str, FQTNContract] = {}
        event_types: set[str] = set()

        for yaml_file in sorted(contracts_dir.glob("*.yaml")):
            contract = FQTNContract.from_yaml(yaml_file)
            contracts[contract.fqtn] = contract
            event_types.update(contract.events)

        return cls(contracts=contracts, event_types=event_types)

    def get_contract(self, fqtn: str) -> FQTNContract:
        """Look up a contract by its FQTN.  Raises KeyError if missing."""
        if fqtn not in self.contracts:
            raise KeyError(f"No contract for FQTN '{fqtn}'")
        return self.contracts[fqtn]


# ---------------------------------------------------------------------------
# JEVEvent — the event that travels the System 1 bus.
# ---------------------------------------------------------------------------

class JEVEvent(BaseModel):
    """
    A JSON Event Vocabulary (JEV) event.

    Carries type, FQTN, validated payload, source, and correlation_id
    through the System 1 dispatch bus.
    """
    type: str
    fqtn: str
    payload: dict[str, Any]
    source: str = "d4_poc"
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def from_validated_payload(
        cls,
        event_type: EventType | str,
        fqtn: str,
        raw_payload: dict[str, Any],
        contract: FQTNContract,
        source: str = "d4_poc",
    ) -> "JEVEvent":
        """
        Validate raw_payload through the compiled Pydantic model,
        then wrap the clean payload in a JEV event.

        Raises ValidationError on bad payload.
        """
        PayloadModel = contract.to_payload_model()
        validated = PayloadModel.model_validate(raw_payload)
        return cls(
            type=str(event_type),
            fqtn=fqtn,
            payload=validated.model_dump(exclude_none=True),
            source=source,
        )


# ---------------------------------------------------------------------------
# DispatchResult — returned by every handler.
# ---------------------------------------------------------------------------

class DispatchResult(BaseModel):
    """
    The result of dispatching a JEV event through System 1.

    Every handler returns one.  BDD assertions check its fields directly:
      ok, event_type, message, data, errors.
    """
    ok: bool
    event_type: str
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# System 2 Envelopes — agentic reasoning rides the JEV bus.
# ---------------------------------------------------------------------------

class MessagePromptEnvelope(BaseModel):
    """
    Wraps a question that requires judgment (System 2).

    Serializes via to_jev() into a JEV event with type="reason",
    dispatched through System 1 like any other event.
    """
    fqtn: str
    question: str
    context: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    def to_jev(self, source: str = "d4_poc") -> JEVEvent:
        """Produce a JEV 'reason' event from this prompt envelope."""
        return JEVEvent(
            type=EventType.REASON,
            fqtn=self.fqtn,
            payload={
                "fqtn": self.fqtn,
                "question": self.question,
                "context": self.context,
            },
            source=source,
            correlation_id=self.correlation_id,
        )


class MessageResponseEnvelope(BaseModel):
    """
    Wraps the answer to a System 2 question.

    Round-trips through JEV: to_jev() serializes, from_jev() deserializes.
    """
    fqtn: str
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    grounded_in: list[str] = Field(default_factory=list)
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    def to_jev(self, source: str = "d4_poc") -> JEVEvent:
        """Produce a JEV 'response' event from this response envelope."""
        return JEVEvent(
            type=EventType.RESPONSE,
            fqtn=self.fqtn,
            payload={
                "fqtn": self.fqtn,
                "answer": self.answer,
                "confidence": self.confidence,
                "grounded_in": self.grounded_in,
            },
            source=source,
            correlation_id=self.correlation_id,
        )

    @classmethod
    def from_jev(cls, event: JEVEvent) -> "MessageResponseEnvelope":
        """Deserialize a JEV 'response' event back into an envelope."""
        return cls(
            fqtn=event.fqtn,
            answer=event.payload["answer"],
            confidence=event.payload["confidence"],
            grounded_in=event.payload.get("grounded_in", []),
            correlation_id=event.correlation_id,
        )
