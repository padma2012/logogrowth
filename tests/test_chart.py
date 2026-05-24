import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from logogrowth.report import TimePoint
from logogrowth.chart import render_chart, ChartError


def _points():
    return [
        TimePoint("2025-05", "2025-05-18", "20250518", count=15, names=["A"]),
        TimePoint("2025-11", "2025-11-20", "20251120", count=28, names=["A", "B"]),
        TimePoint("current", "2026-05-24", "live", count=42, names=["A", "B", "C"]),
        TimePoint("gap", "2024-11-24", "", error="no snapshot"),
    ]


def test_writes_nonempty_png():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "chart.png")
        render_chart("x.ai", _points(), path)
        assert os.path.getsize(path) > 1000
        with open(path, "rb") as fh:
            assert fh.read(8) == b"\x89PNG\r\n\x1a\n"   # PNG magic bytes


def test_requires_two_valid_points():
    pts = [TimePoint("current", "2026-05-24", "live", count=42),
           TimePoint("gap", "2024-11-24", "", error="no snapshot")]
    try:
        render_chart("x.ai", pts, "/tmp/should_not_exist.png")
        assert False, "expected ChartError"
    except ChartError:
        pass


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
