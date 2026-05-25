"""Render a logo-count timeline to a PNG (used with --chart)."""

from __future__ import annotations

from datetime import datetime


class ChartError(RuntimeError):
    pass


def _date_key(p) -> datetime:
    try:
        return datetime.strptime(p.target_date, "%Y-%m-%d")
    except ValueError:
        return datetime.min


def render_chart(domain: str, points, path: str) -> str:
    """Write a line chart of logo count over time to `path`.

    Raises ChartError if matplotlib is missing or there is too little data.
    """
    valid = [p for p in points if not p.error]
    if len(valid) < 2:
        raise ChartError("need at least 2 successful data points to chart")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError as exc:
        raise ChartError(
            "matplotlib is not installed. Install it with: pip install matplotlib"
        ) from exc

    pts = sorted(valid, key=_date_key)
    xs = [_date_key(p) for p in pts]
    ys = [p.count for p in pts]
    oldest, newest = pts[0], pts[-1]
    total_delta = newest.count - oldest.count
    pct = (total_delta / oldest.count * 100) if oldest.count else None

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(xs, ys, marker="o", linewidth=2, color="#2563eb", zorder=3)
    ax.fill_between(xs, ys, color="#2563eb", alpha=0.08, zorder=1)
    for x, y in zip(xs, ys):
        ax.annotate(str(y), (x, y), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=8, color="#374151")

    # Per-segment change (only when not too crowded).
    if len(pts) <= 10:
        for i in range(1, len(pts)):
            d = ys[i] - ys[i - 1]
            if d == 0:
                continue
            midx = xs[i - 1] + (xs[i] - xs[i - 1]) / 2
            midy = (ys[i] + ys[i - 1]) / 2
            color = "#16a34a" if d > 0 else "#dc2626"
            ax.annotate(f"{d:+d}", (midx, midy), textcoords="offset points",
                        xytext=(0, -12), ha="center", fontsize=7.5,
                        color=color, fontweight="bold")

    pct_str = f"{pct:+.0f}%" if pct is not None else "n/a"
    subtitle = (f"{oldest.count} → {newest.count} logos "
                f"({total_delta:+d}, {pct_str})   ·   "
                f"{oldest.label} → {newest.label}")
    ax.set_title(f"Customer logo growth — {domain}", fontsize=13,
                 fontweight="bold", pad=26)
    ax.text(0.5, 1.04, subtitle, transform=ax.transAxes, ha="center",
            fontsize=9.5, color="#6b7280")
    ax.set_ylabel("Logos detected")
    ax.set_xlabel("Date")
    ax.set_ylim(bottom=0)
    ax.margins(x=0.03)
    ax.grid(True, axis="y", alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
