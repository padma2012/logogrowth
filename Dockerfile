FROM python:3.11-slim

WORKDIR /app

COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

COPY logogrowth ./logogrowth

ENV PORT=8080
EXPOSE 8080

# Shell form so $PORT (set by most hosts) is expanded at runtime.
CMD gunicorn logogrowth.webapp:app --bind 0.0.0.0:${PORT} --timeout 120 --workers 2
