# Inbound free-check API (spec §6). Build context = repo root:
#   docker build -f server/Dockerfile -t geo-check-api .
FROM python:3.12-slim

WORKDIR /app

# deps first for layer caching
COPY server/requirements-server.txt server/requirements-server.txt
RUN pip install --no-cache-dir -r server/requirements-server.txt

# the API imports the check engine from scripts/ and renders into reports/
COPY scripts/ scripts/
COPY server/ server/

ENV PORT=8000
EXPOSE 8000

# GEO_SLAB_DB should point at a mounted volume in prod so leads persist.
# CHECK_API_TOKEN + OPENROUTER_API_KEY are required; BREVO_* + REPORT_BASE optional.
WORKDIR /app/server
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "--timeout", "120", "check_api:app"]
