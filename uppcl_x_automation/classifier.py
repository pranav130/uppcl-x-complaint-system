"""Intelligent Bilingual Grievance Classifier for UPPCL.

Analyzes public posts in Hindi (Devanagari), English, and Hinglish.
Categorizes posts into official UPPCL complaint types, detects shift windows,
and filters out non-complaint announcements, PR posts, and spam.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Set


@dataclass
class ClassificationResult:
    is_complaint: bool
    picked_status: str  # 'YES', 'NO', 'APPRECIATION'
    complaint_type: str  # e.g. 'SUPPLY_OUTAGE', 'BILL_RELATED', etc.
    language: str  # 'hi', 'en', 'hi-Latn'
    shift: str  # 'MORNING', 'EVENING', 'NIGHT'
    head: str  # 'upl', 'upm', 'upc', 'ako', 'akb', 'emo'
    c_f: int  # Complaint frequency / follow-up indicator
    untagged_complaint: str  # 'Untagged' or ''
    confidence: float
    reason: str


# RegEx Rule Definitions for Complaint Types
COMPLAINT_PATTERNS: Dict[str, List[str]] = {
    "TRANSFORMER_DAMAGE": [
        r"ट्रांस[फ़ाफ]र्मर", r"ट्रांसफार्मर", r"परिवर्तक", r"\btransformer\b", r"\bdtr\b",
        r"\bblast\b", r"धमाका", r"धुआं", r"dhuan", r"फुंक\s*गया", r"fuk\s*gaya", r"जल\s*गया",
        r"transformer\s*burnt", r"oil\s*leakage", r"खराब\s*ट्रांसफार्मर", r"replace\s*transformer"
    ],
    "ACCIDENT_PRONE_TO_OCCURED": [
        r"करंट", r"करन्ट", r"\bcurrent\b", r"\belectrocution\b", r"शॉर्ट\s*सर्किट", r"short\s*circuit",
        r"आग\s*लग", r"\bfire\b", r"चिंगारी", r"sparking", r"खतरा", r"\bdanger\b",
        r"दुर्घटना", r"accident", r"चोरी", r"कटिया", r"katiya", r"illegal\s*connection"
    ],
    "POLE_RELATED": [
        r"खंभा", r"खम्भा", r"\bpole\b", r"तार\s*टूट", r"toota\s*taar", r"wire\s*broken",
        r"टूटा\s*तार", r"तार\s*झूल", r"hanging\s*wire", r"pole\s*fall", r"pole\s*bent",
        r"पोल\s*टूट", r"पोल\s*गिर", r"तार\s*सड़क"
    ],
    "SUPPLY_OUTAGE": [
        r"लाइट\s*नहीं", r"बिजली\s*नहीं", r"light\s*nahi", r"bijli\s*nahi", r"बिजली\s*गुल",
        r"bijli\s*gul", r"power\s*cut", r"\boutage\b", r"no\s*power", r"no\s*light",
        r"no\s*electricity", r"अंधेरा", r"andhera", r"blackout", r"tripping", r"ट्रिपिंग",
        r"लोड\s*शेडिंग", r"load\s*shedding", r"power\s*failure", r"breakdown", r"light\s*chali\s*gayi",
        r"आपूर्ति\s*बाधित", r"विद्युत\s*आपूर्ति\s*ठप", r"supply\s*off", r"phase\s*missing",
        r"सिंगल\s*फेज", r"single\s*phase"
    ],
    "SUPPLY_VOLTAGE": [
        r"लो\s*वोल्टेज", r"low\s*voltage", r"हाई\s*वोल्टेज", r"high\s*voltage", r"डिम\s*लाइट",
        r"dim\s*light", r"वोल्टेज\s*उतार", r"voltage\s*fluctuation", r"voltage\s*drop",
        r"motor\s*not\s*running", r"मोटर\s*नहीं\s*चल", r"कम\s*वोल्टेज"
    ],
    "BILL_RELATED": [
        r"\bbill\b", r"बिल", r"गलत\s*बिल", r"wrong\s*bill", r"भारी\s*बिल", r"extra\s*bill",
        r"high\s*bill", r"overcharge", r"भुगतान", r"payment", r"receipt", r"रसीद",
        r"smart\s*meter\s*recharge", r"surcharge", r"सरचार्ज", r"bill\s*correction",
        r"बकाया", r"arrears"
    ],
    "CONNECTION_NEW": [
        r"नया\s*कनेक्शन", r"new\s*connection", r"झटपट", r"jhatpat", r"connection\s*apply",
        r"लोड\s*वृद्धि", r"load\s*increase", r"meter\s*shifting", r"नाम\s*परिवर्तन", r"name\s*change"
    ],
    "DISSATISFIED_CONSUMER": [
        r"1912\s*पर\s*कोई\s*सुनवाई\s*नहीं", r"कोई\s*नहीं\s*सुन\s*रहा", r"lineman\s*rude",
        r"je\s*not\s*picking", r"रिश्वत", r"bribe", r"भ्रष्टाचार", r"बार\s*बार\s*शिकायत",
        r"repeated\s*complaint", r"नो\s*रेस्पॉन्स", r"no\s*response"
    ],
    "INFO_AND_SUGG": [
        r"जानकारी\s*चाहिए", r"information\s*needed", r"कृपया\s*बताएं", r"helpline\s*number",
        r"सुझाव", r"suggestion", r"tariff", r"रोस्टर", r"roster"
    ]
}

# Appreciation Patterns
APPRECIATION_PATTERNS = [
    r"धन्यवाद", r"सराहना", r"बहुत\s*अच्छा\s*काम", r"\bthank\s*you\b", r"\bthanks\b",
    r"\bkudos\b", r"grateful", r"आभार", r"great\s*work", r"problem\s*solved"
]

# Non-Complaint PR / Routine Announcement Patterns
PR_ANNOUNCEMENT_PATTERNS = [
    r"माननीय\s*मंत्री\s*जी\s*ने", r"प्रेस\s*विज्ञप्ति", r"उद्घाटन\s*किया", r"बैठक\s*की\s*अध्यक्षता",
    r"समीक्षा\s*बैठक", r"press\s*release", r"inaugurated", r"ch大事ed\s*meeting",
    r"विभागीय\s*समीक्षा", r"हार्दिक\s*शुभकामनाएं", r"बधाई\s*एवं\s*शुभकामनाएं"
]


class GrievanceClassifier:
    """Classifies grievance text into categories and extracts metadata."""

    def __init__(self):
        # Pre-compile regex for speed
        self._compiled_types: List[Tuple[str, List[re.Pattern[str]]]] = []
        for c_type, patterns in COMPLAINT_PATTERNS.items():
            compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
            self._compiled_types.append((c_type, compiled))

        self._appreciation_regex = [re.compile(p, re.IGNORECASE) for p in APPRECIATION_PATTERNS]
        self._pr_regex = [re.compile(p, re.IGNORECASE) for p in PR_ANNOUNCEMENT_PATTERNS]

    @staticmethod
    def detect_language(text: str) -> str:
        """Detect language: 'hi' (Devanagari), 'hi-Latn' (Hinglish), or 'en' (English)."""
        if not text:
            return "en"
        # Check for Devanagari Unicode range (\u0900-\u097F)
        if re.search(r"[\u0900-\u097F]", text):
            return "hi"
        # Check for common Hinglish words
        hinglish_words = {"bijli", "nahi", "rahi", "kripya", "chali", "gayi", "karo", "kijiye", "bhai", "hamare", "yahan", "hai", "me", "ko", "se"}
        tokens = set(re.findall(r"\b[a-zA-Z]+\b", text.lower()))
        if len(tokens.intersection(hinglish_words)) >= 2:
            return "hi-Latn"
        return "en"

    @staticmethod
    def get_ist_shift_and_date(utc_timestamp: Optional[datetime] = None) -> Tuple[str, str]:
        """Convert UTC timestamp to Indian Standard Time (UTC+5:30) and return (Date, Shift)."""
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        if utc_timestamp:
            if utc_timestamp.tzinfo is None:
                utc_timestamp = utc_timestamp.replace(tzinfo=timezone.utc)
            ist_time = utc_timestamp.astimezone(ist_tz)
        else:
            ist_time = datetime.now(ist_tz)

        date_str = ist_time.strftime("%d-%m-%Y")
        hour = ist_time.hour

        if 6 <= hour < 14:
            shift = "MORNING"
        elif 14 <= hour < 22:
            shift = "EVENING"
        else:
            shift = "NIGHT"

        return date_str, shift

    @staticmethod
    def resolve_head(mentioned_accounts: List[str], text: str = "") -> str:
        """Resolve Head abbreviation based on monitored account tagged."""
        clean_handles = [h.lower().lstrip("@") for h in mentioned_accounts]
        combined = f"{' '.join(clean_handles)} {text.lower()}"

        if "mduppcl" in combined:
            return "upm"
        if "chairmanuppcl" in combined:
            return "upc"
        if "aksharmaoffice" in combined:
            return "ako"
        if "aksharmabharat" in combined:
            return "akb"
        if "emofficeup" in combined:
            return "emo"
        if "uppcllko" in combined:
            return "upl"
        return "upl"

    def classify(
        self,
        text: str,
        mentioned_accounts: Optional[List[str]] = None,
        author_username: str = "",
        created_at_utc: Optional[datetime] = None,
        previous_complaint_count: int = 1,
    ) -> ClassificationResult:
        """Classify a post into UPPCL complaint taxonomy."""
        mentioned = mentioned_accounts or []
        lang = self.detect_language(text)
        _, shift = self.get_ist_shift_and_date(created_at_utc)
        head = self.resolve_head(mentioned, text)

        # Check if author didn't tag any apex accounts in post body
        untagged = ""
        has_monitored_tag = any(
            h.lower().lstrip("@") in ["uppcllko", "emofficeup", "aksharmaoffice", "aksharmabharat", "chairmanuppcl", "mduppcl"]
            for h in mentioned
        )
        if not has_monitored_tag:
            untagged = "Untagged"

        # Check for appreciation
        is_appreciation = any(r.search(text) for r in self._appreciation_regex)
        has_negative_indicator = bool(re.search(r"(nahi|नहीं|fuk|फुंक|blast|धमाका|chori|चोरी|toot|टूट|kharab|खराब|pending|बकाया)", text, re.IGNORECASE))
        has_resolution_indicator = bool(re.search(r"(resolv|solved|समाधान|निस्तारण|great work|kudos|बहुत\s*अच्छा)", text, re.IGNORECASE))
        if is_appreciation and (not has_negative_indicator or has_resolution_indicator):
            return ClassificationResult(
                is_complaint=False,
                picked_status="APPRECIATION",
                complaint_type="",
                language=lang,
                shift=shift,
                head=head,
                c_f=previous_complaint_count,
                untagged_complaint=untagged,
                confidence=0.95,
                reason="Consumer expresses appreciation / gratitude.",
            )

        # Check for PR announcements / non-complaints
        is_pr = any(r.search(text) for r in self._pr_regex)
        if is_pr and not any(r.search(text) for _, plist in self._compiled_types[:4] for r in plist):
            return ClassificationResult(
                is_complaint=False,
                picked_status="NO",
                complaint_type="",
                language=lang,
                shift=shift,
                head=head,
                c_f=previous_complaint_count,
                untagged_complaint=untagged,
                confidence=0.90,
                reason="Identified as promotional news, press release, or routine meeting announcement.",
            )

        # Score complaint categories
        matched_types: List[Tuple[str, int]] = []
        for c_type, patterns in self._compiled_types:
            matches = sum(1 for p in patterns if p.search(text))
            if matches > 0:
                matched_types.append((c_type, matches))

        if matched_types:
            # Sort by highest match count, then priority order in list
            matched_types.sort(key=lambda x: x[1], reverse=True)
            chosen_type = matched_types[0][0]
            confidence = min(0.99, 0.70 + (0.10 * matched_types[0][1]))
            return ClassificationResult(
                is_complaint=True,
                picked_status="YES",
                complaint_type=chosen_type,
                language=lang,
                shift=shift,
                head=head,
                c_f=previous_complaint_count,
                untagged_complaint=untagged,
                confidence=confidence,
                reason=f"Matched {matched_types[0][1]} pattern(s) for {chosen_type}.",
            )

        # Ambiguous / Unclassified: Contains mentions of apex handles but no recognized complaint keywords
        return ClassificationResult(
            is_complaint=True,  # Retain for human review instead of silently dropping
            picked_status="YES",
            complaint_type="INFO_AND_SUGG",  # Default fallback category
            language=lang,
            shift=shift,
            head=head,
            c_f=previous_complaint_count,
            untagged_complaint=untagged,
            confidence=0.50,
            reason="Grievance intent detected from monitored handle tag, but specific keyword not matched. Flagged for review.",
        )
