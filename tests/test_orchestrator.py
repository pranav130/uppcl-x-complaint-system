"""Integration tests for UPPCLOrchestrator.

Tests full end-to-end sync lifecycle, idempotency across runs,
duplicate suppression, and emergency stop behavior.
"""

import pytest
from uppcl_x_automation.config import load_config
from uppcl_x_automation.orchestrator import UPPCLOrchestrator


@pytest.fixture
def orchestrator(tmp_path):
    config = load_config()
    config.sqlite_db_path = str(tmp_path / "test_orch.db")
    config.dry_run = True
    config.auto_post_enabled = False
    return UPPCLOrchestrator(config)


def test_end_to_end_sync_cycle(orchestrator):
    summary1 = orchestrator.run_sync_cycle()
    assert summary1.posts_fetched > 0
    assert summary1.complaints_classified > 0
    assert summary1.drafts_prepared > 0
    assert summary1.rows_appended > 0
    assert summary1.replies_published == 0  # auto_post is disabled
    assert summary1.highest_post_id is not None

    # Idempotency / Duplicate test: Running a second time with watermark yields 0 new rows
    summary2 = orchestrator.run_sync_cycle()
    assert summary2.rows_appended == 0
    assert summary2.posts_fetched == 0  # Watermark correctly prevented refetching

    # Now simulate refetching the exact same posts without a watermark
    orchestrator.checkpoint.clear_watermark()
    summary3 = orchestrator.run_sync_cycle()
    assert summary3.rows_appended == 0
    assert summary3.duplicates_skipped >= summary1.rows_appended


def test_emergency_stop_halts_orchestrator(orchestrator):
    orchestrator.config.emergency_stop = True
    summary = orchestrator.run_sync_cycle()
    assert summary.posts_fetched == 0
    assert summary.rows_appended == 0
    assert any("EMERGENCY_STOP is engaged" in e for e in summary.errors)
