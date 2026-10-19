"""Durable SQLite Checkpoint and Audit Store for UPPCL Monitoring.

Ensures at-most-once processing, prevents duplicate rows, tracks daily posting caps,
and maintains an immutable chronological audit trail with WAL-mode persistence.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CheckpointStore:
    """Thread-safe, ACID-compliant local checkpoint database using SQLite."""

    def __init__(self, db_path: str = "data/uppcl_monitor.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS processed_posts (
                    post_id TEXT PRIMARY KEY,
                    post_url TEXT,
                    author_username TEXT,
                    text TEXT,
                    created_at_utc TEXT,
                    first_detected_at_ist TEXT,
                    last_processed_at_ist TEXT,
                    discom TEXT,
                    zone TEXT,
                    district TEXT,
                    complaint_type TEXT,
                    picked_status TEXT,
                    routing_confidence TEXT,
                    draft_text TEXT,
                    approval_status TEXT DEFAULT 'PENDING',
                    reply_post_id TEXT,
                    reply_posted_at_utc TEXT,
                    sheet_row_index INTEGER,
                    sync_status TEXT DEFAULT 'RECORDED',
                    error_message TEXT,
                    raw_json TEXT
                );

                CREATE TABLE IF NOT EXISTS sync_checkpoints (
                    checkpoint_key TEXT PRIMARY KEY,
                    checkpoint_value TEXT,
                    updated_at_utc TEXT
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_utc TEXT,
                    event_type TEXT,
                    level TEXT,
                    message TEXT,
                    details_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_posts_author ON processed_posts(author_username);
                CREATE INDEX IF NOT EXISTS idx_posts_approval ON processed_posts(approval_status);
                CREATE INDEX IF NOT EXISTS idx_posts_reply ON processed_posts(reply_posted_at_utc);
            """)

    def is_post_processed(self, post_id: str) -> bool:
        """Check if post_id is already in processed_posts table."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT 1 FROM processed_posts WHERE post_id = ?", (post_id,))
            return cur.fetchone() is not None

    def get_author_history_count(self, author_username: str) -> int:
        """Get total historical complaints from this author to compute C F."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM processed_posts WHERE author_username = ? AND picked_status = 'YES'",
                (author_username,)
            )
            count = cur.fetchone()[0]
            return count + 1  # 1-indexed

    def save_processed_post(self, post_data: Dict[str, Any]) -> None:
        """Insert or update post in checkpoint store."""
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO processed_posts (
                    post_id, post_url, author_username, text, created_at_utc,
                    first_detected_at_ist, last_processed_at_ist, discom, zone, district,
                    complaint_type, picked_status, routing_confidence, draft_text,
                    approval_status, reply_post_id, reply_posted_at_utc, sheet_row_index,
                    sync_status, error_message, raw_json
                ) VALUES (
                    :post_id, :post_url, :author_username, :text, :created_at_utc,
                    :first_detected_at_ist, :last_processed_at_ist, :discom, :zone, :district,
                    :complaint_type, :picked_status, :routing_confidence, :draft_text,
                    :approval_status, :reply_post_id, :reply_posted_at_utc, :sheet_row_index,
                    :sync_status, :error_message, :raw_json
                )
                ON CONFLICT(post_id) DO UPDATE SET
                    last_processed_at_ist = excluded.last_processed_at_ist,
                    approval_status = excluded.approval_status,
                    reply_post_id = COALESCE(excluded.reply_post_id, processed_posts.reply_post_id),
                    reply_posted_at_utc = COALESCE(excluded.reply_posted_at_utc, processed_posts.reply_posted_at_utc),
                    sheet_row_index = COALESCE(excluded.sheet_row_index, processed_posts.sheet_row_index),
                    sync_status = excluded.sync_status,
                    error_message = excluded.error_message
            """, post_data)

    def get_last_seen_post_id(self) -> Optional[str]:
        """Retrieve highest/latest post ID seen so far."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT checkpoint_value FROM sync_checkpoints WHERE checkpoint_key = 'last_seen_post_id'")
            row = cur.fetchone()
            return row["checkpoint_value"] if row else None

    def update_last_seen_post_id(self, post_id: str) -> None:
        """Update highest seen post ID checkpoint."""
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO sync_checkpoints (checkpoint_key, checkpoint_value, updated_at_utc)
                VALUES ('last_seen_post_id', ?, ?)
                ON CONFLICT(checkpoint_key) DO UPDATE SET
                    checkpoint_value = CASE 
                        WHEN CAST(excluded.checkpoint_value AS INTEGER) > CAST(sync_checkpoints.checkpoint_value AS INTEGER)
                        THEN excluded.checkpoint_value
                        ELSE sync_checkpoints.checkpoint_value
                    END,
                    updated_at_utc = excluded.updated_at_utc
            """, (post_id, now_utc))

    def clear_watermark(self) -> None:
        """Clear watermark checkpoint (e.g. for backfill or testing)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM sync_checkpoints WHERE checkpoint_key = 'last_seen_post_id'")

    def reset_all_for_testing(self) -> None:
        """Clear all processed posts and watermarks for clean test runs."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM processed_posts")
            conn.execute("DELETE FROM sync_checkpoints")

    def get_today_replies_count(self) -> int:
        """Count public replies posted today (UTC/IST)."""
        today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM processed_posts WHERE reply_posted_at_utc LIKE ? AND reply_post_id IS NOT NULL",
                (f"{today_date}%",)
            )
            return cur.fetchone()[0]

    def record_reply_published(self, post_id: str, reply_post_id: str) -> None:
        """Mark post as replied to with timestamp."""
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE processed_posts
                SET reply_post_id = ?, reply_posted_at_utc = ?, approval_status = 'POSTED', sync_status = 'REPLIED'
                WHERE post_id = ?
            """, (reply_post_id, now_utc, post_id))

    def log_audit(self, event_type: str, message: str, level: str = "INFO", details: Optional[Dict[str, Any]] = None) -> None:
        """Append an event to the audit log."""
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_logs (timestamp_utc, event_type, level, message, details_json)
                VALUES (?, ?, ?, ?, ?)
            """, (now_utc, event_type, level, message, json.dumps(details or {}, ensure_ascii=False)))

    def get_summary_stats(self) -> Dict[str, Any]:
        """Compute operational metrics for dashboard."""
        with self._get_connection() as conn:
            total_detected = conn.execute("SELECT COUNT(*) FROM processed_posts").fetchone()[0]
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            today_detected = conn.execute("SELECT COUNT(*) FROM processed_posts WHERE created_at_utc LIKE ?", (f"{today_str}%",)).fetchone()[0]
            replies_posted = conn.execute("SELECT COUNT(*) FROM processed_posts WHERE reply_post_id IS NOT NULL").fetchone()[0]
            needs_review = conn.execute("SELECT COUNT(*) FROM processed_posts WHERE approval_status = 'NEEDS_REVIEW'").fetchone()[0]
            pending_drafts = conn.execute("SELECT COUNT(*) FROM processed_posts WHERE approval_status = 'DRAFT_READY'").fetchone()[0]

            # Discom counts
            cur_discom = conn.execute("SELECT COALESCE(discom, 'UNASSIGNED') as d, COUNT(*) as c FROM processed_posts GROUP BY d")
            discom_counts = {row["d"]: row["c"] for row in cur_discom.fetchall()}

            return {
                "total_detected": total_detected,
                "today_detected": today_detected,
                "replies_posted": replies_posted,
                "needs_review": needs_review,
                "pending_drafts": pending_drafts,
                "discom_breakdown": discom_counts,
            }
