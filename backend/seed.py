#!/usr/bin/env python3
"""Prepare a database for use.

    python seed.py            # verify the curriculum and report what is stored
    python seed.py --demo     # add a few assessments so the UI has something to show
    python seed.py --reset    # wipe all knowledge state and history

The curriculum itself is NOT seeded into the database. Layer 1 is static and user-independent,
so it is served from `curriculum_graph.json` and held in memory — the database holds only what
is genuinely per-user: knowledge state and session history. That is why adding concepts to the
curriculum never requires a data migration; a new node is simply cold until it is assessed.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from knowledgeos.assessment import AssessmentService
from knowledgeos.config import settings
from knowledgeos.curriculum import DEFAULT_CURRICULUM_PATH, JsonCurriculumRepository
from knowledgeos.state import (
    PostgresKnowledgeStateRepository,
    PostgresSessionHistoryRepository,
    StateOverlay,
)

#: A plausible starting point: strong on foundations, thinner further out. Enough to make
#: propagation, decay and the frontier visible in the UI without pretending to be real evidence.
DEMO_SESSIONS = [
    ("prob-axioms", 0.92, 0.88, 0.80, 40),
    ("prob-conditional", 0.88, 0.82, 0.74, 35),
    ("prob-bayes", 0.80, 0.70, 0.58, 30),
    ("linalg-vectors", 0.90, 0.85, 0.78, 28),
    ("linalg-matrix-multiplication", 0.82, 0.72, 0.60, 21),
    ("opt-derivatives", 0.86, 0.78, 0.68, 14),
    ("opt-gradients", 0.70, 0.58, 0.45, 10),
    ("dsa-big-o", 0.75, 0.65, 0.55, 7),
    ("beh-star-method", 0.65, 0.55, 0.50, 3),
]


def engine():
    try:
        # connect_timeout matters: without it a stopped Docker Desktop leaves the script
        # hanging on a dead socket instead of reporting the obvious problem.
        created = sa.create_engine(
            settings.database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
        )
        with created.connect() as connection:
            connection.execute(sa.text("select 1"))
        return created
    except Exception as exc:
        sys.exit(
            f"ERROR: cannot reach Postgres ({type(exc).__name__}: {exc})\n"
            "  Start it with `docker compose up -d` from the repo root,\n"
            "  then create the tables with `alembic upgrade head`."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="add sample assessments")
    parser.add_argument("--reset", action="store_true", help="delete all state and history")
    args = parser.parse_args()

    curriculum = JsonCurriculumRepository(DEFAULT_CURRICULUM_PATH).get()
    print(
        f"curriculum: {len(curriculum)} nodes, {len(curriculum.edges)} edges, "
        f"{len(curriculum.sections)} sections, {len(curriculum.roles)} roles  [validated]"
    )

    db = engine()
    states = PostgresKnowledgeStateRepository(db)
    history = PostgresSessionHistoryRepository(db)

    if args.reset:
        states.clear()
        print("reset: all knowledge state and session history deleted")

    if args.demo:
        overlay = StateOverlay(curriculum, states)
        service = AssessmentService(curriculum, overlay, history)
        now = datetime.now(UTC)
        added = 0

        for node_id, recall, depth, transfer, days_ago in DEMO_SESSIONS:
            if node_id not in curriculum:
                print(f"  skipped {node_id} (not in curriculum)")
                continue
            when = now - timedelta(days=days_ago)
            schema_a = service.generate(node_id, now=when)
            service.ingest(
                {
                    "schema": "knowledgeos.assessment.output",
                    "schema_version": 1,
                    "session_id": str(schema_a.session_id),
                    "node_id": node_id,
                    "completed_at": when.isoformat(),
                    "observations": {
                        "recall": recall,
                        "depth": depth,
                        "transfer": transfer,
                    },
                    "response_time_rating": 0.75,
                    "llm_confidence": 0.8,
                    "gaps_identified": [],
                    "prerequisite_flags": [],
                    "recommended_next_concepts": [],
                    "evidence_summary": "seeded demo session",
                },
                # ingest at "now" so retention reflects the age of each session
                now=now,
            )
            added += 1
        print(f"demo: {added} sessions recorded")

    stored = states.all()
    assessed = [s for s in stored if s.session_count > 0]
    print(
        f"stored: {len(stored)} state rows, {len(assessed)} assessed, "
        f"{len(history.all())} sessions"
    )
    if assessed:
        snapshot = AssessmentService(
            curriculum, StateOverlay(curriculum, states), history
        ).recompute(now=datetime.now(UTC))
        health = snapshot.health
        print(f"health: {health.score:.1f}/100, frontier {health.frontier_size} nodes")
        for role in curriculum.roles:
            readiness = snapshot.readiness[role.role_id]
            print(
                f"  {role.name:24s} {readiness.readiness:6.1%}"
                f"   held back by {readiness.bottleneck_node_id}"
            )
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
