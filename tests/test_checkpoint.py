"""Unit tests for CheckpointStore.

Tests SQLite table schema, WAL persistence, watermark advancement,
duplicate checks, and metrics calculation using a temporary test database.
"""

from datetime import datetime, timezone
import pytest
from uppcl_x_automation.checkpoint import CheckpointStore


@pytest.fixture
def checkpoint(tmp_path):
    db_file = tmp_path / "test_uppcl.db"
    return CheckpointStore(str(db_file))


def test_checkpoint_initialization(checkpoint):
    assert checkpoint.db_path.exists()
    assert checkpoint.get_last_seen_post_id() is None


def test_save_and_is_processed(checkpoint):
    post_data = {
        "post_id": "999888777",
        "post_url": "https://x.com/user/status/999888777",
        "author_username": "consumer_test",
        "text": "Power cut in Gorakhpur",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "first_detected_at_ist": "19-10-2026 12:00:00",
        "last_processed_at_ist": "19-10-2026 12:00:00",
        "discom": "PuVVNL",
        "zone": "GORAKHPUR-1",
        "district": "GORAKHPUR",
        "complaint_type": "SUPPLY_OUTAGE",
        "picked_status": "YES",
        "routing_confidence": "HIGH",
        "draft_text": "Concerned team @PuVVNLHQ...",
        "approval_status": "DRAFT_READY",
        "reply_post_id": None,
        "reply_posted_at_utc": None,
        "sheet_row_index": None,
        "sync_status": "SYNCED",
        "error_message": None,
        "raw_json": "{}",
    }

    assert checkpoint.is_post_processed("999888777") is False
    checkpoint.save_processed_post(post_data)
    assert checkpoint.is_post_processed("999888777") is True


def test_author_history_counter(checkpoint):
    # First complaint from user
    assert checkpoint.get_author_history_count("frequent_user") == 1

    # Record complaint
    checkpoint.save_processed_post({
        "post_id": "111",
        "post_url": "url1",
        "author_username": "frequent_user",
        "text": "Complaint 1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "first_detected_at_ist": "19-10-2026 12:00:00",
        "last_processed_at_ist": "19-10-2026 12:00:00",
        "discom": "MVVNL",
        "zone": "LESA",
        "district": "LUCKNOW",
        "complaint_type": "SUPPLY_OUTAGE",
        "picked_status": "YES",
        "routing_confidence": "HIGH",
        "draft_text": "",
        "approval_status": "DRAFT_READY",
        "reply_post_id": None,
        "reply_posted_at_utc": None,
        "sheet_row_index": None,
        "sync_status": "SYNCED",
        "error_message": None,
        "raw_json": "{}",
    })

    # Next complaint should have C F = 2
    assert checkpoint.get_author_history_count("frequent_user") == 2


def test_watermark_advancement(checkpoint):
    checkpoint.update_last_seen_post_id("100")
    assert checkpoint.get_last_seen_post_id() == "100"

    checkpoint.update_last_seen_post_id("200")
    assert checkpoint.get_last_seen_post_id() == "200"

    # Lower ID should not downgrade watermark
    checkpoint.update_last_seen_post_id("150")
    assert checkpoint.get_last_seen_post_id() == "200"


def test_reply_recording_and_today_count(checkpoint):
    checkpoint.save_processed_post({
        "post_id": "333",
        "post_url": "url3",
        "author_username": "user3",
        "text": "Outage",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "first_detected_at_ist": "19-10-2026 12:00:00",
        "last_processed_at_ist": "19-10-2026 12:00:00",
        "discom": "MVVNL",
        "zone": "LESA",
        "district": "LUCKNOW",
        "complaint_type": "SUPPLY_OUTAGE",
        "picked_status": "YES",
        "routing_confidence": "HIGH",
        "draft_text": "Draft",
        "approval_status": "APPROVED",
        "reply_post_id": None,
        "reply_posted_at_utc": None,
        "sheet_row_index": None,
        "sync_status": "SYNCED",
        "error_message": None,
        "raw_json": "{}",
    })

    assert checkpoint.get_today_replies_count() == 0
    checkpoint.record_reply_published("333", "reply_999")
    assert checkpoint.get_today_replies_count() == 1


def test_audit_log_and_stats(checkpoint):
    checkpoint.log_audit("TEST_EVENT", "Test message", level="INFO")
    stats = checkpoint.get_summary_stats()
    assert isinstance(stats["total_detected"], int)
    assert isinstance(stats["discom_breakdown"], dict)
