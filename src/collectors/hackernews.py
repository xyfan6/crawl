"""Hacker News collector via Algolia search API."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.collectors.base import CollectedItem
from src.http.client import get_shared_client

logger = logging.getLogger(__name__)

_BASE = "https://hn.algolia.com/api/v1/search"


async def collect(
    config: dict,
    cursor: str | None,
    limit: int,
) -> tuple[list[CollectedItem], str | None]:
    """
    config keys:
      query:      str   — search query
      min_points: int   — minimum HN score
    cursor: page number as string
    """
    query = config.get("query", "autism")
    min_points = config.get("min_points", 5)
    page = int(cursor or "0")
    client = get_shared_client()

    params: dict = {
        "query": query,
        "tags": "story",
        "numericFilters": f"points>={min_points}",
        "hitsPerPage": min(limit, 100),
        "page": page,
    }

    try:
        resp = await client.get(_BASE, params=params)
        data = resp.json()
    except Exception as exc:
        logger.error("HackerNews fetch failed: %s", exc)
        return [], cursor

    hits = data.get("hits", [])
    nb_pages = data.get("nbPages", 0)

    items: list[CollectedItem] = []
    for h in hits:
        title = (h.get("title") or "").strip()
        if not title:
            continue

        story_url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}"

        published_at: str | None = None
        created = h.get("created_at_i")
        if created:
            published_at = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()

        items.append(
            CollectedItem(
                title=title,
                url=story_url,
                source="hackernews",
                external_id=h.get("objectID"),
                description=h.get("story_text") or None,
                content_body=None,
                author=h.get("author"),
                authors_json=None,
                published_at=published_at,
                rank_position=None,
                doi=None,
                journal=None,
                open_access=None,
                engagement={
                    "points": h.get("points", 0),
                    "num_comments": h.get("num_comments", 0),
                },
                raw_payload=h,
            )
        )

    next_cursor = str(page + 1) if page + 1 < nb_pages else None
    return items, next_cursor
