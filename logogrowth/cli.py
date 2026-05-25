"""Command-line entry point for the logo-growth scanner."""

from __future__ import annotations

import argparse
import json
import sys

from .core import scan, ScanOptions
from .report import render_text, build_json


def _write_out(path: str, text: str, kind: str) -> None:
    if path == "-":
        print(text)
    else:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"\n{kind} written to {path}", file=sys.stderr)


def run(args: argparse.Namespace) -> int:
    opts = ScanOptions(
        months=args.months,
        timeline=args.timeline,
        render=args.render,
        max_points=args.max_points,
        window_days=args.window_days,
        timeout=args.timeout,
        user_agent=args.user_agent,
        screenshot_dir=args.screenshot_dir,
    )
    log = (lambda msg: print(f"[scan] {msg}", file=sys.stderr)) \
        if args.verbose else None

    domain, points = scan(args.url, opts, log=log)

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
