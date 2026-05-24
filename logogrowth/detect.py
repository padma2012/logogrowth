"""Heuristic detection of customer/partner ("trusted by") logos in HTML.

A SaaS "logo wall" is the section of a marketing site that shows the brands of
customers or partners. This module locates those sections and extracts the
individual logos so they can be counted and named, which lets the caller track
"logo growth" over time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, unquote

from bs4 import BeautifulSoup

# Short text labels that usually sit above a logo wall.
SECTION_TEXT_KEYWORDS = [
    "trusted by", "trusted around", "trusted globally", "our customers",
    "customers", "our clients", "clients", "loved by", "used by", "powering",
    "join thousands", "join the", "teams at", "works with", "in good company",
    "backed by", "from startups to", "the best teams", "who use", "companies",
    "as seen in", "as featured in", "featured in", "press",
]

# class / id fragments that mark a logo-wall container.
CLASS_SECTION_RE = re.compile(
    r"(logo|brand|client|customer|compan|partner|marquee|trusted|"
    r"press[-_]|as[-_]?seen|featured)",
    re.I,
)

KEYWORD_RE = re.compile("|".join(re.escape(k) for k in SECTION_TEXT_KEYWORDS), re.I)

# Substrings in src/alt that mean an image is NOT a customer logo.
NEGATIVE_HINTS = [
    "favicon", "avatar", "twitter", "x-logo", "linkedin", "facebook",
    "instagram", "youtube", "tiktok", "social", "app-store", "appstore",
    "google-play", "play-store", "badge", "arrow", "chevron", "caret",
    "star", "rating", "quote", "emoji", "flag-", "spinner", "loading",
    "placeholder", "sprite", "pattern", "gradient", "blur", "hero-",
    "screenshot", "product-shot", "feature-", "avatar", "headshot",
]

# Tag names / class fragments that are site chrome, not a logo wall.
CHROME_TAGS = {"header", "nav", "footer"}
CHROME_CLASS_RE = re.compile(r"(navbar|nav-|header|footer|menu|cookie|banner)", re.I)

_WAYBACK_PREFIX = re.compile(r"^https?://web\.archive\.org/web/\d+(?:[a-z]{2}_)?/", re.I)

# Tokens stripped from logo filenames before deriving a company name.
_FILENAME_NOISE = re.compile(
    r"\b(logo|logos|logotype|wordmark|colou?r|white|dark|light|black|gray|grey|"
    r"mono|brand|full|horizontal|vertical|symbol|mark|inverted|primary|"
    r"secondary|small|large|2x|3x)\b",
    re.I,
)
_ALT_NOISE = re.compile(r"\b(logo|logotype|wordmark)\b", re.I)
_IMG_EXT = re.compile(r"\.(svg|png|jpe?g|webp|gif|avif)$", re.I)
_HEXISH = re.compile(r"^[0-9a-f]{8,}$", re.I)


@dataclass
class Logo:
    name: str
    src: str
    kind: str          # "img" | "svg" | "bg"
    source_hint: str   # how the logo was found, for debugging

    def key(self) -> str:
        if self.name:
            return "name:" + self.name.lower()
        if self.src:
            return "src:" + self.src.rsplit("/", 1)[-1].lower()
        return "src:" + self.src.lower()


@dataclass
class DetectionResult:
    logos: list[Logo] = field(default_factory=list)
    sections_found: int = 0

    @property
    def count(self) -> int:
        return len(self.logos)

    @property
    def names(self) -> list[str]:
        return sorted({lg.name for lg in self.logos if lg.name})


def strip_wayback(url: str) -> str:
    return _WAYBACK_PREFIX.sub("", url.strip())


def _absolutize(src: str, base_url: str) -> str:
    src = strip_wayback(src)
    if src.startswith("//"):
        return "https:" + src
    if re.match(r"^https?://", src):
        return src
    if base_url:
        try:
            return urljoin(base_url, src)
        except ValueError:
            return src
    return src


def _name_from_filename(src: str) -> str:
    if not src:
        return ""
    base = unquote(urlparse(src).path.rsplit("/", 1)[-1])
    base = _IMG_EXT.sub("", base)
    base = re.sub(r"[-_]+", " ", base)
    base = re.sub(r"\b\d+x\d+\b", " ", base)
    base = _FILENAME_NOISE.sub(" ", base)
    base = re.sub(r"\s+", " ", base).strip()
    if not base or _HEXISH.match(base.replace(" ", "")):
        return ""
    return base.title()


def _clean_alt(alt: str) -> str:
    a = _ALT_NOISE.sub("", alt or "")
    a = re.sub(r"\s+", " ", a).strip(" -|:–—")
    return a


def _in_chrome(el) -> bool:
    cur = el
    for _ in range(8):
        if cur is None or getattr(cur, "name", None) is None:
            break
        if cur.name in CHROME_TAGS:
            return True
        cls = " ".join(cur.get("class", []) or []) + " " + (cur.get("id") or "")
        if cls.strip() and CHROME_CLASS_RE.search(cls):
            return True
        cur = cur.parent
    return False


def _img_src(img) -> str:
    for attr in ("src", "data-src", "data-lazy-src", "data-original",
                 "data-srcset", "srcset"):
        v = img.get(attr)
        if v:
            v = v.split(",")[0].strip().split(" ")[0].strip()
            if v:
                return v
    return ""


def _svg_name(svg) -> str:
    title = svg.find("title")
    if title and title.get_text(strip=True):
        return title.get_text(strip=True)
    for attr in ("aria-label", "data-name", "title"):
        if svg.get(attr):
            return svg.get(attr)
    return ""


def _build_logo(el, base_url: str, hint: str) -> Logo | None:
    if el.name == "svg":
        name = _clean_alt(_svg_name(el))
        if not name:
            return None
        return Logo(name=name, src="", kind="svg", source_hint=hint)

    raw = _img_src(el)
    alt = el.get("alt") or el.get("aria-label") or el.get("title") or ""
    haystack = (raw + " " + alt).lower()
    if any(h in haystack for h in NEGATIVE_HINTS):
        return None

    name = _clean_alt(alt)
    src_abs = ""
    if raw and not raw.startswith("data:"):
        src_abs = _absolutize(raw, base_url)
        if not name:
            name = _name_from_filename(src_abs)
    if not name and not src_abs:
        return None
    return Logo(name=name, src=src_abs, kind="img", source_hint=hint)


_BG_RE = re.compile(r"background(?:-image)?\s*:\s*url\(['\"]?([^'\")]+)", re.I)


def _bg_logos(container, base_url: str, hint: str):
    for el in container.find_all(style=True):
        m = _BG_RE.search(el.get("style", ""))
        if not m:
            continue
        raw = m.group(1)
        if raw.startswith("data:"):
            continue
        if any(h in raw.lower() for h in NEGATIVE_HINTS):
            continue
        src_abs = _absolutize(raw, base_url)
        name = _name_from_filename(src_abs)
        if name or src_abs:
            yield Logo(name=name, src=src_abs, kind="bg", source_hint=hint)


def _nearest_container(el):
    cur = el
    for _ in range(6):
        if cur is None or getattr(cur, "name", None) is None:
            break
        if cur.name in ("section", "div", "ul", "ol", "figure", "aside", "main"):
            if len(cur.find_all(["img", "svg"])) >= 2:
                return cur
        cur = cur.parent
    return el.parent if el.parent is not None else el


def _find_containers(soup) -> list[tuple[object, str]]:
    out: list[tuple[object, str]] = []
    seen: set[int] = set()

    def add(el, hint):
        if el is None or id(el) in seen or _in_chrome(el):
            return
        seen.add(id(el))
        out.append((el, hint))

    # 1. class / id signals
    for el in soup.find_all(attrs={"class": True}):
        cls = " ".join(el.get("class", []) or [])
        if CLASS_SECTION_RE.search(cls):
            add(el, "class")
    for el in soup.find_all(id=CLASS_SECTION_RE):
        add(el, "id")

    # 2. nearby text labels ("Trusted by ...")
    for text in soup.find_all(string=KEYWORD_RE):
        snippet = text.strip()
        if len(snippet) > 90:  # long paragraph, not a section label
            continue
        parent = text.parent
        if parent is None:
            continue
        add(_nearest_container(parent), "keyword")

    # 3. fallback: dense image clusters when nothing above matched
    if not out:
        for el in soup.find_all(["section", "div", "ul"]):
            if _in_chrome(el):
                continue
            if len(el.find_all("img", recursive=True)) >= 4:
                add(el, "cluster")

    return out


def detect_logos(html: str, base_url: str = "") -> DetectionResult:
    """Parse `html` and return the customer/partner logos it advertises."""
    soup = BeautifulSoup(html or "", "html.parser")
    containers = _find_containers(soup)

    found: dict[str, Logo] = {}
    for container, hint in containers:
        for el in container.find_all(["img", "svg"], recursive=True):
            if _in_chrome(el):
                continue
            logo = _build_logo(el, base_url, hint)
            if logo is None:
                continue
            found.setdefault(logo.key(), logo)
        for logo in _bg_logos(container, base_url, hint):
            found.setdefault(logo.key(), logo)

    return DetectionResult(logos=list(found.values()), sections_found=len(containers))
