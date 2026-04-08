"""Europe PMC REST API collector."""
from __future__ import annotations

import logging

from src.collectors.base import CollectedItem, normalize_doi
from src.http.client import get_shared_client

logger = logging.getLogger(__name__)

_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


async def collect(
    config: dict,
    cursor: str | None,
    limit: int,
) -> tuple[list[CollectedItem], str | None]:
    """
    config keys:
      query: str
    cursor: cursorMark string (None → '*')
    """
    query = config.get("query", "autism OR ASD OR autistic")
    cursor_mark = cursor or "*"
    client = get_shared_client()

    params = {
        "query": query,
        "resultType": "core",
        "pageSize": limit,
        "cursorMark": cursor_mark,
        "format": "json",
        "sort": "P_PDATE_D desc",
    }

    try:
        resp = await client.get(_BASE, params=params)
        data = resp.json()
    except Exception as exc:
        logger.error("EuropePMC fetch failed: %s", exc)
        return [], cursor

    results = data.get("resultList", {}).get("result", [])
    next_cursor = data.get("nextCursorMark")

    items: list[CollectedItem] = []
    for r in results:
        title = (r.get("title") or "").strip()
        if not title:
            continue

        pmid = r.get("pmid")
        pmcid = r.get("pmcid")
        doi = normalize_doi(r.get("doi"))

        if pmid:
            url = f"https://europepmc.org/article/MED/{pmid}"
        elif pmcid:
            url = f"https://europepmc.org/article/PMC/{pmcid}"
        elif doi:
            url = f"https://doi.org/{doi}"
        else:
            url = r.get("fullTextUrlList", {}).get("fullTextUrl", [{}])[0].get("url", "")
        if not url:
            continue

        # Authors
        authors_json = []
        for au in r.get("authorList", {}).get("author", []):
            family = au.get("lastName") or au.get("collectiveName")
            given = au.get("firstName")
            if family:
                authors_json.append({"family": family, "given": given})

        published_at: str | None = None
        pub_date = r.get("firstPublicationDate") or r.get("pubYear")
        if pub_date:
            if len(pub_date) == 4:
                published_at = f"{pub_date}-01-01T00:00:00+00:00"
            else:
                published_at = f"{pub_date}T00:00:00+00:00"

        is_oa = r.get("isOpenAccess", "N") == "Y"

        items.append(
            CollectedItem(
                title=title,
                url=url,
                source="europepmc",
                external_id=pmid or pmcid,
                description=r.get("abstractText") or None,
                content_body=r.get("fullText") or None,
                author=authors_json[0]["family"] if authors_json else None,
                authors_json=authors_json or None,
                published_at=published_at,
                rank_position=None,
                doi=doi,
                journal=r.get("journalTitle"),
                open_access=is_oa,
                engagement={},
                raw_payload=r,
            )
        )

    return items, next_cursor if next_cursor and next_cursor != cursor_mark else None
