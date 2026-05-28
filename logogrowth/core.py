"""Core scan engine shared by the CLI and the web app."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable
from urllib.parse import urlparse

from .detect import detect_logos
from .fetch import Fetcher, FetchError, DEFAULT_UA
from .report import TimePoint
from .wayback import query_snapshots, closest_snapshot, Snapshot


@dataclass
class ScanOptions:
    months: list[int] = field(default_factory=lambda: [6, 12, 18])
    timeline: bool = False
    since_years: int = 0          # 0 = no cap; otherwise drop snapshots older than this
    render: bool = False
    max_points: int = 0
    window_days: int = 120
    timeout: int = 30
    user_agent: str = DEFAULT_UA
    screenshot_dir: str | None = None


# A progress callback: receives short status strings. Defaults to a no-op.
Logger = Callable[[str], None]


def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not re.match(r"^https?://", raw):
        raw = "https://" + raw
    return raw


def domain_of(url: str) -> str:
    return urlparse(url).netloc or url


def label_for(months: int) -> str:
    if months == 0:
        return "current"
    if months % 12 == 0:
        y = months // 12
        return f"{y} year{'s' if y > 1 else ''} ago"
    return f"{months} months ago"


def _sanitize(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _get_html(url: str, fetcher: Fetcher, opts: ScanOptions,
              screenshot_path: str | None) -> str:
    if opts.render:
        from .render import render_html, RenderError
        try:
            return render_html(url, screenshot_path=screenshot_path,
                               user_agent=opts.user_agent)
        except RenderError as exc:
            raise FetchError(str(exc)) from exc
    html, _ = fetcher.get(url)
    return html


def _shot_path(opts: ScanOptions, label: str) -> str | None:
    if opts.screenshot_dir and opts.render:
        return f"{opts.screenshot_dir.rstrip('/')}/{_sanitize(label)}.png"
    return None


def _scan_point(target_url: str, view_url: str, tp: TimePoint,
                fetcher: Fetcher, opts: ScanOptions, log: Logger,
                self_domain: str = "") -> TimePoint:
    shot_path = _shot_path(opts, tp.label)
    try:
        html = _get_html(target_url, fetcher, opts, shot_path)
    except FetchError as exc:
        tp.error = str(exc).split("\n")[0][:100]
        log(f"{tp.label}: error — {tp.error}")
        return tp
    result = detect_logos(html, base_url=view_url, self_domain=self_domain)
    tp.count = result.count
    tp.names = result.names
    tp.logos = [{"name": lg.name, "src": lg.src} for lg in result.logos
                if lg.src and not lg.src.startswith("data:")][:80]
    tp.sections_found = result.sections_found
    if shot_path:
        tp.source += " +shot"
    log(f"{tp.label}: {result.count} logos ({result.sections_found} sections)")
    return tp


def _current_point(url: str, now: datetime, fetcher: Fetcher,
                   opts: ScanOptions, log: Logger,
                   self_domain: str = "") -> TimePoint:
    tp = TimePoint(label="current", target_date=now.strftime("%Y-%m-%d"),
                   source="render" if opts.render else "live", url_used=url)
    return _scan_point(url, url, tp, fetcher, opts, log, self_domain)


def _scan_timeline(url: str, now: datetime, snaps: list[Snapshot],
                   fetcher: Fetcher, opts: ScanOptions,
                   log: Logger, self_domain: str = "") -> list[TimePoint]:
    points = [_current_point(url, now, fetcher, opts, log, self_domain)]
    seen_months: set[str] = set()
    cutoff = (now - timedelta(days=int(365.25 * opts.since_years))
              if opts.since_years > 0 else None)
    for snap in sorted(snaps, key=lambda s: s.datetime, reverse=True):
        if cutoff and snap.datetime < cutoff:
            break  # sorted newest-first, so the rest are older too
        ym = snap.datetime.strftime("%Y-%m")
        if ym in seen_months:
            continue
        seen_months.add(ym)
        if opts.max_points and (len(points) - 1) >= opts.max_points:
            break
        tp = TimePoint(label=ym, target_date=snap.datetime.strftime("%Y-%m-%d"),
                       source=snap.timestamp, url_used=snap.view_url)
        target_url = snap.view_url if opts.render else snap.fetch_url
        points.append(_scan_point(target_url, snap.view_url, tp, fetcher,
                                  opts, log, self_domain))
    points.sort(key=lambda p: p.target_date)  # oldest -> newest
    return points


def _scan_offsets(url: str, now: datetime, snaps: list[Snapshot],
                  fetcher: Fetcher, opts: ScanOptions,
                  log: Logger, self_domain: str = "") -> list[TimePoint]:
    points: list[TimePoint] = []
    for m in [0] + sorted(set(opts.months)):
        target = now - timedelta(days=round(m * 30.44))
        if m == 0:
            points.append(_current_point(url, now, fetcher, opts, log,
                                         self_domain))
            continue
        tp = TimePoint(label=label_for(m),
                       target_date=target.strftime("%Y-%m-%d"), source="")
        snap = closest_snapshot(snaps, target, window_days=opts.window_days)
        if snap is None:
            tp.error = "no snapshot near this date"
            points.append(tp)
            continue
        tp.source = snap.timestamp
        tp.url_used = snap.view_url
        target_url = snap.view_url if opts.render else snap.fetch_url
        points.append(_scan_point(target_url, snap.view_url, tp, fetcher,
                                  opts, log, self_domain))
    return points


def scan(url: str, opts: ScanOptions | None = None,
         log: Logger | None = None) -> tuple[str, list[TimePoint]]:
    """Scan `url` now and in the past; return (domain, points oldest->newest)."""
    opts = opts or ScanOptions()
    log = log or (lambda _msg: None)

    url = normalize_url(url)
    domain = domain_of(url)
    # If the user pointed at a specific page (e.g. /suppliers), look up
    # snapshots of THAT path. Otherwise fall back to the whole site.
    parsed = urlparse(url)
    path = (parsed.path or "").rstrip("/")
    lookup = (parsed.netloc + path) if path else domain
    fetcher = Fetcher(user_agent=opts.user_agent, timeout=opts.timeout)
    now = datetime.utcnow()

    snaps: list[Snapshot] = []
    if opts.timeline or any(m > 0 for m in opts.months):
        try:
            snaps = query_snapshots(lookup, fetcher)
            log(f"wayback: {len(snaps)} snapshots found for {lookup}")
        except (FetchError, ValueError) as exc:
            log(f"wayback: snapshot lookup failed: {exc}")

    if opts.timeline:
        return domain, _scan_timeline(url, now, snaps, fetcher, opts, log,
                                      self_domain=domain)
    return domain, _scan_offsets(url, now, snaps, fetcher, opts, log,
                                 self_domain=domain)
