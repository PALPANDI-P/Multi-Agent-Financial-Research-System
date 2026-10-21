# =============================================================================
# Multi-Agent Financial Research System - backend image
# =============================================================================
# Build from the repository root (the build context is the repository root so
# that the seed corpus next to `backend/` can be copied into the image):
#
#     docker build -t frs-backend:local -f backend/Dockerfile .
#
# The image contains the application package, the Alembic migrations and the
# seed manifest.  It runs as a non-root user and starts with the migration
# and the API server:
#
#     alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
#
# NOTE: this image was AUTHORED but never BUILT on the development machine
# (Docker is not installed there).  See README.md.
# =============================================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# libgomp1 is required by the ONNX runtime that the local embedding model
# uses; the rest keeps the image small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# The project metadata and the sources.  The dependencies are resolved by
# `pip install .` from pyproject.toml.
COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini
COPY backend/scripts ./scripts

# The seed corpus: the manifest that pins the source URL and the SHA-256
# checksum of every seed document.  The documents themselves are downloaded
# by the loader, they are not baked into the image.
COPY data/seed_manifest.json ./seed_manifest.json

RUN pip install --no-cache-dir .

# The non-root user that owns the application and the storage directory.
RUN groupadd --system --gid 1001 frs \
    && useradd --system --uid 1001 --gid frs --home-dir /app --shell /usr/sbin/nologin frs \
    && mkdir -p /app/data/storage /var/lib/frs/storage \
    && chown -R frs:frs /app /var/lib/frs

USER frs

# The document storage.  In the compose stack this path is a named volume.
ENV STORAGE_ROOT=/var/lib/frs/storage \
    SEED_MANIFEST_PATH=/app/seed_manifest.json \
    SEED_DOCUMENTS_DIR=/app/seed_documents

EXPOSE 8000

# The health endpoint always answers with HTTP 200 - a degraded dependency is
# reported in the body, not in the status code.
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=5).status == 200 else 1)"]

# The documented start command: migrate first, then serve.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
