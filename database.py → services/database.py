"""
TruthTrack — Database Service
Async SQLite layer for storing and querying fact-check results.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import aiosqlite

DB_PATH = Path(__file__).parent.parent / "truthtrack.db"

# ── Schema ────────────────────────────────────────────────────────────────────

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS checks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  REAL    NOT NULL,          -- Unix timestamp
    claim_text  TEXT    NOT NULL,
    file_name   TEXT,
    verdict     TEXT    NOT NULL,
    confidence  INTEGER NOT NULL,
    summary     TEXT,
    key_findings TEXT,                     -- JSON array
    sources      TEXT                      -- JSON array
);
"""

# ── Init ──────────────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Create tables if they don't exist. Call once at app startup."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE)
        await db.commit()


# ── Write ─────────────────────────────────────────────────────────────────────

async def save_check(
    claim_text: str,
    verdict: str,
    confidence: int,
    summary: str,
    key_findings: list[str],
    sources: list[str],
    file_name: Optional[str] = None,
) -> int:
    """Insert a completed fact-check and return its new row ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO checks
              (created_at, claim_text, file_name, verdict, confidence,
               summary, key_findings, sources)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                claim_text[:2000],          # cap stored text
                file_name,
                verdict,
                confidence,
                summary,
                json.dumps(key_findings),
                json.dumps(sources),
            ),
        )
        await db.commit()
        return cur.lastrowid


# ── Read ──────────────────────────────────────────────────────────────────────

async def get_recent_checks(limit: int = 20) -> list[dict]:
    """Return the most recent `limit` checks, newest first."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT id, created_at, claim_text, file_name, verdict, confidence, summary
            FROM checks
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_verdict_counts() -> dict[str, int]:
    """Return a mapping of verdict → count for all stored checks."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT verdict, COUNT(*) as cnt FROM checks GROUP BY verdict ORDER BY cnt DESC"
        )
        rows = await cur.fetchall()
        return {row[0]: row[1] for row in rows}


async def get_stats() -> dict:
    """Return aggregate statistics for the dashboard."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Total checks
        cur = await db.execute("SELECT COUNT(*) FROM checks")
        total = (await cur.fetchone())[0]

        # Average confidence
        cur = await db.execute("SELECT AVG(confidence) FROM checks")
        avg_conf_row = await cur.fetchone()
        avg_conf = round(avg_conf_row[0] or 0, 1)

        # Verdict breakdown
        cur = await db.execute(
            "SELECT verdict, COUNT(*) FROM checks GROUP BY verdict ORDER BY COUNT(*) DESC"
        )
        verdict_counts = {row[0]: row[1] for row in await cur.fetchall()}

        # Checks per day (last 7 days)
        cur = await db.execute(
            """
            SELECT DATE(created_at, 'unixepoch') as day, COUNT(*) as cnt
            FROM checks
            WHERE created_at >= strftime('%s', 'now', '-7 days')
            GROUP BY day
            ORDER BY day
            """
        )
        daily = [{"day": row[0], "count": row[1]} for row in await cur.fetchall()]

        return {
            "total": total,
            "avg_confidence": avg_conf,
            "verdict_counts": verdict_counts,
            "daily_checks": daily,
        }
