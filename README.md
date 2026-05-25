# logogrowth

Track a SaaS company's **customer/partner logo wall** over time to gauge growth.

Marketing sites for AI/SaaS companies (e.g. [granola.ai](https://granola.ai))
show a "Trusted by…" strip of customer logos. The number of logos is a rough
proxy for how fast the company is landing customers. `logogrowth` scans a site
**now** and at points in the **past** (via the Internet Archive's Wayback
Machine) and reports how the logo count has changed.

```
Logo growth report — granola.ai
============================================================
When            Date        Source           Logos
------------------------------------------------------------
current         2026-05-24  live                42  ████████████████████████
6 months ago    2025-11-24  20251120            28  ████████████████
1 year ago      2025-05-24  20250518            15  █████████
18 months ago   2024-11-24  —                  n/a  (no snapshot near this date)
------------------------------------------------------------
Growth 1 year ago → current: 15 → 42  ▲ +27 (+180%)
  New logos (5): Figma, Linear, Loom, Ramp, Vercel
```

## Install

```bash
pip install -r requirements.txt
# or, to get the `logogrowth` command on your PATH:
pip install -e .
```

Python 3.9+.

## Usage

```bash
# Current site + 6 / 12 / 18 months ago (the defaults)
python -m logogrowth granola.ai

# Custom time points (months ago) and a JSON report
python -m logogrowth granola.ai --months 3 6 9 12 --json report.json

# Walk EVERY monthly Wayback snapshot and chart logo count over time
python -m logogrowth granola.ai --timeline --csv granola_timeline.csv

# Same, but also save a PNG growth chart (needs matplotlib)
python -m logogrowth granola.ai --timeline --chart granola_growth.png

# Limit the timeline to the 12 most recent snapshots
python -m logogrowth granola.ai --timeline --max-points 12

# JSON to stdout, verbose progress on stderr
python -m logogrowth notion.so --json - -v
```

### Timeline mode

`--timeline` ignores `--months` and instead creates one data point for **every
monthly snapshot** the Wayback Machine has, giving a month-by-month growth
curve. Pair it with `--csv` to open the series in a spreadsheet and chart it:

```
When            Date        Source       Logos
2024-11         2024-11-18  20241118        12  ███████
2025-05         2025-05-18  20250518        15  █████████
2025-11         2025-11-20  20251120        28  ████████████████
current         2026-05-24  live            42  ████████████████████████
Growth 2024-11 → current: 12 → 42  ▲ +30 (+250%)
```

Add `--chart growth.png` (after `pip install matplotlib`) to save the same
series as a PNG line chart instead of reading the ASCII bars.

## Web UI (paste a link, get a report)

A polished single-page UI for sharing — paste a company URL and get an
interactive growth chart, a headline like "+180%", new-logo chips, and a data
table.

```bash
pip install flask
python -m logogrowth.webapp           # then open http://127.0.0.1:5000
# options: --host 0.0.0.0 --port 8080
```

Click **"see a sample report"** on the page to view a baked-in demo (works with
no network). A real scan can take up to a minute in timeline mode.

Notes for sharing with others:
- The chart uses Chart.js from a CDN, so the viewer's browser needs internet
  (the page still shows the table if the CDN is blocked).
- The server fetches whatever URL is submitted, so run it locally or behind
  trusted access — don't expose it to the open internet without auth.
- For more than a demo, serve it with a real WSGI server, e.g.
  `gunicorn logogrowth.webapp:app`.

### JS-heavy sites: `--render`

Many modern landing pages render logos with JavaScript, so they aren't in the
raw HTML. Use `--render` to load each page in headless Chromium first:

```bash
pip install playwright && playwright install chromium

python -m logogrowth granola.ai --render --screenshot-dir ./shots
```

`--screenshot-dir` saves a full-page screenshot per time point so you can
eyeball the logo walls yourself.

## How it works

1. **Current page** is fetched live (or rendered with `--render`).
2. **Historical pages** are located through the Wayback Machine CDX API; for
   each requested month offset it picks the archived capture closest to that
   date (within `--window-days`, default 120).
3. Each page is parsed for the logo wall — sections flagged by text labels
   ("Trusted by", "Our customers", …), `class`/`id` hints (`logo-cloud`,
   `brands`, `clients`, …), or, failing those, a dense cluster of images.
   Site chrome (header/nav/footer), social icons, badges, hero shots and
   feature images are filtered out. Logos are de-duplicated and named from
   `alt` text or the image filename.
4. Counts (and best-effort names) are compared across time points.

**Counts are the primary signal; names are best-effort** — filename- and
alt-derived names can be noisy, so treat the added/dropped lists as a hint, not
gospel. For a definitive view use `--render --screenshot-dir`.

## Options

| Flag | Description |
|------|-------------|
| `--months N [N ...]` | Historical offsets in months (default `6 12 18`). |
| `--timeline` | Walk every monthly Wayback snapshot (ignores `--months`). |
| `--max-points N` | In `--timeline`, cap to the N most recent snapshots (0 = all). |
| `--csv PATH` | Write a CSV report (`-` for stdout). |
| `--chart PATH` | Write a PNG line chart of logo count over time (needs matplotlib). |
| `--render` | Render pages with headless Chromium (needs Playwright). |
| `--screenshot-dir DIR` | Save full-page screenshots (requires `--render`). |
| `--json PATH` | Write a JSON report (`-` for stdout). |
| `--window-days N` | Max days a snapshot may deviate from a target date (default 120). |
| `--timeout N` | Per-request timeout in seconds (default 30). |
| `--user-agent UA` | Override the HTTP User-Agent. |
| `-v, --verbose` | Print progress to stderr. |

## Network access

The tool needs outbound HTTPS to **`web.archive.org`** (historical snapshots)
and to the **target domain** (the live/current scan). In a sandboxed
environment with an allowlist, add those hosts or you'll get `403 / Host not
in allowlist` and every data point will report a fetch error.

## Tests

```bash
python tests/test_detect.py
```

Offline tests cover the logo detector and name extraction against a fixture.

## Limitations

- Heuristic detection: a site with an unusual layout may over- or under-count.
  Spot-check with `--render --screenshot-dir`.
- The Wayback Machine doesn't capture every site on every date; gaps show as
  "no snapshot near this date" (widen with `--window-days`).
- Archived pages sometimes fail to capture JS-loaded logos, so very old
  snapshots of JS-heavy sites may undercount.
