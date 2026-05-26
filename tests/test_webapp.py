import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from logogrowth.webapp import app


def _client():
    return app.test_client()


def test_index_serves_page_with_hooks():
    html = _client().get("/").get_data(as_text=True)
    for hook in ['id="scan"', 'id="url"', 'id="chart"', 'id="rTable"',
                 "function render", "function drawChart"]:
        assert hook in html, f"missing {hook}"


def test_demo_payload_has_growth_summary():
    d = _client().post("/api/scan", json={"demo": True}).get_json()
    s = d["summary"]
    assert len(d["points"]) == 5
    assert s["to_count"] > s["from_count"]
    assert len(s["added"]) > 0


def test_missing_url_returns_400():
    r = _client().post("/api/scan", json={})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_basic_auth_gate(monkeypatch=None):
    import base64
    os.environ["LOGOGROWTH_PASSWORD"] = "s3cret"
    os.environ["LOGOGROWTH_USER"] = "vc"
    try:
        c = _client()
        assert c.get("/").status_code == 401          # no creds -> blocked
        good = base64.b64encode(b"vc:s3cret").decode()
        assert c.get("/", headers={"Authorization": f"Basic {good}"}
                     ).status_code == 200             # right creds -> allowed
        bad = base64.b64encode(b"vc:nope").decode()
        assert c.get("/", headers={"Authorization": f"Basic {bad}"}
                     ).status_code == 401             # wrong creds -> blocked
    finally:
        os.environ.pop("LOGOGROWTH_PASSWORD", None)
        os.environ.pop("LOGOGROWTH_USER", None)


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1; print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
