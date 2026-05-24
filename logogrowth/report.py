"""Assemble per-date detection results into a logo-growth report."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class TimePoint:
    label: str                      # e.g. "current", "6 months ago"
    target_date: str                # YYYY-MM-DD we aimed for
    source: str                     # "live", a Wayback timestamp, or "render"
    url_used: str = ""
    count: int = 0
    names: list[str] = field(default_factory=list)
    sections_found: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _bar(n: int, scale: int, width: int = 24) -> str:
    if scale <= 0:
        return ""
    return "█" * max(0, min(width, round(n / scale * width)))


def render_text(domain: str, points: list[TimePoint]) -> str:
    valid = [p for p in points if not p.error]
    scale = max((p.count for p in valid), default=0)

    lines: list[str] = []
    lines.append(f"Logo growth report — {domain}")
    lines.append("=" * 60)
    header = f"{'When':<16}{'Date':<12}{'Source':<16}{'Logos':>6}  "
    lines.append(header)
    lines.append("-" * 60)
    for p in points:
        if p.error:
            lines.append(f"{p.label:<16}{p.target_date:<12}{'—':<16}"
                         f"{'n/a':>6}  ({p.error})")
            continue
        src = p.source if len(p.source) <= 15 else p.source[:12] + "…"
        lines.append(
            f"{p.label:<16}{p.target_date:<12}{src:<16}{p.count:>6}  "
            f"{_bar(p.count, scale)}"
        )
    lines.append("-" * 60)

    # Growth summary: oldest valid point -> current/newest valid point.
    if len(valid) >= 2:
        oldest, newest = valid[-1], valid[0]
        delta = newest.count - oldest.count
        pct = (delta / oldest.count * 100) if oldest.count else None
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "—")
        pct_str = f"{pct:+.0f}%" if pct is not None else "n/a"
        lines.append(
            f"Growth {oldest.label} → {newest.label}: "
            f"{oldest.count} → {newest.count}  {arrow} {delta:+d} ({pct_str})"
        )
        old_names, new_names = set(oldest.names), set(newest.names)
        added = sorted(new_names - old_names)
        removed = sorted(old_names - new_names)
        if added:
            lines.append(f"  New logos ({len(added)}): " + ", ".join(added[:20])
                         + (" …" if len(added) > 20 else ""))
        if removed:
            lines.append(f"  Dropped ({len(removed)}): " + ", ".join(removed[:20])
                         + (" …" if len(removed) > 20 else ""))
        lines.append("  (Names are best-effort; counts are the primary signal.)")
    elif len(valid) == 1:
        lines.append("Only one data point resolved — no historical comparison.")
    else:
        lines.append("No usable data points. See errors above.")

    return "\n".join(lines)


def build_json(domain: str, points: list[TimePoint]) -> dict:
    valid = [p for p in points if not p.error]
    summary = {}
    if len(valid) >= 2:
        oldest, newest = valid[-1], valid[0]
        delta = newest.count - oldest.count
        summary = {
            "from_label": oldest.label,
            "to_label": newest.label,
            "from_count": oldest.count,
            "to_count": newest.count,
            "delta": delta,
            "pct_change": (delta / oldest.count * 100) if oldest.count else None,
            "added": sorted(set(newest.names) - set(oldest.names)),
            "dropped": sorted(set(oldest.names) - set(newest.names)),
        }
    return {
        "domain": domain,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "points": [p.to_dict() for p in points],
        "summary": summary,
    }
