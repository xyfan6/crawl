"""OpenAlex REST API collector (no key needed; polite pool via mailto)."""
from __future__ import annotations

import logging

from src.collectors.base import CollectedItem, normalize_doi
from src.config import settings
from src.http.client import get_shared_client

logger = logging.getLogger(__name__)

_BASE = "https://api.openalex.org/works"


async def collect(
    config: dict,
    cursor: str | None,
    limit: int,
) -> tuple[list[CollectedItem], str | None]:
    """
    config keys:
      query:  str   — title/abstract search
      filter: str   — e.g. 'open_access.is_oa:true'
    cursor: OpenAlex cursor string (None → '*')
    """
    query = config.get("query", "autism spectrum disorder")
    extra_filter = config.get("filter", "")
    oa_cursor = cursor or "*"
    client = get_shared_client()

    filters = f"title.search:{query}"
    if extra_filter:
        filters += f",{extra_filter}"

    params: dict = {
        "filter": filters,
        "per-page": min(limit, 200),
        "cursor": oa_cursor,
        "sort": "publication_date:desc",
        "select": "id,title,doi,publication_date,authorships,primary_location,open_access,abstract_inverted_index,cited_by_count",
        "mailto": settings.CRAWLER_EMAIL,
    }

    try:
        resp = await client.get(_BASE, params=params)
        data = resp.json()
    except Exception as exc:
        logger.error("OpenAlex fetch failed: %s", exc)
        return [], cursor

    results = data.get("results", [])
    meta = data.get("meta", {})
    next_cursor = meta.get("next_cursor")

    items: list[CollectedItem] = []
    for r in results:
        title = (r.get("title") or "").strip()
        if not title:
            continue

        doi = normalize_doi(r.get("doi"))
        oa_url = r.get("primary_location", {}) or {}
        url = (
            oa_url.get("landing_page_url")
            or oa_url.get("pdf_url")
            or (f"https://doi.org/{doi}" if doi else "")
        )
        if not url:
            continue

        # Reconstruct abstract from inverted index
        description: str | None = None
        inv = r.get("abstract_inverted_index")
        if inv:
            try:
                words: dict[int, str] = {}
                for word, positions in inv.items():
                    for pos in positions:
                        words[pos] = word
                description = " ".join(words[i] for i in sorted(words))
            except Exception:
                pass

        # Authors
        authors_json = []
        for au in r.get("authorships", []):
            author_info = au.get("author", {})
            display = author_info.get("display_name", "")
            parts = display.rsplit(" ", 1)
            family = parts[-1] if parts else display
            given = parts[0] if len(parts) > 1 else None
            if family:
                authors_json.append({"family": family, "given": given})

        pub_date = r.get("publication_date")
        published_at = f"{pub_date}T00:00:00+00:00" if pub_date else None

        oa_info = r.get("open_access", {})
        is_oa = oa_info.get("is_oa")

        journal = (r.get("primary_location") or {}).get("source", {}) or {}
        journal_name = journal.get("display_name") if isinstance(journal, dict) else None

        items.append(
            CollectedItem(
                title=title,
                url=url,
                source="openalex",
                external_id=r.get("id"),
                description=description,
                content_body=None,
                author=authors_json[0]["family"] if authors_json else None,
                authors_json=authors_json or None,
                published_at=published_at,
                rank_position=None,
                doi=doi,
                journal=journal_name,
                open_access=is_oa,
                engagement={"cited_by_count": r.get("cited_by_count", 0)},
                raw_payload=r,
            )
        )

    return items, next_cursor
