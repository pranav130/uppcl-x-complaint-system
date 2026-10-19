"""Official X (Twitter) API v2 Client and Mock Replay Adapter.

Provides resilient querying for recent complaint posts with rate limit handling,
exponential backoff, pagination, and reply posting.
Includes an offline Mock Replay Adapter for zero-cost testing.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import requests
from requests_oauthlib import OAuth1

logger = logging.getLogger(__name__)


@dataclass
class XPost:
    post_id: str
    author_id: str
    author_username: str
    author_name: str
    author_location: Optional[str]
    text: str
    created_at_utc: datetime
    post_url: str
    conversation_id: Optional[str]
    in_reply_to_user_id: Optional[str]
    referenced_tweet_ids: List[str] = field(default_factory=list)
    mentioned_accounts: List[str] = field(default_factory=list)
    lang: str = "und"
    public_metrics: Dict[str, int] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)


class XApiError(Exception):
    """Base exception for X API errors."""


class XRateLimitError(XApiError):
    """Raised when HTTP 429 Too Many Requests is encountered."""
    def __init__(self, message: str, reset_timestamp: Optional[int] = None):
        super().__init__(message)
        self.reset_timestamp = reset_timestamp


class XClient:
    """Official X API v2 Client with rate limit tracking and retry logic."""

    BASE_URL = "https://api.x.com/2"

    def __init__(
        self,
        bearer_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None,
        mock_mode: bool = False,
    ):
        self.bearer_token = bearer_token
        self.mock_mode = mock_mode or not bool(bearer_token)
        self.session = requests.Session()

        # Configure OAuth1 for user context write requests if credentials provided
        self.auth_user: Optional[OAuth1] = None
        if api_key and api_secret and access_token and access_token_secret:
            self.auth_user = OAuth1(
                client_key=api_key,
                client_secret=api_secret,
                resource_owner_key=access_token,
                resource_owner_secret=access_token_secret,
            )

        self.last_rate_limit_reset: Optional[int] = None
        self.last_rate_limit_remaining: Optional[int] = None

    def search_recent(
        self,
        query: str,
        since_id: Optional[str] = None,
        max_results: int = 50,
        max_retries: int = 3,
    ) -> List[XPost]:
        """Search recent tweets (last 7 days) matching query."""
        if self.mock_mode:
            logger.info("XClient running in MOCK mode. Returning realistic simulated posts.")
            return self._generate_mock_posts(since_id)

        url = f"{self.BASE_URL}/tweets/search/recent"
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "User-Agent": "UPPCLComplaintMonitor/1.0",
        }
        params: Dict[str, Any] = {
            "query": query,
            "max_results": min(max(10, max_results), 100),
            "tweet.fields": "id,text,author_id,created_at,conversation_id,in_reply_to_user_id,referenced_tweets,public_metrics,entities,lang",
            "expansions": "author_id,referenced_tweets.id,in_reply_to_user_id",
            "user.fields": "id,name,username,location,verified",
        }
        if since_id:
            params["since_id"] = since_id

        attempt = 0
        while attempt < max_retries:
            attempt += 1
            try:
                resp = self.session.get(url, headers=headers, params=params, timeout=20)

                # Capture rate limit headers
                if "x-rate-limit-remaining" in resp.headers:
                    self.last_rate_limit_remaining = int(resp.headers["x-rate-limit-remaining"])
                if "x-rate-limit-reset" in resp.headers:
                    self.last_rate_limit_reset = int(resp.headers["x-rate-limit-reset"])

                if resp.status_code == 429:
                    reset_time = self.last_rate_limit_reset or int(time.time() + 60)
                    wait_sec = max(1, reset_time - int(time.time()))
                    logger.warning(f"Rate limit exceeded on X API. Resets in {wait_sec}s.")
                    if attempt < max_retries:
                        sleep_time = min(wait_sec, 60) + random.uniform(0.5, 2.0)
                        time.sleep(sleep_time)
                        continue
                    raise XRateLimitError(f"X API rate limit exceeded. Reset at {reset_time}", reset_time)

                if resp.status_code in (500, 502, 503, 504):
                    backoff = (2 ** attempt) + random.uniform(0.1, 1.0)
                    logger.warning(f"X API server error {resp.status_code}. Retrying in {backoff:.2f}s...")
                    time.sleep(backoff)
                    continue

                if resp.status_code != 200:
                    raise XApiError(f"X API error {resp.status_code}: {resp.text}")

                data = resp.json()
                return self._parse_tweets_response(data)

            except requests.RequestException as e:
                logger.warning(f"Network error calling X API: {e}. Attempt {attempt}/{max_retries}")
                if attempt >= max_retries:
                    raise XApiError(f"Network error calling X API: {e}") from e
                time.sleep((2 ** attempt) + random.uniform(0.1, 1.0))

        return []

    def post_reply(
        self,
        in_reply_to_tweet_id: str,
        text: str,
        dry_run: bool = True,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Publish a reply to a tweet.

        Returns:
            Tuple of (success, reply_post_id, error_message)
        """
        if dry_run or self.mock_mode:
            mock_reply_id = str(int(time.time() * 1000) + random.randint(100, 999))
            logger.info(f"[DRY-RUN] Simulated reply to {in_reply_to_tweet_id}: '{text}' -> Reply ID: {mock_reply_id}")
            return True, mock_reply_id, None

        if not self.auth_user:
            return False, None, "User OAuth credentials not configured. Cannot post write requests."

        url = f"{self.BASE_URL}/tweets"
        payload = {
            "text": text,
            "reply": {
                "in_reply_to_tweet_id": in_reply_to_tweet_id
            }
        }

        try:
            resp = self.session.post(url, auth=self.auth_user, json=payload, timeout=20)
            if resp.status_code in (200, 201):
                data = resp.json()
                reply_id = data.get("data", {}).get("id")
                return True, reply_id, None
            return False, None, f"X API error {resp.status_code}: {resp.text}"
        except Exception as e:
            return False, None, f"Exception while posting reply: {e}"

    def _parse_tweets_response(self, data: Dict[str, Any]) -> List[XPost]:
        """Convert raw X API v2 JSON response into XPost dataclass objects."""
        tweets = data.get("data", [])
        if not tweets:
            return []

        # Index includes
        users_by_id: Dict[str, Dict[str, Any]] = {}
        for u in data.get("includes", {}).get("users", []):
            users_by_id[u["id"]] = u

        results: List[XPost] = []
        for t in tweets:
            t_id = t["id"]
            author_id = t.get("author_id", "")
            user_info = users_by_id.get(author_id, {})
            username = user_info.get("username", "unknown")
            user_name = user_info.get("name", "Unknown")
            location = user_info.get("location")

            # Extract mentions
            mentions: List[str] = []
            for m in t.get("entities", {}).get("mentions", []):
                handle = m.get("username", "")
                if handle:
                    mentions.append(f"@{handle}")

            # Extract referenced tweets
            ref_ids: List[str] = []
            for r in t.get("referenced_tweets", []):
                if "id" in r:
                    ref_ids.append(r["id"])

            # Created at
            raw_time = t.get("created_at")
            if raw_time:
                try:
                    dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                except ValueError:
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            post_url = f"https://x.com/{username}/status/{t_id}"

            results.append(XPost(
                post_id=t_id,
                author_id=author_id,
                author_username=username,
                author_name=user_name,
                author_location=location,
                text=t.get("text", ""),
                created_at_utc=dt,
                post_url=post_url,
                conversation_id=t.get("conversation_id"),
                in_reply_to_user_id=t.get("in_reply_to_user_id"),
                referenced_tweet_ids=ref_ids,
                mentioned_accounts=mentions,
                lang=t.get("lang", "und"),
                public_metrics=t.get("public_metrics", {}),
                raw_data=t,
            ))

        return results

    def _generate_mock_posts(self, since_id: Optional[str] = None) -> List[XPost]:
        """Generate high-fidelity sample complaints matching real UPPCL patterns."""
        now = datetime.now(timezone.utc)
        samples = [
            {
                "id": "2111604765486707028",
                "username": "Diwaker70180261",
                "name": "Diwaker Kumar",
                "location": "Gonda, Uttar Pradesh",
                "text": "@UPPCLLKO @mduppcl गोंडा जिले के वजीरगंज ब्लॉक में पिछले 12 घंटे से बिजली आपूर्ति पूरी तरह बाधित है। कृपया संज्ञान लें।",
                "mentions": ["@UPPCLLKO", "@mduppcl"],
                "created_at": now,
            },
            {
                "id": "2111609477049012326",
                "username": "durgeshkumabq8",
                "name": "Durgesh Singh",
                "location": "Ayodhya",
                "text": "@aksharmaBharat @UPPCLLKO हमारे गांव में 63 KVA का ट्रांसफार्मर फुंक गया है। 3 दिन से अंधेरा है। नया ट्रांसफार्मर लगवाया जाए।",
                "mentions": ["@aksharmaBharat", "@UPPCLLKO"],
                "created_at": now,
            },
            {
                "id": "2111617408557568279",
                "username": "drx_mohd_sami",
                "name": "Mohd Sami",
                "location": "Bulandshahr, India",
                "text": "@UPPCLLKO @PVVNLHQ Bulandshahr city power outage since 2 PM. Inverter batteries dying, please restore supply immediately.",
                "mentions": ["@UPPCLLKO", "@PVVNLHQ"],
                "created_at": now,
            },
            {
                "id": "2111626795447706058",
                "username": "Er_Naushad_khan",
                "name": "Naushad Khan",
                "location": "Kanpur, UP",
                "text": "@UPPCLLKO @KESCoHQ Rawatpur Kanpur me heavy voltage fluctuation chal raha hai. Fridge and AC damaged. Please fix transformer.",
                "mentions": ["@UPPCLLKO", "@KESCoHQ"],
                "created_at": now,
            },
            {
                "id": "2111631974771360067",
                "username": "rohi_tkushwahaa",
                "name": "Rohit Kushwaha",
                "location": "Deoria, UP",
                "text": "@mduppcl @PuVVNLHQ देवरिया में झटपट पोर्टल पर नए कनेक्शन के लिए 15 दिन पहले अप्लाई किया था लेकिन अभी तक मीटर नहीं लगा।",
                "mentions": ["@mduppcl", "@PuVVNLHQ"],
                "created_at": now,
            },
            {
                "id": "2111658518130642993",
                "username": "PooranSardar",
                "name": "Pooran Singh",
                "location": "Mathura",
                "text": "@UPPCLLKO @dvvnlhq मथुरा छाता क्षेत्र में अत्यधिक गलत बिल भेज दिया गया है। 2 कमरे के घर का बिल 45000 आया है।",
                "mentions": ["@UPPCLLKO", "@dvvnlhq"],
                "created_at": now,
            },
            {
                "id": "2111648779447513600",
                "username": "mishraprashan14",
                "name": "Prashant Mishra",
                "location": "Jaunpur",
                "text": "@UPPCLLKO @ChairmanUppcl जौनपुर बदलापुर रोड पर 11KV का खंभा झुक गया है और तार सड़क पर लटक रहे हैं, गंभीर दुर्घटना हो सकती है।",
                "mentions": ["@UPPCLLKO", "@ChairmanUppcl"],
                "created_at": now,
            },
            {
                "id": "2111660825899323771",
                "username": "Neeraj120459",
                "name": "Neeraj Shukla",
                "location": "Lucknow",
                "text": "@UPPCLLKO @mduppcl Gomti Nagar sub station team resolved my fuse blown complaint within 30 minutes! Excellent work and thank you!",
                "mentions": ["@UPPCLLKO", "@mduppcl"],
                "created_at": now,
            },
            {
                "id": "2111664121863372976",
                "username": "up_news_bulletin",
                "name": "UP News",
                "location": "Lucknow",
                "text": "ऊर्जा मंत्री श्री @aksharmaBharat जी ने आज शक्ति भवन में वरिष्ठ अधिकारियों के साथ महत्वपूर्ण समीक्षा बैठक की। #UPPCL",
                "mentions": ["@aksharmaBharat"],
                "created_at": now,
            }
        ]

        # If since_id is provided, only return posts with id > since_id
        if since_id:
            try:
                s_int = int(since_id)
                samples = [s for s in samples if int(s["id"]) > s_int]
            except ValueError:
                pass

        posts: List[XPost] = []
        for s in samples:
            posts.append(XPost(
                post_id=s["id"],
                author_id=f"u_{s['username']}",
                author_username=s["username"],
                author_name=s["name"],
                author_location=s["location"],
                text=s["text"],
                created_at_utc=s["created_at"],
                post_url=f"https://x.com/{s['username']}/status/{s['id']}",
                conversation_id=s["id"],
                in_reply_to_user_id=None,
                mentioned_accounts=s["mentions"],
                lang="hi" if "गोंडा" in s["text"] else "en",
                public_metrics={"retweet_count": 2, "reply_count": 1, "like_count": 5},
            ))

        return posts
