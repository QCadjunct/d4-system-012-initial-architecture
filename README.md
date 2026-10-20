# D⁴ System 0/1/2 — Proof of Concept

A complete end-to-end implementation of the D⁴ (Domain-Driven Database Design) three-layer runtime stack, using the enrollment domain as the reference case.

## Architecture

| Layer | Role | Implementation |
|-------|------|----------------|
| **System 0** | Domain Declaration | YAML contracts → Pydantic v2 `create_model()` |
| **System 1** | Event Reaction | JEV (JSON Event Vocabulary) dispatch via `@event_handler` decorator + `match/case` on `EventType(StrEnum)` |
| **System 2** | Agentic Reasoning | `MessagePromptEnvelope` / `MessageResponseEnvelope` riding the JEV bus |

## FQTN Contracts (enrollment domain)

- `enrollment.student` — student records (PK: `student_id`)
- `enrollment.section` — course sections (PK: `section_id`)
- `enrollment.registration` — enrollment records (PK: `registration_id`)

## Quick Start (uv)

This project uses [Astral's uv](https://docs.astral.sh/uv/) for dependency management and script running.

```bash
# Sync dependencies (creates .venv automatically)
uv sync

# Run the end-to-end demo
uv run demo

# Run with PostgreSQL 18 (optional)
uv run demo-pg

# Run BDD (Behavior-Driven Development) tests — 37 scenarios
uv run test

# Generate DDL (Data Definition Language) to stdout
uv run ddl

# Or run any file directly
uv run python main.py
```

### Without uv (pip fallback)

```bash
pip install pydantic pyyaml
python main.py
pip install pytest
python -m pytest tests/ -v
```

## Project Structure

```
d4_poc/
├── contracts/          # YAML FQTN contracts (System 0 DI container)
├── d4/
│   ├── models.py       # Pydantic v2 backbone (normative)
│   ├── system0.py      # Domain Declaration loader
│   ├── system1.py      # JEV dispatch (match/case interpreter)
│   ├── system2.py      # Agentic reasoning bridge
│   ├── handlers/       # Event handlers (validate, lookup, mutate, notify)
│   └── pg/             # PostgreSQL 18 DDL generation + persistence
├── tests/              # BDD verification tests (37 scenarios)
├── main.py             # End-to-end demo runner
└── pyproject.toml
```

## Key Design Patterns

- **EventType as StrEnum** — forces dotted-name comparison in `match/case` (Tihomir Manushev's interpreter pattern)
- **@event_handler decorator** — registry pattern; adding a handler = adding a module, not editing a chain
- **YAML is normative; Python is informative** — the contract is the source of truth, not the code
- **BDD assertions on DispatchResult** — every test checks `ok`, `event_type`, `message`, `data`, `errors`

## Author

Peter Heller — Queens College, CUNY
Mind Over Metadata LLC

## Status

Proof of Concept — teaching and demonstration use.
D⁴ methodology is Peter Heller's original, unregistered intellectual property.
