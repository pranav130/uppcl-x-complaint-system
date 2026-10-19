"""Unit tests for ReplyEngine and Auto-Post Guardrails.

Tests PII scrubbing, template drafting, 280-character limit checks,
and multi-tier safety checks before automated publishing.
"""

import pytest
from uppcl_x_automation.config import load_config
from uppcl_x_automation.reply_engine import ReplyEngine


@pytest.fixture
def reply_engine():
    config = load_config()
    return ReplyEngine(config)


def test_scrub_pii(reply_engine):
    text = "Consumer phone 9876543210 and account 123456789012 with email test@example.com"
    scrubbed = reply_engine.scrub_pii(text)
    assert "9876543210" not in scrubbed
    assert "[PHONE_REDACTED]" in scrubbed
    assert "123456789012" not in scrubbed
    assert "[ACC_REDACTED]" in scrubbed
    assert "test@example.com" not in scrubbed
    assert "[EMAIL_REDACTED]" in scrubbed


def test_generate_draft_supply_outage_hindi(reply_engine):
    draft = reply_engine.generate_draft(
        complaint_type="SUPPLY_OUTAGE",
        discom_handle="@PVVNLHQ",
        language="hi",
        consumer_handle="user123",
        routing_confidence="HIGH",
    )
    assert draft.is_safe is True
    assert draft.approval_status == "DRAFT_READY"
    assert "@PVVNLHQ" in draft.draft_text
    assert "बिजली आपूर्ति" in draft.draft_text
    assert len(draft.draft_text) <= 280


def test_generate_draft_missing_discom(reply_engine):
    draft = reply_engine.generate_draft(
        complaint_type="SUPPLY_OUTAGE",
        discom_handle=None,
        language="hi",
        consumer_handle="user123",
        routing_confidence="UNCERTAIN",
    )
    assert draft.is_safe is False
    assert draft.approval_status == "NEEDS_REVIEW"
    assert "No receiving DISCOM handle available" in draft.validation_errors[0]


def test_generate_draft_disallowed_handle(reply_engine):
    draft = reply_engine.generate_draft(
        complaint_type="SUPPLY_OUTAGE",
        discom_handle="@FakePowerDISCOM",
        language="hi",
        consumer_handle="user123",
        routing_confidence="HIGH",
    )
    assert draft.is_safe is False
    assert any("not in the authorized safety allowlist" in e for e in draft.validation_errors)


def test_can_auto_post_disabled_by_default(reply_engine):
    # Auto-post should be strictly blocked when auto_post_enabled=False
    reply_engine.config.auto_post_enabled = False
    draft = reply_engine.generate_draft("SUPPLY_OUTAGE", "@PVVNLHQ", "hi", "u1", routing_confidence="HIGH")
    can_post, reason = reply_engine.can_auto_post(
        draft=draft,
        original_post_id="12345",
        already_posted=False,
        today_posted_count=5,
    )
    assert can_post is False
    assert "AUTO_POST_ENABLED is false" in reason


def test_can_auto_post_emergency_stop(reply_engine):
    reply_engine.config.auto_post_enabled = True
    reply_engine.config.emergency_stop = True
    draft = reply_engine.generate_draft("SUPPLY_OUTAGE", "@PVVNLHQ", "hi", "u1", routing_confidence="HIGH")
    can_post, reason = reply_engine.can_auto_post(
        draft=draft,
        original_post_id="12345",
        already_posted=False,
        today_posted_count=5,
    )
    assert can_post is False
    assert "Emergency stop is active" in reason


def test_can_auto_post_daily_cap_exceeded(reply_engine):
    reply_engine.config.auto_post_enabled = True
    reply_engine.config.emergency_stop = False
    reply_engine.config.daily_post_cap = 50
    draft = reply_engine.generate_draft("SUPPLY_OUTAGE", "@PVVNLHQ", "hi", "u1", routing_confidence="HIGH")
    can_post, reason = reply_engine.can_auto_post(
        draft=draft,
        original_post_id="12345",
        already_posted=False,
        today_posted_count=50,
    )
    assert can_post is False
    assert "Daily posting cap reached" in reason


def test_can_auto_post_duplicate_protection(reply_engine):
    reply_engine.config.auto_post_enabled = True
    reply_engine.config.emergency_stop = False
    draft = reply_engine.generate_draft("SUPPLY_OUTAGE", "@PVVNLHQ", "hi", "u1", routing_confidence="HIGH")
    can_post, reason = reply_engine.can_auto_post(
        draft=draft,
        original_post_id="12345",
        already_posted=True,  # Already replied!
        today_posted_count=5,
    )
    assert can_post is False
    assert "already been replied to" in reason
