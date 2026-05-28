"""Optional Playwright rendering for JS-heavy pages (used with --render)."""

from __future__ import annotations

from .fetch import DEFAULT_UA


class RenderError(RuntimeError):
    pass


def render_html(url: str, timeout_ms: int = 45000,
                screenshot_path: str | None = None,
                user_agent: str = DEFAULT_UA) -> str:
    """Render `url` in headless Chromium and return the final DOM HTML.

    Raises RenderError if Playwright (or its browser) is not installed.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RenderError(
            "Playwright is not installed. Install it with:\n"
            "    pip install playwright\n"
            "    playwright install chromium"
        ) from exc

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=user_agent,
                                    viewport={"width": 1440, "height": 2400})
            try:
                page.goto(url, wait_until="load", timeout=timeout_ms)
            except Exception:
                # Wayback can be slow; keep whatever rendered so far.
                pass
            page.wait_for_timeout(2000)
            # Scroll to the bottom in steps so lazy-loaded logos render.
            try:
                page.evaluate("""async () => {
                    await new Promise(resolve => {
                        let total = 0;
                        const step = 700;
                        const tick = setInterval(() => {
                            window.scrollBy(0, step);
                            total += step;
                            if (total >= document.body.scrollHeight) {
                                clearInterval(tick);
                                setTimeout(resolve, 900);
                            }
                        }, 220);
                    });
                }""")
            except Exception:
                pass
            page.wait_for_timeout(800)
            html = page.content()
            if screenshot_path:
                page.screenshot(path=screenshot_path, full_page=True)
            browser.close()
            return html
    except RenderError:
        raise
    except Exception as exc:  # pragma: no cover - depends on browser install
        raise RenderError(f"failed to render {url}: {exc}") from exc
