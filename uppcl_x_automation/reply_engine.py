"""Safe Reply Drafting and Automated Publishing Engine for UPPCL.

Handles template-based drafting in Hindi/English, scrubs PII, enforces character
limits, and implements multi-layer safety guardrails before publishing replies on X.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uppcl_x_automation.config import AppConfig


@dataclass
class ReplyDraftResult:
    draft_text: str
    target_discom_handle: str
    is_safe: bool
    approval_status: str  # 'DRAFT_READY', 'NEEDS_REVIEW', 'APPROVED', 'POSTED', 'REJECTED'
    validation_errors: List[str]


@dataclass
class PublishResult:
    success: bool
    reply_post_id: Optional[str]
    reply_post_url: Optional[str]
    posted_at_utc: Optional[datetime]
    error_message: Optional[str]
    dry_run: bool


# PII Regex Patterns to redact from public replies
PHONE_PATTERN = re.compile(r"\b[6-9]\d{9}\b")
ACCOUNT_PATTERN = re.compile(r"\b\d{10,12}\b")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


class ReplyEngine:
    """Generates official complaint forwarding drafts and executes guarded posting."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.templates = config.reply_templates
        self.allowed_handles = set(config.allowed_discom_handles)

    @staticmethod
    def scrub_pii(text: str) -> str:
        """Remove mobile numbers, electricity account IDs, and emails."""
        cleaned = PHONE_PATTERN.sub("[PHONE_REDACTED]", text)
        cleaned = ACCOUNT_PATTERN.sub("[ACC_REDACTED]", cleaned)
        cleaned = EMAIL_PATTERN.sub("[EMAIL_REDACTED]", cleaned)
        return cleaned

    def generate_draft(
        self,
        complaint_type: str,
        discom_handle: Optional[str],
        language: str = "hi",
        consumer_handle: str = "",
        post_text: str = "",
        routing_confidence: str = "HIGH",
    ) -> ReplyDraftResult:
        """Generate a compliant, safe reply draft directed to the receiving DISCOM."""
        errors: List[str] = []

        # Validate DISCOM handle
        if not discom_handle:
            return ReplyDraftResult(
                draft_text="",
                target_discom_handle="",
                is_safe=False,
                approval_status="NEEDS_REVIEW",
                validation_errors=["No receiving DISCOM handle available."],
            )

        if discom_handle not in self.allowed_handles:
            errors.append(f"Target handle {discom_handle} is not in the authorized safety allowlist.")

        if routing_confidence in ("LOW", "UNCERTAIN"):
            errors.append(f"Routing confidence is {routing_confidence}; requires manual human verification.")

        # Select template
        c_templates = self.templates.get(complaint_type, self.templates.get("DEFAULT", {}))
        lang_key = "hi" if language.startswith("hi") else "en"
        raw_template = c_templates.get(lang_key) or c_templates.get("hi") or "Concerned team {discom_handle}, kindly look into this consumer grievance and take appropriate action."

        # Format template
        draft = raw_template.format(discom_handle=discom_handle)

        # Prepend consumer mention if not already replying in-thread
        # When posting in-thread via X API, consumer is automatically notified
        # But ensure character limit is strictly observed (280 characters for standard X)
        draft = self.scrub_pii(draft)

        if len(draft) > 280:
            errors.append(f"Draft exceeds 280 characters limit (length={len(draft)}).")

        is_safe = len(errors) == 0
        approval_status = "DRAFT_READY" if is_safe else "NEEDS_REVIEW"

        return ReplyDraftResult(
            draft_text=draft,
            target_discom_handle=discom_handle,
            is_safe=is_safe,
            approval_status=approval_status,
            validation_errors=errors,
        )

    def can_auto_post(
        self,
        draft: ReplyDraftResult,
        original_post_id: str,
        already_posted: bool,
        today_posted_count: int,
    ) -> Tuple[bool, Optional[str]]:
        """Validate all safety guardrails before allowing a public reply to be published."""
        # Guardrail 1: Global Emergency Stop
        if self.config.emergency_stop:
            return False, "Emergency stop is active. All automated posting is locked."

        # Guardrail 2: Master Auto Post Switch
        if not self.config.auto_post_enabled:
            return False, "AUTO_POST_ENABLED is false. Posting requires explicit activation."

        # Guardrail 3: Safe draft validation
        if not draft.is_safe:
            return False, f"Draft is not certified safe: {'; '.join(draft.validation_errors)}"

        # Guardrail 4: Duplicate posting protection
        if already_posted:
            return False, f"Post ID {original_post_id} has already been replied to."

        # Guardrail 5: Daily cap enforcement
        if today_posted_count >= self.config.daily_post_cap:
            return False, f"Daily posting cap reached ({today_posted_count}/{self.config.daily_post_cap})."

        # Guardrail 6: Target handle in allowlist
        if draft.target_discom_handle not in self.allowed_handles:
            return False, f"Target handle {draft.target_discom_handle} not in allowed handles."

        # Guardrail 7: Post ID presence
        if not original_post_id:
            return False, "Original post ID is missing or empty."

        return True, None
