# Pinned Python runtime for Railway / local Docker.
FROM python:3.12.8-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    MCP_TRANSPORT_HOST=0.0.0.0 \
    GARMINTOKENS=/data/garth

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

RUN mkdir -p /data/garth && chmod 700 /data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, urllib.request; port=os.environ.get('PORT','8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=4)"

CMD ["python", "-m", "garmin_mcp.server"]
