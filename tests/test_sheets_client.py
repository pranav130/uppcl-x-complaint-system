"""Unit tests for GoogleSheetsManager.

Tests row serialization, column alignment, duplicate identifier extraction,
and offline dry-run appending.
"""

import pytest
from uppcl_x_automation.sheets_client import GoogleSheetsManager, FULL_HEADERS, EXISTING_HEADERS


@pytest.fixture
def sheets_manager():
    return GoogleSheetsManager(
        spreadsheet_id="12smJ_xw3sRWPcCzDsh_hC44ac2NlpO9I_wDnXF-wFXU",
        tab_name="Twitter Complaint List",
        service_account_file=None,  # Offline / dry-run mode
        dry_run=True,
    )


def test_serialize_row_structure(sheets_manager):
    record = {
        "date": "19-10-2026",
        "link_shift": "MORNING",
        "reply_shift": "MORNING",
        "c_f": 1,
        "link_url": "https://x.com/user/status/12345",
        "twitter_id": "user",
        "head": "upm",
        "untagged_complaint": "",
        "picked_status": "YES",
        "complaint_type": "SUPPLY_OUTAGE",
        "discom": "MVVNL",
        "zone": "LESA",
        "district": "LUCKNOW",
        "remark": "Verified match",
        "post_id": "12345",
        "post_text": "Bijli nahi aa rahi",
        "created_at_utc": "2026-10-19T06:00:00Z",
        "detected_at_ist": "19-10-2026 11:30:00",
        "language": "hi-Latn",
        "routing_confidence": "HIGH",
        "reply_draft": "Draft text",
        "approval_status": "DRAFT_READY",
        "reply_post_id": "",
        "reply_post_url": "",
        "reply_posted_at": "",
        "processing_status": "CLASSIFIED",
        "last_error": "",
    }

    serialized = sheets_manager.serialize_row(record)
    assert len(serialized) == len(FULL_HEADERS)
    assert serialized[0] == "19-10-2026"  # DATE
    assert serialized[1] == "MORNING"     # Link Shift
    assert serialized[4] == "https://x.com/user/status/12345"  # LINK URL
    assert serialized[5] == "user"        # Twitter Id
    assert serialized[6] == "upm"         # Head
    assert serialized[8] == "YES"         # Picked Status
    assert serialized[9] == "SUPPLY_OUTAGE"  # Complaint Type
    assert serialized[10] == "MVVNL"      # DISCOM
    assert serialized[11] == "LESA"       # Zone
    assert serialized[12] == "LUCKNOW"    # District
    assert serialized[14] == "Forwarded to Discom"  # Status
    assert serialized[19] == "12345"      # Post ID (Col T)


def test_append_rows_dry_run(sheets_manager):
    rows = [
        {"date": "19-10-2026", "link_url": "https://x.com/u/status/1", "post_id": "1"},
        {"date": "19-10-2026", "link_url": "https://x.com/u/status/2", "post_id": "2"},
    ]
    appended, err = sheets_manager.append_rows(rows)
    assert appended == 2
    assert err is None
