"""YouTube Data API v3 collector."""
from __future__ import annotations

import logging

from src.collectors.base import CollectedItem
from src.config import settings
from src.http.client import get_shared_client

logger = logging.getLogger(__name__)

_BASE = "https://www.googleapis.com/youtube/v3/search"
_VIDEO_BASE = "https://www.googleapis.com/youtube/v3/videos"


async def collect(
    config: dict,
    cursor: str | None,
    limit: int,
) -> tuple[list[CollectedItem], str | None]:
    """
    config keys:
      query:     str   — search query
      min_views: int   — minimum view count (applied post-fetch)
    cursor: pageToken or None
    """
    if not settings.YOUTUBE_API_KEY:
        logger.warning("YOUTUBE_API_KEY not set — skipping YouTube collector")
        return [], cursor

    query = config.get("query", "autism")
    min_views = config.get("min_views", 0)
    client = get_shared_client()

    search_params: dict = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "date",
        "maxResults": min(limit, 50),
        "key": settings.YOUTUBE_API_KEY,
        "relevanceLanguage": "en",
    }
    if cursor:
        search_params["pageToken"] = cursor

    try:
        resp = await client.get(_BASE, params=search_params)
        data = resp.json()
    except Exception as exc:
        logger.error("YouTube search failed: %s", exc)
        return [], cursor

    video_items = data.get("items", [])
    next_token = data.get("nextPageToken")

    if not video_items:
        return [], next_token

    # Fetch view counts if min_views filter is active
    if min_views > 0:
        video_ids = ",".join(i["id"]["videoId"] for i in video_items if "videoId" in i.get("id", {}))
        stats_params = {
            "part": "statistics",
            "id": video_ids,
            "key": settings.YOUTUBE_API_KEY,
        }
        try:
            stats_resp = await client.get(_VIDEO_BASE, params=stats_params)
            stats_data = stats_resp.json()
            stats_by_id = {
                s["id"]: int(s.get("statistics", {}).get("viewCount", 0))
                for s in stats_data.get("items", [])
            }
        except Exception:
            stats_by_id = {}
    else:
        stats_by_id = {}

    items: list[CollectedItem] = []
    for v in video_items:
        vid_id = v.get("id", {}).get("videoId", "")
        if not vid_id:
            continue

        view_count = stats_by_id.get(vid_id, 0)
        if min_views > 0 and view_count < min_views:
            continue

        snippet = v.get("snippet", {})
        title = snippet.get("title", "").strip()
        if not title:
            continue

        url = f"https://www.youtube.com/watch?v={vid_id}"
        published_at = snippet.get("publishedAt")
        description = snippet.get("description", "").strip() or None
        channel = snippet.get("channelTitle")

        items.append(
            CollectedItem(
                title=title,
                url=url,
                source="youtube",
                external_id=vid_id,
                description=description,
                content_body=None,
                author=channel,
                authors_json=None,
                published_at=published_at,
                rank_position=None,
                doi=None,
                journal=None,
                open_access=None,
                engagement={"view_count": view_count},
                raw_payload=snippet,
            )
        )

    return items, next_token
