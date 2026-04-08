"""Semantic Scholar Graph API collector."""
from __future__ import annotations

import logging

from src.collectors.base import CollectedItem, normalize_doi
from src.config import settings
from src.http.client import get_shared_client

logger = logging.getLogger(__name__)

_BASE = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,url,abstract,authors,year,externalIds,publicationDate,venue,isOpenAccess,citationCount"


async def collect(
    config: dict,
    cursor: str | None,
    limit: int,
) -> tuple[list[CollectedItem], str | None]:
    """
    config keys:
      query: str
    cursor: offset as string
    """
    query = config.get("query", "autism spectrum disorder")
    offset = int(cursor or "0")
    client = get_shared_client()

    params: dict = {
        "query": query,
        "fields": _FIELDS,
        "limit": min(limit, 100),
        "offset": offset,
    }

    headers: dict = {}
    if settings.SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY

    try:
        resp = await client.get(_BASE, params=params, headers=headers)
        data = resp.json()
    except Exception as exc:
        logger.error("SemanticScholar fetch failed: %s", exc)
        return [], cursor

    papers = data.get("data", [])
    total = data.get("total", 0)
    new_offset = offset + len(papers)

    items: list[CollectedItem] = []
    for p in papers:
        title = (p.get("title") or "").strip()
        if not title:
            continue

        paper_url = p.get("url", "")
        doi = normalize_doi(p.get("externalIds", {}).get("DOI"))
        if not paper_url and doi:
            paper_url = f"https://doi.org/{doi}"
        if not paper_url:
            continue

        authors_json = []
        for au in p.get("authors", []):
            name = au.get("name", "")
            parts = name.rsplit(" ", 1)
            family = parts[-1] if parts else name
            given = parts[0] if len(parts) > 1 else None
            if family:
                authors_json.append({"family": family, "given": given})

        pub_date = p.get("publicationDate")
        year = p.get("year")
        if pub_date:
            published_at = f"{pub_date}T00:00:00+00:00"
        elif year:
            published_at = f"{year}-01-01T00:00:00+00:00"
        else:
            published_at = None

        items.append(
            CollectedItem(
                title=title,
                url=paper_url,
                source="semanticscholar",
                external_id=p.get("paperId"),
                description=p.get("abstract") or None,
                content_body=None,
                author=authors_json[0]["family"] if authors_json else None,
                authors_json=authors_json or None,
                published_at=published_at,
                rank_position=None,
                doi=doi,
                journal=p.get("venue") or None,
                open_access=p.get("isOpenAccess"),
                engagement={"citation_count": p.get("citationCount", 0)},
                raw_payload=p,
            )
        )

    next_cursor = str(new_offset) if new_offset < total else None
    return items, next_cursor
