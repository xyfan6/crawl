"""Human behavior simulation for HTML scraping targets (Strategy 7)."""
import asyncio
import logging
import math
import random
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class HumanBehaviorSimulator:
    """Simulates human browsing patterns to reduce bot-detection risk.

    Only use this for HTML scraping targets, NOT for official APIs.
    Budget cap: simulated requests <= 30% of real requests.
    """

    def __init__(self) -> None:
        self._real_count = 0
        self._sim_count = 0
        self._penalty_until = 0.0
        self._base_delay = 5.0  # log-normal peak (seconds)

    def _sim_budget_ok(self) -> bool:
        return self._sim_count < max(1, self._real_count) * 0.30

    async def pre_request_delay(self) -> None:
        """Wait 2–15 s before each page fetch (log-normal, peak ~5 s)."""
        in_penalty = time.monotonic() < self._penalty_until
        mu = math.log(self._base_delay * 2.5 if in_penalty else self._base_delay)
        delay = random.lognormvariate(mu, 0.5)
        delay = max(2.0, min(15.0, delay))
        logger.debug("Human pre-request delay: %.1f s", delay)
        await asyncio.sleep(delay)

    async def maybe_visit_homepage(self, client: "Any", base_url: str) -> None:
        """20% chance to fetch homepage before a deep URL."""
        if not self._sim_budget_ok():
            return
        if random.random() >= 0.20:
            return
        try:
            parsed = urlparse(base_url)
            home = f"{parsed.scheme}://{parsed.netloc}/"
            self._sim_count += 1
            logger.debug("Human: visiting homepage %s", home)
            await client.get(home, use_browser_ua=True)
        except Exception:
            pass

    async def maybe_prefetch_favicon(self, client: "Any", base_url: str) -> None:
        """15% chance to HEAD /favicon.ico."""
        if not self._sim_budget_ok():
            return
        if random.random() >= 0.15:
            return
        try:
            parsed = urlparse(base_url)
            favicon_url = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
            self._sim_count += 1
            logger.debug("Human: prefetching favicon %s", favicon_url)
            await client._client.head(favicon_url, timeout=5)
        except Exception:
            pass

    def record_real_request(self) -> None:
        self._real_count += 1

    def on_blocked(self) -> None:
        """Call when 429 or 403 received — increases delays for 15 minutes."""
        self._penalty_until = time.monotonic() + 900
        self._base_delay = min(self._base_delay * 2.5, 30.0)
        logger.warning("Human simulator: penalty mode active for 15 min (base_delay=%.1f s)", self._base_delay)


from typing import Any  # noqa: E402 — placed here to avoid circular import issues
