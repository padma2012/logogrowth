"""Flask web UI: paste a URL, get an interactive logo-growth report.

Run with:  python -m logogrowth.webapp   (or `logogrowth-web`)
"""

from __future__ import annotations

import argparse
import hmac
import os

from flask import Flask, Response, jsonify, render_template, request

from .core import scan, ScanOptions
from .report import TimePoint, build_json

app = Flask(__name__)


@app.before_request
def _require_auth():
    """If LOGOGROWTH_PASSWORD is set, gate the whole app behind basic auth.

    Unset (the default) means no auth — convenient for local use. Always set
    it when hosting publicly, since the server fetches arbitrary URLs.
    """
    password = os.environ.get("LOGOGROWTH_PASSWORD")
    if not password:
        return None
    user = os.environ.get("LOGOGROWTH_USER", "vc")
    auth = request.authorization
    ok = (auth and auth.username == user
          and hmac.compare_digest(auth.password or "", password))
    if not ok:
        return Response("Authentication required.", 401,
                        {"WWW-Authenticate": 'Basic realm="logogrowth"'})
    return None


_LOGO_DOMAINS = {
    "Stripe": "stripe.com", "Notion": "notion.so", "Ramp": "ramp.com",
    "Vercel": "vercel.com", "Linear": "linear.app", "Loom": "loom.com",
    "Figma": "figma.com", "Retool": "retool.com", "Census": "getcensus.com",
    "Hex": "hex.tech", "Webflow": "webflow.com", "Mercury": "mercury.com",
    "Brex": "brex.com", "Deel": "deel.com", "Rippling": "rippling.com",
    "Airtable": "airtable.com", "Amplitude": "amplitude.com",
    "Snowflake": "snowflake.com", "Datadog": "datadoghq.com",
    "Plaid": "plaid.com", "Scale": "scale.com", "Anthropic": "anthropic.com",
    "OpenAI": "openai.com", "Cursor": "cursor.com",
    "Perplexity": "perplexity.ai", "Replit": "replit.com", "Vanta": "vanta.com",
    "Clay": "clay.com", "Attio": "attio.com", "Pylon": "usepylon.com",
    "Cohere": "cohere.com", "Mistral": "mistral.ai", "Sierra": "sierra.ai",
    "Decagon": "decagon.ai", "Harvey": "harvey.ai", "Glean": "glean.com",
}


def _logo(name: str) -> dict:
    d = _LOGO_DOMAINS.get(name)
    return {"name": name,
            "src": f"https://logo.clearbit.com/{d}?size=128" if d else ""}


def _demo_payload() -> dict:
    """Canned data so the UI is viewable without network access."""
    sets = [
        ["Stripe", "Notion", "Ramp", "Vercel", "Linear", "Loom"],
        ["Stripe", "Notion", "Ramp", "Vercel", "Linear", "Loom", "Figma",
         "Retool", "Census", "Hex", "Webflow"],
        ["Stripe", "Notion", "Ramp", "Vercel", "Linear", "Loom", "Figma",
         "Retool", "Census", "Hex", "Webflow", "Mercury", "Brex", "Deel",
         "Rippling", "Airtable", "Amplitude"],
        ["Stripe", "Notion", "Ramp", "Vercel", "Linear", "Loom", "Figma",
         "Retool", "Census", "Hex", "Webflow", "Mercury", "Brex", "Deel",
         "Rippling", "Airtable", "Amplitude", "Snowflake", "Datadog", "Plaid",
         "Scale", "Anthropic", "OpenAI", "Cursor", "Perplexity", "Replit"],
        ["Stripe", "Notion", "Ramp", "Vercel", "Linear", "Loom", "Figma",
         "Retool", "Census", "Hex", "Webflow", "Mercury", "Brex", "Deel",
         "Rippling", "Airtable", "Amplitude", "Snowflake", "Datadog", "Plaid",
         "Scale", "Anthropic", "OpenAI", "Cursor", "Perplexity", "Replit",
         "Vanta", "Clay", "Attio", "Pylon", "Cohere", "Mistral", "Sierra",
         "Decagon", "Harvey", "Glean"],
    ]
    meta = [
        ("2024-05", "2024-05-12", "20240512"),
        ("2024-11", "2024-11-18", "20241118"),
        ("2025-05", "2025-05-18", "20250518"),
        ("2025-11", "2025-11-20", "20251120"),
        ("current", "2026-05-24", "live"),
    ]
    pts = []
    for (label, date, src), names in zip(meta, sets):
        logos = [_logo(n) for n in names]
        pts.append(TimePoint(label=label, target_date=date, source=src,
                             url_used="https://granola.ai" if src == "live" else "",
                             count=len(names), names=names, logos=logos))
    return build_json("granola.ai (demo)", pts)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/scan")
def api_scan():
    data = request.get_json(force=True, silent=True) or {}

    if data.get("demo"):
        return jsonify(_demo_payload())

    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Please enter a website URL."}), 400

    opts = ScanOptions(
        timeline=bool(data.get("timeline", True)),
        since_years=int(data.get("since_years", 5) or 0),
        render=bool(data.get("render", False)),
        months=data.get("months") or [6, 12, 18],
        max_points=int(data.get("max_points", 0) or 0),
        window_days=int(data.get("window_days", 120) or 120),
        timeout=int(data.get("timeout", 25) or 25),
    )
    try:
        domain, points = scan(url, opts)
    except Exception as exc:  # surface a clean message to the browser
        return jsonify({"error": f"Scan failed: {exc}"}), 500

    payload = build_json(domain, points)
    if not any(not p.error for p in points):
        payload["error"] = ("Could not retrieve any pages. The site or the "
                            "Wayback Machine may be unreachable from this server.")
    return jsonify(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="logogrowth-web",
                                     description="Web UI for logogrowth.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)
    print(f"\n  logogrowth web UI → http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
