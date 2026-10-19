"""UPPCL Complaint Monitoring Orchestrator.

Ties together X search, NLP classification, DISCOM routing, safe reply drafting,
Google Sheets persistence, SQLite checkpointing, and audit logging into an
atomic, idempotent pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from uppcl_x_automation.config import AppConfig
from uppcl_x_automation.classifier import GrievanceClassifier
from uppcl_x_automation.router import DiscomRouter
from uppcl_x_automation.reply_engine import ReplyEngine
from uppcl_x_automation.x_client import XClient, XPost
from uppcl_x_automation.checkpoint import CheckpointStore
from uppcl_x_automation.sheets_client import GoogleSheetsManager

logger = logging.getLogger(__name__)


@dataclass
class SyncSummary:
    started_at_utc: datetime
    completed_at_utc: datetime
    posts_fetched: int
    duplicates_skipped: int
    complaints_classified: int
    appreciation_count: int
    non_complaints_skipped: int
    drafts_prepared: int
    replies_published: int
    rows_appended: int
    highest_post_id: Optional[str]
    errors: List[str] = field(default_factory=list)


class UPPCLOrchestrator:
    """Master workflow runner for UPPCL grievance automation."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.classifier = GrievanceClassifier()
        self.router = DiscomRouter(config)
        self.reply_engine = ReplyEngine(config)
        self.checkpoint = CheckpointStore(config.sqlite_db_path)
        self.sheets = GoogleSheetsManager(
            spreadsheet_id=config.google_spreadsheet_id,
            tab_name=config.google_sheet_tab_name,
            service_account_file=config.google_service_account_file,
            dry_run=config.dry_run,
        )
        self.x_client = XClient(
            bearer_token=config.x_bearer_token,
            api_key=config.x_api_key,
            api_secret=config.x_api_secret,
            access_token=config.x_access_token,
            access_token_secret=config.x_access_token_secret,
            mock_mode=not bool(config.x_bearer_token),
        )

    def build_search_query(self) -> str:
        """Construct the search query covering all 6 monitored accounts and direct replies."""
        # 6 Apex handles
        handles = [acc.handle for acc in self.config.monitored_accounts]
        mentions_part = " OR ".join(handles)
        replies_part = " OR ".join([f"to:{h.lstrip('@')}" for h in handles])
        # Exclude retweets to focus on original complaints and quotes/replies
        return f"({mentions_part} OR {replies_part}) -is:retweet"

    def run_sync_cycle(self) -> SyncSummary:
        """Execute one complete synchronization cycle."""
        start_time = datetime.now(timezone.utc)
        logger.info(f"Starting UPPCL synchronization cycle at {start_time.isoformat()} (Dry-run: {self.config.dry_run})")

        errors: List[str] = []
        highest_id: Optional[str] = None
        posts_fetched = 0
        duplicates_skipped = 0
        complaints_classified = 0
        appreciation_count = 0
        non_complaints = 0
        drafts_prepared = 0
        replies_published = 0
        rows_to_append: List[Dict[str, Any]] = []

        # Check emergency stop
        if self.config.emergency_stop:
            msg = "EMERGENCY_STOP is engaged. Sync cycle aborted."
            logger.warning(msg)
            self.checkpoint.log_audit("SYNC_ABORTED", msg, level="WARNING")
            return SyncSummary(
                started_at_utc=start_time,
                completed_at_utc=datetime.now(timezone.utc),
                posts_fetched=0,
                duplicates_skipped=0,
                complaints_classified=0,
                appreciation_count=0,
                non_complaints_skipped=0,
                drafts_prepared=0,
                replies_published=0,
                rows_appended=0,
                highest_post_id=None,
                errors=[msg],
            )

        # 1. Fetch checkpoints & existing identifiers
        last_seen_id = self.checkpoint.get_last_seen_post_id()
        existing_sheet_ids, existing_sheet_urls = self.sheets.fetch_existing_post_identifiers()

        # 2. Query X for recent posts
        query = self.build_search_query()
        try:
            posts: List[XPost] = self.x_client.search_recent(query=query, since_id=last_seen_id, max_results=50)
            posts_fetched = len(posts)
            logger.info(f"Fetched {posts_fetched} post(s) from X search.")
        except Exception as e:
            err_msg = f"Failed to fetch posts from X API: {e}"
            logger.error(err_msg)
            errors.append(err_msg)
            self.checkpoint.log_audit("X_SEARCH_FAILED", err_msg, level="ERROR")
            posts = []

        # 3. Process each post
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(ist_tz).strftime("%d-%m-%Y %H:%M:%S")

        for post in posts:
            p_id = post.post_id

            # Update highest watermark
            if highest_id is None or int(p_id) > int(highest_id):
                highest_id = p_id

            # Deduplication checks
            if self.checkpoint.is_post_processed(p_id) or p_id in existing_sheet_ids or post.post_url in existing_sheet_urls:
                duplicates_skipped += 1
                logger.debug(f"Skipping duplicate post ID {p_id} ({post.post_url})")
                continue

            # Historical count for C F (Complaint Frequency)
            cf_count = self.checkpoint.get_author_history_count(post.author_username)

            # NLP Classification
            c_result = self.classifier.classify(
                text=post.text,
                mentioned_accounts=post.mentioned_accounts,
                author_username=post.author_username,
                created_at_utc=post.created_at_utc,
                previous_complaint_count=cf_count,
            )

            # DISCOM & District Routing
            r_result = self.router.route(
                text=post.text,
                mentioned_handles=post.mentioned_accounts,
                author_location=post.author_location,
            )

            # Draft Generation
            draft_result = self.reply_engine.generate_draft(
                complaint_type=c_result.complaint_type,
                discom_handle=r_result.discom_handle,
                language=c_result.language,
                consumer_handle=post.author_username,
                post_text=post.text,
                routing_confidence=r_result.confidence,
            )

            if c_result.picked_status == "YES":
                complaints_classified += 1
            elif c_result.picked_status == "APPRECIATION":
                appreciation_count += 1
            else:
                non_complaints += 1

            if draft_result.is_safe:
                drafts_prepared += 1

            # Auto-post check (Guarded Phase 2)
            reply_post_id = None
            reply_post_url = None
            reply_posted_at = None
            today_replies = self.checkpoint.get_today_replies_count()
            can_post, reason = self.reply_engine.can_auto_post(
                draft=draft_result,
                original_post_id=p_id,
                already_posted=False,
                today_posted_count=today_replies,
            )

            if can_post and not self.config.dry_run:
                ok, rep_id, post_err = self.x_client.post_reply(
                    in_reply_to_tweet_id=p_id,
                    text=draft_result.draft_text,
                    dry_run=False,
                )
                if ok and rep_id:
                    replies_published += 1
                    reply_post_id = rep_id
                    reply_post_url = f"https://x.com/UPPCLLKO/status/{rep_id}"
                    reply_posted_at = datetime.now(timezone.utc).isoformat()
                    draft_result.approval_status = "POSTED"
                    self.checkpoint.record_reply_published(p_id, rep_id)
                else:
                    errors.append(f"Failed to publish reply for {p_id}: {post_err}")

            # Date and shift in IST
            date_str, link_shift = self.classifier.get_ist_shift_and_date(post.created_at_utc)

            # Row data structure
            row_dict: Dict[str, Any] = {
                "date": date_str,
                "link_shift": link_shift,
                "reply_shift": link_shift,
                "c_f": cf_count,
                "link_url": post.post_url,
                "twitter_id": post.author_username,
                "head": c_result.head,
                "untagged_complaint": c_result.untagged_complaint,
                "picked_status": c_result.picked_status,
                "complaint_type": c_result.complaint_type,
                "discom": r_result.discom or "",
                "zone": r_result.zone or "",
                "district": r_result.district or "",
                "remark": r_result.reasoning,
                "reply_within_30_min": "YES" if c_result.picked_status == "YES" else "",
                "reply_within_60_min": "",
                "complaint_no": "",
                "sts": "",
                "post_id": p_id,
                "post_text": post.text,
                "created_at_utc": post.created_at_utc.isoformat(),
                "detected_at_ist": now_ist,
                "language": c_result.language,
                "routing_confidence": r_result.confidence,
                "reply_draft": draft_result.draft_text,
                "approval_status": draft_result.approval_status,
                "reply_post_id": reply_post_id or "",
                "reply_post_url": reply_post_url or "",
                "reply_posted_at": reply_posted_at or "",
                "processing_status": "CLASSIFIED",
                "last_error": "; ".join(draft_result.validation_errors),
            }

            # Persist to local SQLite checkpoint
            self.checkpoint.save_processed_post({
                "post_id": p_id,
                "post_url": post.post_url,
                "author_username": post.author_username,
                "text": post.text,
                "created_at_utc": post.created_at_utc.isoformat(),
                "first_detected_at_ist": now_ist,
                "last_processed_at_ist": now_ist,
                "discom": r_result.discom,
                "zone": r_result.zone,
                "district": r_result.district,
                "complaint_type": c_result.complaint_type,
                "picked_status": c_result.picked_status,
                "routing_confidence": r_result.confidence,
                "draft_text": draft_result.draft_text,
                "approval_status": draft_result.approval_status,
                "reply_post_id": reply_post_id,
                "reply_posted_at_utc": reply_posted_at,
                "sheet_row_index": None,
                "sync_status": "SYNCED",
                "error_message": "; ".join(draft_result.validation_errors) or None,
                "raw_json": str(post.raw_data),
            })

            rows_to_append.append(row_dict)

        # 4. Batch append new rows into Google Sheets
        rows_appended, sheet_err = self.sheets.append_rows(rows_to_append)
        if sheet_err:
            errors.append(sheet_err)

        # 5. Advance watermark checkpoint
        if highest_id:
            self.checkpoint.update_last_seen_post_id(highest_id)

        # 6. Audit logging
        end_time = datetime.now(timezone.utc)
        duration_sec = (end_time - start_time).total_seconds()
        self.checkpoint.log_audit(
            event_type="SYNC_COMPLETED",
            message=f"Cycle finished in {duration_sec:.2f}s. Fetched: {posts_fetched}, New: {len(rows_to_append)}, Skipped: {duplicates_skipped}, Appended: {rows_appended}.",
            level="INFO" if not errors else "WARNING",
            details={
                "posts_fetched": posts_fetched,
                "duplicates_skipped": duplicates_skipped,
                "rows_appended": rows_appended,
                "errors": errors,
            }
        )

        return SyncSummary(
            started_at_utc=start_time,
            completed_at_utc=end_time,
            posts_fetched=posts_fetched,
            duplicates_skipped=duplicates_skipped,
            complaints_classified=complaints_classified,
            appreciation_count=appreciation_count,
            non_complaints_skipped=non_complaints,
            drafts_prepared=drafts_prepared,
            replies_published=replies_published,
            rows_appended=rows_appended,
            highest_post_id=highest_id,
            errors=errors,
        )
