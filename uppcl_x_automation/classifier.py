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
        r"दुर्घटना", r"accident", r"चोरी", r"कटिया", r"katiya", r"illegal\s*connection",
        r"हादसा", r"हाईटेंशन", r"ht\s*line"
    ],
    "POLE_RELATED": [
        r"खंभा", r"खम्भा", r"\bpole\b", r"तार\s*टूट", r"toota\s*taar", r"wire\s*broken",
        r"टूटा\s*तार", r"तार\s*झूल", r"hanging\s*wire", r"pole\s*fall", r"pole\s*bent",
        r"पोल\s*टूट", r"पोल\s*गिर", r"तार\s*सड़क", r"broken\s*pole"
    ],
    "SUPPLY_OUTAGE": [
        r"लाइट\s*नहीं", r"बिजली\s*नहीं", r"light\s*nahi", r"bijli\s*nahi", r"बिजली\s*गुल",
        r"bijli\s*gul", r"power\s*cut", r"\boutage\b", r"no\s*power", r"no\s*light",
        r"no\s*electricity", r"अंधेरा", r"andhera", r"blackout", r"tripping", r"ट्रिपिंग",
        r"लोड\s*शेडिंग", r"load\s*shedding", r"power\s*failure", r"breakdown", r"light\s*chali\s*gayi",
        r"आपूर्ति\s*बाधित", r"विद्युत\s*आपूर्ति\s*ठप", r"supply\s*off", r"phase\s*missing",
        r"सिंगल\s*फेज", r"single\s*phase",
        # Flexible natural language variations
        r"बिजली\b.*?\b(नहीं|नही|गायब|गुल|ठप|कट|गई|chali|band|nahi)",
        r"लाइट\b.*?\b(नहीं|नही|गायब|गुल|ठप|कट|गई|chali|band|nahi)",
        r"बिना\s*बिजली", r"बिजली\s*(काट|कट|गुल|गायब)",
        r"light\s*(kaat|kat|cut|off|chali|gul|nahi)",
        r"supply\s*(disrupt|cut|off|fail|stop)",
        r"power\s*supply.*?(disrupt|cut|off|fail|stop)",
        r"आपूर्ति\s*(बाधित|ठप|बंद)"
    ],
    "SUPPLY_VOLTAGE": [
        r"लो\s*वोल्टेज", r"low\s*voltage", r"हाई\s*वोल्टेज", r"high\s*voltage", r"डिम\s*लाइट",
        r"dim\s*light", r"वोल्टेज\s*उतार", r"voltage\s*fluctuation", r"voltage\s*drop",
        r"motor\s*not\s*running", r"मोटर\s*नहीं\s*चल", r"कम\s*वोल्टेज", r"बल्ब\s*(तक\s*)?नहीं\s*जल"
    ],
    "BILL_RELATED": [
        r"\bbill\b", r"बिल", r"गलत\s*बिल", r"wrong\s*bill", r"भारी\s*बिल", r"extra\s*bill",
        r"high\s*bill", r"overcharge", r"भुगतान", r"payment", r"receipt", r"रसीद",
        r"smart\s*meter\s*recharge", r"surcharge", r"सरचार्ज", r"bill\s*correction",
        r"बकाया", r"arrears", r"\bots\b", r"एक\s*मुस्त\s*समाधान"
    ],
    "CONNECTION_NEW": [
        r"नया\s*कनेक्शन", r"new\s*connection", r"झटपट", r"jhatpat", r"connection\s*apply",
        r"लोड\s*वृद्धि", r"load\s*increase", r"meter\s*shifting", r"नाम\s*परिवर्तन", r"name\s*change"
    ],
    "DISSATISFIED_CONSUMER": [
        r"1912\s*पर\s*कोई\s*सुनवाई\s*नहीं", r"कोई\s*नहीं\s*सुन\s*रहा", r"lineman\s*rude",
        r"je\s*not\s*picking", r"रिश्वत", r"bribe", r"भ्रष्टाचार", r"बार\s*बार\s*शिकायत",
        r"repeated\s*complaint", r"नो\s*रेस्पॉन्स", r"no\s*response",
        # DISCOM in-progress and follow-up complaint indicators
        r"काम\s*चल\s*रहा\s*है", r"कार्य\s*प्रगति\s*पर", r"work\s*is\s*going\s*on",
        r"पूर्व\s*में\s*दर्ज\s*शिकायत", r"previously\s*lodged", r"दर्ज\s*शिकायत",
        r"शिकायत\s*संख्या", r"complaint\s*(no|number)", r"संबंधित\s*अधिकारी",
        r"समाधान\s*कर\s*दिया\s*गया\s*है", r"complaint\s*has\s*been\s*resolved",
        r"\b(PV|DV|MV|PU|KS)\d{8,}\b",
        # Follow-up dissatisfaction
        r"समाधान\s*(नहीं|नही)", r"हल\s*(नहीं|नही)",
        r"(रिक्वेस्ट|शिकायत|ticket)\s*(को\s*)?(क्लोज|बंद|close)",
        r"no\s*respon[sc]e", r"nobody\s*contacted", r"no\s*action",
        r"कोई\s*(नहीं\s*आया|सुनवाई\s*नहीं)", r"फर्जी\s*(निस्तारण|क्लोज)"
    ],
    "INFO_AND_SUGG": [
        r"जानकारी\s*चाहिए", r"information\s*needed", r"कृपया\s*बताएं", r"helpline\s*number",
        r"सुझाव", r"suggestion", r"tariff", r"रोस्टर", r"roster"
    ]
}

# Known Official DISCOM and Apex Accounts
OFFICIAL_HANDLES: Set[str] = {
    # Apex & Minister Handles
    "uppcllko", "cmofficeup", "emofficeup", "aksharmaoffice", "aksharmabharat",
    "chairmanuppcl", "mduppcl",
    # Core DISCOM HQ & Helplines
    "pvvnlhq", "1912pvvnl", "pvvnl",
    "dvvnlhq", "dvvnl_care", "1912dvvnl",
    "puvvnlhq", "puvvnl", "1912puvvnl",
    "kescohq", "skescokanpur", "1912kesco",
    "mvvnlhq", "mvvnlmd", "madhyanchalv", "1912mvvnl",
    # PuVVNL Regional & District Handles
    "puvvnlazamgarh", "puvvnlbhadohi", "puvvnlballia", "puvvnlbasti", "puvvnlchandauli",
    "puvvnldeoria", "puvvnlfatehpur", "puvvnlghazipur", "puvvnlgorakhpur", "puvvnljaunpur",
    "puvvnlkaushambi", "puvvnlkusinagar", "puvvnlmhrjganj", "puvvnlmau", "puvvnlmirzapur1",
    "puvvnlprtapgarh", "puvvnlprayagraj", "puvvnlsknagar", "puvvnlsdnagar", "puvvnlsonbhadra",
    "puvvnlvaranasi",
    # MVVNL Regional, District & Zone Handles
    "mvvnlbareilly", "mvvnlbudaun", "mvvnlpilibhit", "mvvnlsahjahapur", "edc_ambdkrnagar",
    "mvvnlamethi", "mvvnlbarabanki", "mvvnlayodhya", "mvvnlsultanpur", "mvvnlbahraich",
    "mvvnlbalrampur", "mvvnlgonda", "mvvnlshrawasti", "zoneamausi", "mvvnlcisgomti2",
    "zonegomtinagar", "mvvnllesatrans", "mvvnllakhimpur", "mvvnlhardoi", "mvvnlraebareli",
    "mvvnlsitapur", "mvvnlunnao", "gomtinagarzone", "cebareilly1",
    # DVVNL Regional & District Handles
    "dvvnlagra", "dvvnlaligarh", "dvvnlauraiya", "dvvnlbanda", "dvvnlchitrakoot",
    "dvvnletah", "dvvnletawah01", "dvvnlfarrukhaba", "dvvnlfirozabad", "dvvnlhamirpur",
    "dvvnlhathras", "dvvnljalaun2", "dvvnljhansi", "dvvnlkannauj", "dvvnlkanpurdeha",
    "dvvnlkanpurnagr", "dvvnlkasganj", "dvvnllalitpur2", "dvvnlmahoba", "dvvnlmainpuri",
    "dvvnlmathura1",
    # PVVNL Regional & District Handles
    "pvvnlamroha", "pvvnlbaghpat", "pvvnlbijnor", "pvvnlbulandshr", "pvvnlgbnagar",
    "pvvnlghaziabad", "pvvnlhapur", "pvvnlmeerut", "pvvnlmoradabad", "pvvnlmuzafarngr",
    "pvvnlrampur", "pvvnlsaharanpur", "pvvnlsambhal", "pvvnlshamli", "pvvnlnoida"
}

OFFICIAL_HANDLE_REGEX = re.compile(
    r"^(uppcl|kesco|pvvnl|dvvnl|puvvnl|mvvnl|1912|cmoffice|emoffice|aksharma|chairman|mduppcl|zone|ce|se|ee|sdohq|lesa|edc_)",
    re.IGNORECASE
)

# Text Markers Indicating an Official Department Response in a Complaint Thread
OFFICIAL_REPLY_PATTERNS: List[str] = [
    r"प्रिय\s*उपभोक्ता", r"प्रिय\s*ग्राहक", r"dear\s*consumer", r"dear\s*customer", r"dear\s*sir",
    r"काम\s*चल\s*रहा\s*है", r"कार्य\s*प्रगति\s*पर", r"work\s*is\s*going\s*on",
    r"पूर्व\s*में\s*दर्ज\s*शिकायत", r"previously\s*lodged", r"दर्ज\s*शिकायत",
    r"शिकायत\s*संख्या", r"complaint\s*(no|number)", r"संबंधित\s*अधिकारी", r"concerned\s*officer",
    r"1912\s*नम्बर\s*पर\s*संपर्क", r"toll-free\s*number\s*1912", r"टोल[- ]?फ्री\s*नंबर",
    r"contact\s*(number\s*)?1912", r"update\s*you\s*soon", r"we\s*will\s*update\s*you",
    r"status\s*of\s*the\s*complaint", r"please\s*take\s*action", r"inform\s*the\s*consumer",
    r"\b(PV|DV|MV|PU|KS)\d{8,}\b",
    r"#1912\w+", r"#dvvnlhq\w*", r"#PVVNLHQ\w*", r"#GoodGovernance", r"#upm\d+"
]

# Genuine Citizen Appreciation (Must explicitly express problem resolution or direct team praise)
GENUINE_APPRECIATION_PATTERNS: List[str] = [
    r"(समस्या|शिकायत)\s*का\s*(समाधान|निस्तारण)\s*(हो\s*गया|कर\s*दिया|हुआ)",
    r"बिजली\s*आ\s*गई\s*(है)?", r"लाइट\s*आ\s*गई\s*(है)?", r"power\s*restored", r"light\s*aa\s*gayi",
    r"काम\s*(हो|कर)\s*गया\s*(है)?", r"कार्य\s*पूर्ण\s*हो\s*गया",
    r"सप्लाई\s*चालू\s*(करने\s*के\s*लिए|हो\s*गई)",
    r"शानदार\s*(विद्युत\s*)?(आपूर्ति|सप्लाई)",
    r"(problem|complaint|issue|outage|power\s*outage)\s*(is\s*)?(solved|resolved)",
    r"resolv(ing|ed)\s*(the\s*)?(fuse|complaint|issue|outage|power\s*outage|problem)",
    r"(great|excellent|superb|fast|quick|good)\s*(work|job|resolution|service|speed)",
    r"बहुत\s*अच्छा\s*काम", r"त्वरित\s*समाधान", r"शानदार\s*कार्य"
]

# Request or Complaint Disqualifiers (A post containing these is NOT appreciation even if polite words appear)
REQUEST_OR_COMPLAINT_INDICATORS: List[str] = [
    r"अनुरोध", r"निवेदन", r"प्रार्थना", r"कृपा\s*कर", r"कृपया", r"\bplease\b", r"\bplz\b",
    r"कराएं", r"करवाएं", r"करा\s*दीजिए", r"कीजिए", r"कराओ",
    r"nahi", r"नहीं", r"fuk", r"फुंक", r"blast", r"धमाका", r"chori", r"चोरी",
    r"toot", r"टूट", r"kharab", r"खराब", r"pending", r"पेंडिंग", r"लंबित", r"बकाया",
    r"झूल", r"hanging", r"कब\s*तक", r"सुधार", r"overcharge", r"tripping",
    r"no\s*power", r"no\s*light", r"no\s*electricity", r"power\s*cut",
    r"आभारी\s*रहेंगे",
    r"update\s*you", r"work\s*is\s*going", r"previously\s*lodged", r"concerned\s*officer",
    r"status\s*of\s*the\s*complaint", r"please\s*take\s*action", r"inform\s*the\s*consumer"
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

        self._compiled_genuine_appreciation = [re.compile(p, re.IGNORECASE) for p in GENUINE_APPRECIATION_PATTERNS]
        self._compiled_request_or_complaint = [re.compile(p, re.IGNORECASE) for p in REQUEST_OR_COMPLAINT_INDICATORS]
        self._compiled_official_replies = [re.compile(p, re.IGNORECASE) for p in OFFICIAL_REPLY_PATTERNS]
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

    @staticmethod
    def is_official_account(author_username: str) -> bool:
        """Check if author username belongs to an official DISCOM or apex account."""
        clean = (author_username or "").strip().lower().lstrip("@")
        if not clean:
            return False
        if clean in OFFICIAL_HANDLES:
            return True
        if OFFICIAL_HANDLE_REGEX.match(clean):
            return True
        if clean.endswith("hq") or clean.endswith("care"):
            return True
        return False

    def is_official_reply_text(self, text: str) -> bool:
        """Check if post body contains official DISCOM reply/in-progress boilerplate."""
        return any(r.search(text) for r in self._compiled_official_replies)

    @staticmethod
    def ends_with_official_handle(text: str) -> bool:
        """Check if post or reply ends with one or more official UPPCL/DISCOM handles (even if followed by hashtags/links)."""
        if not text:
            return False
        clean = text.strip()
        # Match trailing handles after stripping trailing hashtags, URLs, and punctuation
        stripped = re.sub(r"(?:#\w+|\bhttps?://\S+|[.,!?;:\s])+$", "", clean, flags=re.IGNORECASE).strip()
        trailing_match = re.search(r"((?:@[\w]+\s*)+)$", stripped)
        if trailing_match:
            trailing_part = trailing_match.group(1)
            found_handles = re.findall(r"@([\w]+)", trailing_part)
            for h in found_handles:
                c = h.lower()
                if c in OFFICIAL_HANDLES or OFFICIAL_HANDLE_REGEX.match(c) or c.endswith("hq") or c.endswith("care"):
                    return True
        return False

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

        # Check if author is official or post contains official reply boilerplate or ends with official handles
        author_is_official = self.is_official_account(author_username)
        has_official_reply_markers = self.is_official_reply_text(text)
        ends_with_official = self.ends_with_official_handle(text)

        # 1. Genuine Citizen Appreciation Check
        # Disqualified if:
        # - Author is official handle OR post has official reply markers (e.g. DISCOM replying to a consumer)
        # - Post ends with any official handle(s) (e.g. tagging handles at end of grievance)
        # - Post contains citizen request/complaint markers (e.g. asking for OTS, reporting hanging wire with "धन्यवाद")
        if not author_is_official and not has_official_reply_markers and not ends_with_official:
            has_genuine_appreciation = any(r.search(text) for r in self._compiled_genuine_appreciation)
            has_request_or_complaint = any(r.search(text) for r in self._compiled_request_or_complaint)
            if has_genuine_appreciation and not has_request_or_complaint:
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
                    reason="Citizen expresses genuine appreciation for resolved service.",
                )

        # 2. Check for PR announcements / non-complaints (Must not be an official reply to an active complaint)
        is_pr = any(r.search(text) for r in self._pr_regex)
        if is_pr and not has_official_reply_markers and not any(r.search(text) for _, plist in self._compiled_types[:4] for r in plist):
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

        # 3. Score complaint categories
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

        # 4. If author is official or post has official reply markers but no specific keyword matched:
        # It is an official reply in a complaint thread -> default to DISSATISFIED_CONSUMER
        if author_is_official or has_official_reply_markers:
            return ClassificationResult(
                is_complaint=True,
                picked_status="YES",
                complaint_type="DISSATISFIED_CONSUMER",
                language=lang,
                shift=shift,
                head=head,
                c_f=previous_complaint_count,
                untagged_complaint=untagged,
                confidence=0.85,
                reason="Official DISCOM grievance thread reply / in-progress follow-up detected.",
            )

        # 5. Ambiguous / Unclassified: Contains mentions of apex handles but no recognized complaint keywords
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
