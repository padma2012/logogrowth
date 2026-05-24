"""Command-line entry point for the logo-growth scanner."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import urlparse

from .detect import detect_logos
from .fetch import Fetcher, FetchError
from .report import TimePoint, render_text, build_json
from .wayback import query_snapshots, closest_snapshot, Snapshot


def _normalize_url(raw: str) -> str:
    if not re.match(r"^https?://", raw):
        raw = "https://" + raw
    return raw


def _domain(url: str) -> str:
    return urlparse(url).netloc or url


def _label_for(months: int) -> str:
    if months == 0:
        return "current"
    if months % 12 == 0:
        y = months // 12
        return f"{y} year{'s' if y > 1 else ''} ago"
    return f"{months} months ago"


def _sanitize(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _get_html(url: str, fetcher: Fetcher, render: bool,
              screenshot_path: str | None) -> str:
    if render:
        from .render import render_html, RenderError
        try:
            return render_html(url, screenshot_path=screenshot_path,
                               user_agent=fetcher.session.headers["User-Agent"])
        except RenderError as exc:
            raise FetchError(str(exc)) from exc
    html, _ = fetcher.get(url)
    return html


def _shot_path(args: argparse.Namespace, label: str) -> str | None:
    if args.screenshot_dir and args.render:
        return f"{args.screenshot_dir.rstrip('/')}/{_sanitize(label)}.png"
    return None


def _scan(target_url: str, view_url: str, tp: TimePoint,
          fetcher: Fetcher, args: argparse.Namespace) -> TimePoint:
    """Fetch + detect for one time point, filling `tp` in place."""
    shot_path = _shot_path(args, tp.label)
    try:
        html = _get_html(target_url, fetcher, args.render, shot_path)
    except FetchError as exc:
        tp.error = str(exc).split("\n")[0][:100]
        return tp
    result = detect_logos(html, base_url=view_url)
    tp.count = result.count
    tp.names = result.names
    tp.sections_found = result.sections_found
    if shot_path:
        tp.source += " +shot"
    if args.verbose:
        print(f"[detect] {tp.label}: {result.count} logos "
              f"({result.sections_found} sections)", file=sys.stderr)
    return tp


def _current_point(url: str, now: datetime, fetcher: Fetcher,
                   args: argparse.Namespace) -> TimePoint:
    tp = TimePoint(label="current", target_date=now.strftime("%Y-%m-%d"),
                   source="render" if args.render else "live", url_used=url)
    return _scan(url, url, tp, fetcher, args)


def _scan_timeline(url: str, now: datetime, snaps: list[Snapshot],
                   fetcher: Fetcher, args: argparse.Namespace) -> list[TimePoint]:
    points = [_current_point(url, now, fetcher, args)]
    seen_months: set[str] = set()
    for snap in sorted(snaps, key=lambda s: s.datetime, reverse=True):
        ym = snap.datetime.strftime("%Y-%m")
        if ym in seen_months:
            continue
        seen_months.add(ym)
        if args.max_points and (len(points) - 1) >= args.max_points:
            break
        tp = TimePoint(label=ym, target_date=snap.datetime.strftime("%Y-%m-%d"),
                       source=snap.timestamp, url_used=snap.view_url)
        target_url = snap.view_url if args.render else snap.fetch_url
        points.append(_scan(target_url, snap.view_url, tp, fetcher, args))
    points.sort(key=lambda p: p.target_date)  # oldest -> newest
    return points


def _scan_offsets(url: str, now: datetime, snaps: list[Snapshot],
                  fetcher: Fetcher, args: argparse.Namespace) -> list[TimePoint]:
    points: list[TimePoint] = []
    for m in [0] + sorted(set(args.months)):
        target = now - timedelta(days=round(m * 30.44))
        if m == 0:
            points.append(_current_point(url, now, fetcher, args))
            continue
        tp = TimePoint(label=_label_for(m),
                       target_date=target.strftime("%Y-%m-%d"), source="")
        snap = closest_snapshot(snaps, target, window_days=args.window_days)
        if snap is None:
            tp.error = "no snapshot near this date"
            points.append(tp)
            continue
        tp.source = snap.timestamp
        tp.url_used = snap.view_url
        target_url = snap.view_url if args.render else snap.fetch_url
        points.append(_scan(target_url, snap.view_url, tp, fetcher, args))
    return points


def _write_out(path: str, text: str, kind: str) -> None:
    if path == "-":
        print(text)
    else:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"\n{kind} written to {path}", file=sys.stderr)


def run(args: argparse.Namespace) -> int:
    url = _normalize_url(args.url)
    domain = _domain(url)
    fetcher = Fetcher(user_agent=args.user_agent, timeout=args.timeout)
    now = datetime.utcnow()

    # Historical points need Wayback snapshots; only query if we need them.
    snaps: list[Snapshot] = []
    if args.timeline or any(m > 0 for m in args.months):
        try:
            snaps = query_snapshots(domain, fetcher)
            if args.verbose:
                print(f"[wayback] {len(snaps)} snapshots found for {domain}",
                      file=sys.stderr)
        except (FetchError, ValueError) as exc:
            print(f"[wayback] snapshot lookup failed: {exc}", file=sys.stderr)

    if args.timeline:
        points = _scan_timeline(url, now, snaps, fetcher, args)
    else:
        points = _scan_offsets(url, now, snaps, fetcher, args)

    print(render_text(domain, points))

    if args.json:
        _write_out(args.json, json.dumps(build_json(domain, points), indent=2),
                   "JSON")
    if args.csv:
        from .report import build_csv
        _write_out(args.csv, build_csv(points), "CSV")

    if args.chart:
        from .chart import render_chart, ChartError
        try:
            render_chart(domain, points, args.chart)
            print(f"\nChart written to {args.chart}", file=sys.stderr)
        except ChartError as exc:
            print(f"[chart] {exc}", file=sys.stderr)

    return 0 if any(not p.error for p in points) else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="logogrowth",
        description="Scan a website now and in the past (via the Wayback "
                    "Machine) to measure customer/partner logo growth.",
    )
    p.add_argument("url", help="website to scan, e.g. granola.ai")
    p.add_argument("--months", type=int, nargs="+", default=[6, 12, 18],
                   metavar="N", help="historical offsets in months "
                                     "(default: 6 12 18)")
    p.add_argument("--timeline", action="store_true",
                   help="walk every monthly Wayback snapshot to chart logo "
                        "count over time (ignores --months)")
    p.add_argument("--max-points", type=int, default=0, metavar="N",
                   help="in --timeline mode, cap to the N most recent "
                        "snapshots (0 = no limit)")
    p.add_argument("--csv", metavar="PATH",
                   help="write a CSV report to PATH ('-' for stdout)")
    p.add_argument("--chart", metavar="PATH",
                   help="write a PNG line chart of logo count over time "
                        "(needs matplotlib)")
    p.add_argument("--render", action="store_true",
                   help="render pages with headless Chromium (Playwright) "
                        "for JS-heavy sites")
    p.add_argument("--screenshot-dir", metavar="DIR",
                   help="save full-page screenshots here (requires --render)")
    p.add_argument("--json", metavar="PATH",
                   help="write a JSON report to PATH ('-' for stdout)")
    p.add_argument("--window-days", type=int, default=120,
                   help="max days a snapshot may deviate from a target date "
                        "(default: 120)")
    p.add_argument("--user-agent", default=None,
                   help="override the HTTP User-Agent header")
    p.add_argument("--timeout", type=int, default=30,
                   help="per-request timeout in seconds (default: 30)")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="print progress to stderr")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.user_agent is None:
        from .fetch import DEFAULT_UA
        args.user_agent = DEFAULT_UA
    if args.screenshot_dir and not args.render:
        parser.error("--screenshot-dir requires --render")
    try:
        return run(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
