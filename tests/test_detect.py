import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from logogrowth.detect import detect_logos, _name_from_filename, strip_wayback

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample.html")


def _load():
    with open(FIXTURE, encoding="utf-8") as fh:
        return fh.read()


def test_counts_customer_logos_only():
    res = detect_logos(_load(), base_url="https://acme.ai")
    names = res.names
    # 5 distinct customer logos (Stripe appears twice -> deduped).
    assert res.count == 5, f"got {res.count}: {names}"
    assert set(names) == {"Stripe", "Notion", "Ramp", "Vercel", "Linear"}


def test_excludes_chrome_and_icons():
    names = detect_logos(_load(), base_url="https://acme.ai").names
    assert "Acme Ai" not in names          # header/footer brand logo
    assert "Twitter" not in names           # social icon in nav
    assert "Linkedin" not in names          # social icon in footer


def test_excludes_feature_and_hero_images():
    names = detect_logos(_load()).names
    assert not any("screenshot" in n.lower() for n in names)
    assert not any("feature" in n.lower() for n in names)


def test_name_from_filename():
    assert _name_from_filename("https://x.com/logos/stripe-logo.svg") == "Stripe"
    assert _name_from_filename("/logos/ramp-color.png") == "Ramp"
    assert _name_from_filename("/logos/acme-logo-white.svg") == "Acme"
    assert _name_from_filename("/i/9f8a7b6c5d4e.png") == ""


def test_strip_wayback():
    u = "https://web.archive.org/web/20230101000000im_/https://acme.ai/logo.svg"
    assert strip_wayback(u) == "https://acme.ai/logo.svg"


def test_empty_html():
    res = detect_logos("")
    assert res.count == 0


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
