#!/usr/bin/env python3
"""
D⁴ System 0/1/2 — Proof of Concept Demo Runner.

Walks through the entire stack end-to-end:
  1. System 0 — Load YAML contracts (Domain Declaration via DI)
  2. System 1 — Dispatch JEV events (VALIDATE, MUTATE, LOOKUP, NOTIFY)
  3. System 2 — Agentic reasoning via bounded prompt graph stub
  4. PostgreSQL 18 — Generate DDL from contracts

Run:
    python main.py
    python main.py --pg "host=localhost dbname=d4_poc"   # optional PG
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: register all handlers before dispatch
# ---------------------------------------------------------------------------
from d4.system0 import load_system0
from d4.models import EventType, JEVEvent
from d4.system1 import dispatch, get_registry
import d4.handlers          # registers VALIDATE, LOOKUP, MUTATE, NOTIFY
import d4.system2 as sys2   # registers REASON, RESPONSE
from d4.handlers.lookup import seed_store_with_pk, get_store
from d4.handlers.notify import get_notification_log
from d4.pg.ddl import env_to_ddl
from d4.pg.persistence import try_connect


CONTRACTS_DIR = Path(__file__).resolve().parent / "contracts"

DIVIDER = "=" * 70


def banner(title: str) -> None:
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def step(label: str) -> None:
    print(f"\n--- {label} ---")


def show_result(result) -> None:
    status = "OK" if result.ok else "FAIL"
    print(f"  [{status}] {result.message}")
    if result.data:
        for k, v in result.data.items():
            print(f"    {k}: {v}")
    if result.errors:
        for e in result.errors:
            print(f"    ERROR: {e}")


def main(pg_conninfo: str | None = None) -> int:
    # ==================================================================
    # PHASE 1 — System 0: Domain Declaration
    # ==================================================================
    banner("PHASE 1 — System 0: Domain Declaration (YAML DI)")

    env = load_system0(CONTRACTS_DIR)
    print(f"  Loaded {len(env.contracts)} FQTN (Fully Qualified Table Name) contracts:")
    for fqtn, contract in sorted(env.contracts.items()):
        print(f"    • {fqtn}  (owner: {contract.owner}, PK: {contract.primary_key})")
    print(f"  Event types: {sorted(env.event_types)}")

    # ==================================================================
    # PHASE 2 — System 1: JEV Dispatch
    # ==================================================================
    banner("PHASE 2 — System 1: JEV (JSON Event Vocabulary) Dispatch")

    registry = get_registry()
    print(f"  Registered handlers: {sorted(registry.keys())}")

    # --- VALIDATE ---
    step("VALIDATE — valid student payload")
    event_v1 = JEVEvent(
        type=EventType.VALIDATE,
        fqtn="enrollment.student",
        payload={
            "student_id": "12345678",
            "last_name": "Heller",
            "first_name": "Peter",
            "email": "Peter.Heller@qc.cuny.edu",
        },
    )
    show_result(dispatch(event_v1, env))

    step("VALIDATE — invalid student payload (bad student_id)")
    event_v2 = JEVEvent(
        type=EventType.VALIDATE,
        fqtn="enrollment.student",
        payload={"student_id": "ABCD", "last_name": "Bad", "first_name": "Data", "email": "x@y.com"},
    )
    show_result(dispatch(event_v2, env))

    # --- MUTATE (create) ---
    step("MUTATE — create student record")
    event_m1 = JEVEvent(
        type=EventType.MUTATE,
        fqtn="enrollment.student",
        payload={
            "student_id": "12345678",
            "last_name": "Heller",
            "first_name": "Peter",
            "email": "Peter.Heller@qc.cuny.edu",
            "gpa": 3.9,
            "is_active": True,
        },
    )
    show_result(dispatch(event_m1, env))

    step("MUTATE — create a section")
    event_m2 = JEVEvent(
        type=EventType.MUTATE,
        fqtn="enrollment.section",
        payload={
            "section_id": "CSCI331-01",
            "course_name": "Database Systems",
            "instructor": "Peter Hartmann Heller",
            "capacity": 35,
            "enrolled_count": 28,
            "semester": "Fall2026",
        },
    )
    show_result(dispatch(event_m2, env))

    step("MUTATE — register the student for the section")
    event_m3 = JEVEvent(
        type=EventType.MUTATE,
        fqtn="enrollment.registration",
        payload={
            "registration_id": "REG-0000000001",
            "student_id": "12345678",
            "section_id": "CSCI331-01",
            "registered_at": "2026-09-01T10:00:00Z",
            "status": "enrolled",
        },
    )
    show_result(dispatch(event_m3, env))

    # --- LOOKUP ---
    step("LOOKUP — find the student by PK")
    event_l1 = JEVEvent(
        type=EventType.LOOKUP,
        fqtn="enrollment.student",
        payload={"student_id": "12345678"},
    )
    show_result(dispatch(event_l1, env))

    step("LOOKUP — find a missing student")
    event_l2 = JEVEvent(
        type=EventType.LOOKUP,
        fqtn="enrollment.student",
        payload={"student_id": "99999999"},
    )
    show_result(dispatch(event_l2, env))

    # --- NOTIFY ---
    step("NOTIFY — enrollment notification")
    event_n1 = JEVEvent(
        type=EventType.NOTIFY,
        fqtn="enrollment.registration",
        payload={"student_id": "12345678", "section_id": "CSCI331-01", "action": "enrolled"},
    )
    show_result(dispatch(event_n1, env))
    print(f"  Notification log entries: {len(get_notification_log())}")

    # ==================================================================
    # PHASE 3 — System 2: Agentic Reasoning
    # ==================================================================
    banner("PHASE 3 — System 2: Agentic Reasoning (bounded prompt graph)")

    step("REASON — ask about enrolled students")
    response = sys2.reason(
        question="Who is currently enrolled in enrollment.student?",
        fqtn="enrollment.student",
        env=env,
    )
    print(f"  Answer: {response.answer}")
    print(f"  Confidence: {response.confidence}")
    print(f"  Grounded in: {response.grounded_in}")

    step("REASON — ask about sections (has data)")
    response2 = sys2.reason(
        question="What sections are available?",
        fqtn="enrollment.section",
        env=env,
    )
    print(f"  Answer: {response2.answer}")
    print(f"  Confidence: {response2.confidence}")

    # ==================================================================
    # PHASE 4 — PostgreSQL 18 DDL Generation
    # ==================================================================
    banner("PHASE 4 — PostgreSQL 18 DDL Generation")

    ddl = env_to_ddl(env)
    print(ddl)

    # Optional: execute against a live PostgreSQL instance
    pg = try_connect(pg_conninfo)
    if pg is not None:
        step("Bootstrapping PostgreSQL schema")
        pg.bootstrap(env)
        # Persist the mutated records
        for fqtn_key, records in get_store().items():
            contract = env.get_contract(fqtn_key)
            for record in records.values():
                pg.upsert(contract, record)
        print("  Records persisted to PostgreSQL.")
        pg.close()
    else:
        print("\n  (No PostgreSQL connection — DDL shown above is ready to execute)")

    # ==================================================================
    # Summary
    # ==================================================================
    banner("SUMMARY")
    print(f"  Contracts loaded:      {len(env.contracts)}")
    print(f"  Handlers registered:   {len(registry)}")
    print(f"  Records in store:      {sum(len(v) for v in get_store().values())}")
    print(f"  Notifications emitted: {len(get_notification_log())}")
    print(f"  System 2 responses:    {len(sys2.get_response_log())}")
    print(f"  PostgreSQL connected:  {'yes' if pg and pg.is_connected else 'no'}")
    print(f"\n  D⁴ PoC (Proof of Concept) — all three layers operational. ✓\n")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="D⁴ System 0/1/2 PoC Demo")
    parser.add_argument(
        "--pg",
        metavar="CONNINFO",
        default=None,
        help="PostgreSQL connection string (optional)",
    )
    sys.exit(main(pg_conninfo=parser.parse_args().pg))
