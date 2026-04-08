"""NewsAPI.org collector."""
from __future__ import annotations

import logging

from src.collectors.base import CollectedItem
from src.config import settings
from src.http.client import get_shared_client

logger = logging.getLogger(__name__)

_BASE = "https://newsapi.org/v2/everything"


async def collect(
    config: dict,
    cursor: str | None,
    limit: int,
) -> tuple[list[CollectedItem], str | None]:
    """
    config keys:
      query: str
    cursor: page number as string
    """
    if not settings.NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY not set — skipping NewsAPI collector")
        return [], cursor

    query = config.get("query", 'autism OR autistic OR "autism spectrum"')
    page = int(cursor or "1")
    client = get_shared_client()

    params: dict = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": min(limit, 100),
        "page": page,
        "apiKey": settings.NEWSAPI_KEY,
    }

    try:
        resp = await client.get(_BASE, params=params)
        data = resp.json()
    except Exception as exc:
        logger.error("NewsAPI fetch failed: %s", exc)
        return [], cursor

    if data.get("status") != "ok":
        logger.error("NewsAPI error: %s", data.get("message"))
        return [], cursor

    articles = data.get("articles", [])
    total = data.get("totalResults", 0)

    items: list[CollectedItem] = []
    for a in articles:
        title = (a.get("title") or "").strip()
        if not title or title == "[Removed]":
            continue

        url = a.get("url", "").strip()
        if not url:
            continue

        source_name = a.get("source", {}).get("name")
        author = a.get("author") or None
        description = a.get("description", "").strip() or None
        content = a.get("content", "").strip() or None
        published_at = a.get("publishedAt")

        items.append(
            CollectedItem(
                title=title,
                url=url,
                source="newsapi",
                external_id=None,
                description=description,
                content_body=content,
                author=author,
                authors_json=None,
                published_at=published_at,
                rank_position=None,
                doi=None,
                journal=source_name,
                open_access=None,
                engagement={},
                raw_payload=a,
            )
        )

    page_size = min(limit, 100)
    fetched = (page - 1) * page_size + len(articles)
    next_cursor = str(page + 1) if fetched < total and len(articles) > 0 else None
    return items, next_cursor
