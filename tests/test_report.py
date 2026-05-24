import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from logogrowth.report import TimePoint, render_text, build_csv, _oldest_newest


def _points():
    return [
        TimePoint("current", "2026-05-24", "live", "https://x.ai", 42,
                  ["Stripe", "Notion", "Linear"]),
        TimePoint("6 months ago", "2025-11-24", "20251120", count=28,
                  names=["Stripe", "Notion"]),
        TimePoint("1 year ago", "2025-05-24", "20250518", count=15,
                  names=["Stripe"]),
        TimePoint("18 months ago", "2024-11-24", "", error="no snapshot"),
    ]


def test_oldest_newest_by_date_ignores_errors():
    oldest, newest = _oldest_newest(_points())
    assert oldest.label == "1 year ago"   # oldest VALID point
    assert newest.label == "current"


def test_render_shows_growth_and_new_logos():
    out = render_text("x.ai", _points())
    assert "15 → 42" in out
    assert "+180%" in out
    assert "Linear" in out                 # added since oldest


def test_csv_is_sorted_oldest_first_with_header():
    rows = build_csv(_points()).strip().splitlines()
    assert rows[0].startswith("date,label,source,logo_count")
    # first data row is the oldest date
    assert rows[1].startswith("2024-11-24")
    assert rows[-1].startswith("2026-05-24")
    assert len(rows) == 5                   # header + 4 points


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
