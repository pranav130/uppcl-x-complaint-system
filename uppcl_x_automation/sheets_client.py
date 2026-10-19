"""Google Sheets API Client with Safe Schema Alignment for UPPCL.

Preserves existing spreadsheet structure (Columns A through S), reads existing
historical rows to prevent duplicates, and safely appends automation metadata in
Columns T through AF. Supports Service Account, OAuth2, and Offline CSV fallback.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import requests

logger = logging.getLogger(__name__)

# Expected Header layout for 'Twitter Complaint List'
EXISTING_HEADERS = [
    "DATE", "Link Shift", "Reply Shift", "C F", " LINK URL", "Twitter Id",
    "Head", "Untagged Complaint", "Picked Status", "Complaint Type", "DISCOM",
    "Zone", "District", "Remark", "Status", "REPLY_WITHIN_30_MIN_BY_Laqshya Media",
    "REPLY_WITHIN_60_MIN_BY_DISCOM", "COMPLAINT_NO", "STS"
]

AUTOMATION_HEADERS = [
    "Post ID", "Post Text", "Post Created At (UTC)", "First Detected At (IST)",
    "Language", "Routing Confidence", "Suggested Reply Draft", "Reply Approval Status",
    "Reply Post ID", "Reply Post URL", "Reply Posted At", "Processing Status", "Last Error"
]

FULL_HEADERS = EXISTING_HEADERS + AUTOMATION_HEADERS


@dataclass
class SheetRecord:
    row_number: int
    date: str
    link_shift: str
    reply_shift: str
    c_f: str
    link_url: str
    twitter_id: str
    head: str
    untagged_complaint: str
    picked_status: str
    complaint_type: str
    discom: str
    zone: str
    district: str
    remark: str
    status: str
    reply_within_30_min: str
    reply_within_60_min: str
    complaint_no: str
    sts: str
    post_id: str
    post_text: str
    created_at_utc: str
    detected_at_ist: str
    language: str
    routing_confidence: str
    reply_draft: str
    approval_status: str
    reply_post_id: str
    reply_post_url: str
    reply_posted_at: str
    processing_status: str
    last_error: str


class GoogleSheetsManager:
    """Manages reading and writing to the UPPCL complaint Google Spreadsheet."""

    def __init__(
        self,
        spreadsheet_id: str = "12smJ_xw3sRWPcCzDsh_hC44ac2NlpO9I_wDnXF-wFXU",
        tab_name: str = "Twitter Complaint List",
        service_account_file: Optional[str] = None,
        dry_run: bool = True,
    ):
        self.spreadsheet_id = spreadsheet_id
        self.tab_name = tab_name
        self.service_account_file = service_account_file
        self.dry_run = dry_run
        self.client = None
        self.sheet = None
        self._is_authorized = False

        self._init_client()

    def _init_client(self) -> None:
        """Attempt to authenticate with Google Sheets API via gspread."""
        if not self.service_account_file:
            logger.info("No service account file specified. Google Sheets running in offline/dry-run mode.")
            return

        sa_path = Path(self.service_account_file)
        if not sa_path.exists():
            logger.warning(f"Service account file not found at {sa_path}. Running in offline/dry-run mode.")
            return

        try:
            import gspread
            self.client = gspread.service_account(filename=str(sa_path))
            spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            self.sheet = spreadsheet.worksheet(self.tab_name)
            self._is_authorized = True
            logger.info(f"Successfully authenticated to Google Sheets: '{spreadsheet.title}' -> Tab: '{self.tab_name}'")
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Sheets API: {e}. Falling back to dry-run mode.")
            self._is_authorized = False

    @property
    def is_authorized(self) -> bool:
        return self._is_authorized

    def fetch_existing_post_identifiers(self) -> Tuple[Set[str], Set[str]]:
        """Fetch all existing Post IDs and URLs from the spreadsheet to prevent duplicates.

        Returns:
            Tuple of (set_of_post_ids, set_of_urls)
        """
        post_ids: Set[str] = set()
        post_urls: Set[str] = set()

        if self._is_authorized and self.sheet:
            try:
                records = self.sheet.get_all_values()
                if len(records) > 9:  # Row 9 is header, data starts at row 10
                    for row in records[9:]:
                        # Column E (index 4) is ' LINK URL'
                        if len(row) > 4 and row[4]:
                            url = row[4].strip()
                            post_urls.add(url)
                            # Extract tweet id from URL: status/123456789
                            m = re.search(r"status/(\d+)", url)
                            if m:
                                post_ids.add(m.group(1))
                        # Column T (index 19) is 'Post ID' if populated
                        if len(row) > 19 and row[19]:
                            post_ids.add(row[19].strip())
                return post_ids, post_urls
            except Exception as e:
                logger.warning(f"Error reading existing rows via API: {e}. Trying public CSV export.")

        # Fallback to public CSV export
        try:
            export_url = f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/export?format=csv&gid=283417465"
            resp = requests.get(export_url, timeout=15)
            if resp.status_code == 200:
                reader = csv.reader(io.StringIO(resp.text))
                rows = list(reader)
                if len(rows) > 9:
                    for row in rows[9:]:
                        if len(row) > 4 and row[4]:
                            url = row[4].strip()
                            post_urls.add(url)
                            m = re.search(r"status/(\d+)", url)
                            if m:
                                post_ids.add(m.group(1))
                        if len(row) > 19 and row[19]:
                            post_ids.add(row[19].strip())
                logger.info(f"Loaded {len(post_ids)} existing post IDs from public CSV export.")
        except Exception as e:
            logger.error(f"Failed to fetch existing post identifiers: {e}")

        return post_ids, post_urls

    def serialize_row(self, data: Dict[str, Any]) -> List[Any]:
        """Convert a complaint record dictionary into an exact row vector aligned with headers."""
        status_val = "Forwarded to Discom" if data.get("discom") else "Reply to Consumer"
        if data.get("picked_status") == "APPRECIATION":
            status_val = ""

        # Default columns A through S
        row = [
            data.get("date", ""),
            data.get("link_shift", ""),
            data.get("reply_shift", ""),
            str(data.get("c_f", "1")),
            data.get("link_url", ""),
            data.get("twitter_id", ""),
            data.get("head", ""),
            data.get("untagged_complaint", ""),
            data.get("picked_status", "YES"),
            data.get("complaint_type", ""),
            data.get("discom", "") or "",
            data.get("zone", "") or "",
            data.get("district", "") or "",
            data.get("remark", ""),
            status_val,
            data.get("reply_within_30_min", "YES" if data.get("picked_status") == "YES" else ""),
            data.get("reply_within_60_min", ""),
            data.get("complaint_no", ""),
            data.get("sts", ""),
            # Columns T through AF (Automation Extension)
            data.get("post_id", ""),
            data.get("post_text", ""),
            data.get("created_at_utc", ""),
            data.get("detected_at_ist", ""),
            data.get("language", ""),
            data.get("routing_confidence", ""),
            data.get("reply_draft", ""),
            data.get("approval_status", "PENDING"),
            data.get("reply_post_id", ""),
            data.get("reply_post_url", ""),
            data.get("reply_posted_at", ""),
            data.get("processing_status", "NEW"),
            data.get("last_error", ""),
        ]
        return row

    def append_rows(self, rows_data: List[Dict[str, Any]]) -> Tuple[int, Optional[str]]:
        """Append new rows to the spreadsheet with duplicate prevention."""
        if not rows_data:
            return 0, None

        serialized_rows = [self.serialize_row(d) for d in rows_data]

        if self.dry_run or not self._is_authorized:
            logger.info(f"[DRY-RUN / OFFLINE] Successfully prepared {len(serialized_rows)} rows for insertion into '{self.tab_name}'.")
            return len(serialized_rows), None

        try:
            # Use gspread batch append
            self.sheet.append_rows(serialized_rows, value_input_option="USER_ENTERED")
            logger.info(f"Successfully appended {len(serialized_rows)} rows into Google Sheet.")
            return len(serialized_rows), None
        except Exception as e:
            err_msg = f"Failed to append rows to Google Sheets: {e}"
            logger.error(err_msg)
            return 0, err_msg
