"""HTTP fetching with a browser-like UA and exponential-backoff retries."""

from __future__ import annotations

import time

import requests

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 logogrowth/0.1"
)


class FetchError(RuntimeError):
    pass


class Fetcher:
    def __init__(self, user_agent: str = DEFAULT_UA, timeout: int = 30,
                 retries: int = 3):
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def get(self, url: str) -> tuple[str, str]:
        """Return (html_text, final_url). Raise FetchError after retries."""
        last_err: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = self.session.get(url, timeout=self.timeout,
                                        allow_redirects=True)
                resp.raise_for_status()
                return resp.text, resp.url
            except requests.RequestException as exc:
                last_err = exc
                if attempt < self.retries - 1:
                    time.sleep(2 ** attempt)
        raise FetchError(f"failed to fetch {url}: {last_err}")
