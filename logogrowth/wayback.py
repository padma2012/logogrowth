"""Locate Wayback Machine snapshots closest to target dates via the CDX API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from .fetch import Fetcher, FetchError

CDX_URL = "https://web.archive.org/cdx/search/cdx"
_TS_FMT = "%Y%m%d%H%M%S"


@dataclass
class Snapshot:
    timestamp: str          # 14-digit Wayback timestamp
    original: str           # original captured URL
    datetime: datetime

    @property
    def fetch_url(self) -> str:
        # `id_` returns the raw archived page (no Wayback toolbar / rewriting),
        # which is what we want to parse.
        return f"https://web.archive.org/web/{self.timestamp}id_/{self.original}"

    @property
    def view_url(self) -> str:
        return f"https://web.archive.org/web/{self.timestamp}/{self.original}"


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, _TS_FMT)
    except ValueError:
        return None


def query_snapshots(url: str, fetcher: Fetcher) -> list[Snapshot]:
    """Return all successful HTML captures of `url`, oldest first."""
    params = (
        f"?url={url}&output=json&fl=timestamp,original"
        "&filter=statuscode:200&filter=mimetype:text/html"
        "&collapse=timestamp:6"  # collapse to ~monthly granularity
    )
    text, _ = fetcher.get(CDX_URL + params)
    text = text.strip()
    if not text:
        return []
    rows = json.loads(text)
    if not rows:
        return []
    snaps: list[Snapshot] = []
    for row in rows[1:]:  # row[0] is the header
        if len(row) < 2:
            continue
        ts, original = row[0], row[1]
        dt = _parse_ts(ts)
        if dt is None:
            continue
        snaps.append(Snapshot(timestamp=ts, original=original, datetime=dt))
    snaps.sort(key=lambda s: s.datetime)
    return snaps


def closest_snapshot(snaps: list[Snapshot], target: datetime,
                     window_days: int = 120) -> Snapshot | None:
    """Pick the snapshot nearest `target`, within `window_days`."""
    best: Snapshot | None = None
    best_gap = None
    for s in snaps:
        gap = abs((s.datetime - target).days)
        if best_gap is None or gap < best_gap:
            best, best_gap = s, gap
    if best is None or best_gap is None or best_gap > window_days:
        return None
    return best
