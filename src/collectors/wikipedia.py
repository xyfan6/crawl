"""Wikipedia API collector (background reference articles by title)."""
from __future__ import annotations

import logging

from src.collectors.base import CollectedItem
from src.http.client import get_shared_client

logger = logging.getLogger(__name__)

_SUMMARY_API = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_WIKI_API = "https://en.wikipedia.org/w/api.php"


async def collect(
    config: dict,
    cursor: str | None,
    limit: int,
) -> tuple[list[CollectedItem], str | None]:
    """
    config keys:
      titles: list[str]   — Wikipedia article titles to fetch
    cursor: last-fetched title (skip titles already fetched) or None
    """
    titles: list[str] = config.get("titles", ["Autism spectrum disorder"])
    client = get_shared_client()

    # Determine which titles to fetch (skip until after cursor)
    if cursor and cursor in titles:
        idx = titles.index(cursor)
        remaining = titles[idx + 1:]
    else:
        remaining = titles

    items: list[CollectedItem] = []
    last_fetched: str | None = cursor

    for title in remaining[:limit]:
        encoded = title.replace(" ", "_")
        url = f"https://en.wikipedia.org/wiki/{encoded}"

        try:
            resp = await client.get(_SUMMARY_API.format(title=encoded))
            data = resp.json()
        except Exception as exc:
            logger.warning("Wikipedia fetch failed for '%s': %s", title, exc)
            continue

        if data.get("type") == "disambiguation":
            logger.info("Wikipedia '%s' is disambiguation page — skipping", title)
            continue

        summary_title = data.get("title", title).strip()
        description = data.get("extract", "").strip() or None
        thumbnail = data.get("thumbnail", {}).get("source")
        last_modified = data.get("timestamp")

        published_at: str | None = None
        if last_modified:
            published_at = last_modified  # already ISO8601

        items.append(
            CollectedItem(
                title=summary_title,
                url=url,
                source="wikipedia",
                external_id=str(data.get("pageid", "")),
                description=description,
                content_body=None,
                author=None,
                authors_json=None,
                published_at=published_at,
                rank_position=None,
                doi=None,
                journal=None,
                open_access=True,
                engagement={},
                raw_payload=data,
            )
        )
        last_fetched = title

    # Return last fetched title as cursor; None if all fetched
    next_cursor = last_fetched if last_fetched != titles[-1] else None
    return items, next_cursor
