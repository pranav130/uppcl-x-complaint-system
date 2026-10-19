"""Unit tests for XClient.

Tests mock mode generation, since_id filtering, rate limit handling,
exponential backoff, and JSON response parsing.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
import requests
from uppcl_x_automation.x_client import XClient, XRateLimitError, XApiError


def test_mock_search_returns_posts():
    client = XClient(mock_mode=True)
    posts = client.search_recent(query="test query", max_results=10)
    assert len(posts) > 0
    first = posts[0]
    assert first.post_id != ""
    assert first.author_username != ""
    assert "https://x.com/" in first.post_url
    assert len(first.mentioned_accounts) > 0


def test_mock_search_since_id_filtering():
    client = XClient(mock_mode=True)
    # Get all posts
    all_posts = client.search_recent(query="test", max_results=50)
    assert len(all_posts) > 0

    # Pick middle ID
    mid_id = all_posts[len(all_posts) // 2].post_id
    filtered = client.search_recent(query="test", since_id=mid_id)
    for p in filtered:
        assert int(p.post_id) > int(mid_id)


def test_post_reply_dry_run():
    client = XClient(mock_mode=True)
    ok, reply_id, err = client.post_reply(in_reply_to_tweet_id="12345", text="Test reply", dry_run=True)
    assert ok is True
    assert reply_id is not None
    assert err is None


def test_parse_tweets_response():
    client = XClient(bearer_token="mock_token")
    mock_payload = {
        "data": [
            {
                "id": "1001",
                "author_id": "u1",
                "text": "Outage in Meerut @UPPCLLKO",
                "created_at": "2026-10-19T06:00:00.000Z",
                "entities": {
                    "mentions": [{"username": "UPPCLLKO"}]
                },
                "public_metrics": {"reply_count": 0, "retweet_count": 1}
            }
        ],
        "includes": {
            "users": [
                {"id": "u1", "username": "meerut_citizen", "name": "Citizen", "location": "Meerut"}
            ]
        }
    }

    posts = client._parse_tweets_response(mock_payload)
    assert len(posts) == 1
    p = posts[0]
    assert p.post_id == "1001"
    assert p.author_username == "meerut_citizen"
    assert p.author_location == "Meerut"
    assert "@UPPCLLKO" in p.mentioned_accounts
    assert p.post_url == "https://x.com/meerut_citizen/status/1001"


def test_rate_limit_backoff(monkeypatch):
    client = XClient(bearer_token="mock_token", mock_mode=False)

    # Mock response with 429
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {
        "x-rate-limit-remaining": "0",
        "x-rate-limit-reset": "1792392000"
    }
    mock_resp.text = "Rate limit exceeded"

    mock_get = MagicMock(return_value=mock_resp)
    monkeypatch.setattr(client.session, "get", mock_get)

    with pytest.raises(XRateLimitError):
        client.search_recent(query="test", max_retries=1)
