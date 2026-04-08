"""Ingest pipeline: upserts CollectedItems into the DB and enriches with Unpaywall."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.collectors.base import CollectedItem, normalize_title
from src.storage.models import CrawledItem

logger = logging.getLogger(__name__)


async def save_items(
    items: list[CollectedItem],
    surface_key: str,
    session: AsyncSession,
) -> int:
    """Upsert items into crawled_items. Returns count of newly inserted rows."""
    if not items:
        return 0

    inserted = 0
    for item in items:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        if not title or not url:
            continue

        published_at_val: datetime | None = None
        raw_date = item.get("published_at")
        if raw_date:
            try:
                from dateutil.parser import parse as parse_date  # type: ignore
                published_at_val = parse_date(raw_date)
            except Exception:
                try:
                    published_at_val = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                except Exception:
                    pass

        row = {
            "external_id": item.get("external_id"),
            "source": item.get("source", "unknown"),
            "surface_key": surface_key,
            "title": title,
            "url": url,
            "description": item.get("description"),
            "content_body": item.get("content_body"),
            "author": item.get("author"),
            "authors_json": item.get("authors_json"),
            "published_at": published_at_val,
            "collected_at": datetime.now(tz=timezone.utc),
            "rank_position": item.get("rank_position"),
            "engagement": item.get("engagement") or {},
            "doi": item.get("doi"),
            "journal": item.get("journal"),
            "open_access": item.get("open_access"),
            "raw_payload": item.get("raw_payload") or {},
        }

        stmt = insert(CrawledItem).values(**row)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_crawled_items_url",
            set_={
                "engagement": stmt.excluded.engagement,
                "rank_position": stmt.excluded.rank_position,
                "description": stmt.excluded.description,
                "collected_at": stmt.excluded.collected_at,
            },
        )

        try:
            result = await session.execute(stmt)
            # rowcount == 1 on insert, 0 on update (DO UPDATE with no change)
            if result.rowcount == 1:
                inserted += 1
        except IntegrityError:
            # DOI unique constraint conflict (same DOI at different URL)
            await session.rollback()
            logger.debug("DOI conflict skipped for url=%s doi=%s", url, item.get("doi"))
            continue

    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.error("pipeline commit failed: %s", exc)
        return 0

    return inserted


# ---------------------------------------------------------------------------
# Unpaywall enrichment
# ---------------------------------------------------------------------------

async def enrich_unpaywall(session: AsyncSession, batch_size: int = 50) -> int:
    """Fetch open-access URLs from Unpaywall for records with DOI but no content_body."""
    from src.config import settings
    from src.http.client import get_shared_client

    client = get_shared_client()
    updated = 0

    # Find records with DOI but no content_body
    result = await session.execute(
        select(CrawledItem.id, CrawledItem.doi)
        .where(CrawledItem.doi.isnot(None))
        .where(CrawledItem.content_body.is_(None))
        .where(CrawledItem.open_access.isnot(True))
        .limit(batch_size)
    )
    rows = result.fetchall()

    for row_id, doi in rows:
        url = f"https://api.unpaywall.org/v2/{doi}?email={settings.CRAWLER_EMAIL}"
        try:
            resp = await client.get(url)
            data = resp.json()
        except Exception as exc:
            logger.debug("Unpaywall failed for doi=%s: %s", doi, exc)
            continue

        is_oa = data.get("is_oa", False)
        best_oa = data.get("best_oa_location") or {}
        oa_url = best_oa.get("url_for_pdf") or best_oa.get("url")

        if is_oa or oa_url:
            await session.execute(
                update(CrawledItem)
                .where(CrawledItem.id == row_id)
                .values(open_access=is_oa)
            )
            updated += 1

    await session.commit()
    return updated
