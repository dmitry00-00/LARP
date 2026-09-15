"""Один вежливый HTTP-клиент на все импортёры.

Пауза между запросами к одному хосту, честный User-Agent, ретраи на 5xx.
Лимиты Telegram здесь ни при чём — это про чужие сайты, которые нас не
звали: DATA_SOURCES §5 «агрегатор, который выглядит воровством контента,
получает бан в чатах и умирает».
"""
from __future__ import annotations

import time
from urllib.parse import urlsplit

import httpx
import structlog

from hmb import config

log = structlog.get_logger("hmb.http")
_last_hit: dict[str, float] = {}


class Http:
    def __init__(self, delay: float | None = None, timeout: float = 30.0) -> None:
        self.delay = config.POLITE_DELAY_SEC if delay is None else delay
        self._client = httpx.Client(
            headers={"User-Agent": config.USER_AGENT, "Accept-Language": "ru,en;q=0.8,de;q=0.6,nl;q=0.5"},
            timeout=timeout, follow_redirects=True,
        )

    def _wait(self, url: str) -> None:
        host = urlsplit(url).netloc
        prev = _last_hit.get(host)
        if prev is not None:
            gap = self.delay - (time.monotonic() - prev)
            if gap > 0:
                time.sleep(gap)
        _last_hit[host] = time.monotonic()

    def get(self, url: str, **kw) -> httpx.Response:
        for attempt in range(3):
            self._wait(url)
            r = self._client.get(url, **kw)
            if r.status_code < 500:
                return r
            log.warning("http.5xx", url=url, status=r.status_code, attempt=attempt)
            time.sleep(2.0 * (attempt + 1))
        return r

    def json(self, url: str, **kw):
        r = self.get(url, **kw)
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._client.close()
