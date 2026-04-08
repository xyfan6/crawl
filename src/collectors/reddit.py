"""Reddit JSON API collector (no OAuth — public endpoint)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.collectors.base import CollectedItem, normalize_title
from src.config import settings
from src.http.client import get_shared_client

logger = logging.getLogger(__name__)

_BASE = "https://www.reddit.com/r/{subreddit}/new.json"


async def collect(
    config: dict,
    cursor: str | None,
    limit: int,
) -> tuple[list[CollectedItem], str | None]:
    """
    config keys:
      subreddit: str
    cursor: Reddit 'after' token (e.g. 't3_abc123') or None
    """
    subreddit = config["subreddit"]
    client = get_shared_client()

    params: dict = {
        "limit": min(limit, 100),
        "raw_json": 1,
    }
    if cursor:
        params["after"] = cursor

    url = _BASE.format(subreddit=subreddit)
    try:
        resp = await client.get(
            url,
            params=params,
            headers={
                "User-Agent": settings.USER_AGENT,
                "Accept": "application/json",
            },
        )
    except Exception as exc:
        logger.error("Reddit fetch failed for r/%s: %s", subreddit, exc)
        return [], cursor

    data = resp.json()
    children = data.get("data", {}).get("children", [])
    after = data.get("data", {}).get("after")

    items: list[CollectedItem] = []
    for child in children:
        post = child.get("data", {})
        title = post.get("title", "").strip()
        if not title:
            continue

        permalink = post.get("permalink", "")
        post_url = f"https://www.reddit.com{permalink}" if permalink else post.get("url", "")

        published_at: str | None = None
        created = post.get("created_utc")
        if created:
            published_at = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()

        items.append(
            CollectedItem(
                title=title,
                url=post_url,
                source="reddit",
                external_id=post.get("name"),
                description=post.get("selftext") or None,
                content_body=None,
                author=post.get("author"),
                authors_json=None,
                published_at=published_at,
                rank_position=None,
                doi=None,
                journal=None,
                open_access=None,
                engagement={
                    "score": post.get("score", 0),
                    "upvote_ratio": post.get("upvote_ratio"),
                    "num_comments": post.get("num_comments", 0),
                },
                raw_payload=post,
            )
        )

    return items, after
