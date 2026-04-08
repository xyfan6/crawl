from __future__ import annotations

from typing import TypedDict


class CollectedItem(TypedDict, total=False):
    title: str                      # required
    url: str                        # required
    source: str                     # required
    external_id: str | None
    description: str | None         # abstract for academic sources
    content_body: str | None
    author: str | None              # first author family name or username
    authors_json: list | None       # [{"family": "...", "given": "..."}]
    published_at: str | None        # ISO8601
    rank_position: int | None
    doi: str | None                 # normalized: no prefix, lowercase
    journal: str | None
    open_access: bool | None
    engagement: dict
    raw_payload: dict


def normalize_doi(doi: str | None) -> str | None:
    """Strip https://doi.org/ prefix and lowercase. (O2 — option A)"""
    if not doi:
        return None
    doi = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi.lower()


def normalize_title(title: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace. (O2 — option A)"""
    import re
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title
