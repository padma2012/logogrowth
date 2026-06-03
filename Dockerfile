FROM python:3.11-slim

WORKDIR /app

# Install Python deps, then Playwright + Chromium with its system deps.
# Chromium is what powers the "Render JS" option in the UI — JS-heavy sites
# (Webflow, Framer, etc.) need it or most logos are missed.
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt playwright \
 && playwright install --with-deps chromium

COPY logogrowth ./logogrowth

ENV PORT=8080 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

EXPOSE 8080

# Single worker + long timeout: scans can take a while, and Chromium is
# memory-hungry on small hosts (Render free tier = 512 MB).
CMD gunicorn logogrowth.webapp:app --bind 0.0.0.0:${PORT} --timeout 300 --workers 1
