"""
Postgres access for the `testing` schema (test-sweep subjects and results).

Connects directly via DATABASE_URL (a Supabase session-pooler connection
string) rather than through Supabase's REST API, since `testing` isn't
exposed to PostgREST -- only `public` is.

DATABASE_URL is required for any of this to work; there is no CSV fallback
for reading subjects anymore; testing.test_subjects is the source of truth.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Loaded here rather than relying on sequence_runner's load_dotenv() call --
# that runs at import time too, and which module gets imported first isn't
# something this module should have to depend on.
load_dotenv(os.path.join(os.path.dirname(__file__), ".env.local"))

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def require_configured() -> None:
    """Exit with a clear message if DATABASE_URL isn't set, rather than
    failing deep inside a query with a confusing error."""
    if not DATABASE_URL:
        sys.exit(
            "DATABASE_URL is not set. Add it to .env.local -- "
            "see Vanyshr Production project -> Connect -> Session pooler."
        )


def _connect():
    return psycopg2.connect(DATABASE_URL)


def fetch_subjects(group: str) -> List[Dict[str, Any]]:
    """Test subjects tagged with `group` in test_group, ordered by id."""
    with _connect() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, first_name, last_name, city, state_id "
            "FROM testing.test_subjects "
            "WHERE %s = ANY(test_group) "
            "ORDER BY id",
            (group,),
        )
        return [dict(row) for row in cur.fetchall()]


def start_run(git_ref: str, notes: str = "") -> int:
    """Insert a scrape_runs row, return its id (the FK value other tables use)."""
    # Seconds, not just minutes -- back-to-back batches (run_summary_test.py
    # --offset in sequence) can easily start within the same minute and
    # collide on run_id's unique constraint otherwise.
    run_id = f"summary.{datetime.now().strftime('%m.%d.%H.%M.%S')}"
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO testing.scrape_runs (run_id, git_ref, notes) "
            "VALUES (%s, %s, %s) RETURNING id",
            (run_id, git_ref, notes),
        )
        return cur.fetchone()[0]


def finish_run(run_pk: int) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE testing.scrape_runs SET finished_at = now() WHERE id = %s",
            (run_pk,),
        )


def insert_summary_results(run_pk: int, subject_id: str, rows: List[Dict[str, Any]]) -> None:
    """
    Each row: target, status, response_time_ms, and optionally full_name,
    address, age, profile_url, phone, email, aliases, relatives,
    previous_addresses, notes, raw (a JSON-able dict).
    """
    if not rows:
        return

    values = [
        (
            run_pk,
            subject_id,
            r["target"],
            r.get("full_name"),
            r.get("address"),
            r.get("age"),
            r.get("profile_url"),
            r.get("phone"),
            r.get("email"),
            r.get("aliases"),
            r.get("relatives"),
            r.get("previous_addresses"),
            r.get("response_time_ms"),
            r["status"],
            r.get("notes"),
            psycopg2.extras.Json(r["raw"]) if r.get("raw") is not None else None,
        )
        for r in rows
    ]

    with _connect() as conn, conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO testing.summary_results "
            "(run_id, subject_id, target, full_name, address, age, "
            "profile_url, phone, email, aliases, relatives, previous_addresses, "
            "response_time_ms, status, notes, raw) VALUES %s",
            values,
        )
