# -------------------------------------------------------------
# BorderWise AI: Google Cloud Run Container Specification
# Optimized for Always-Free Tier ($0.00 / Month)
# -------------------------------------------------------------
FROM python:3.12-slim

# Prevent Python from writing .pyc files & enable unbuffered streaming logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency requirements & install
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source and database
COPY backend /app/backend
COPY evals /app/evals
COPY web /app/web
COPY extension /app/extension

# Expose server port
EXPOSE 8080

# Cloud Run healthcheck & launch using high-performance Uvicorn ASGI
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
