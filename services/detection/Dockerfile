# Build stage
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libsnappy-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies for snappy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsnappy1v5 \
    && rm -rf /var/lib/apt/lists/*

# Run as non-root user - create user first
RUN addgroup --gid 1000 helios && \
    adduser --disabled-password --gecos '' --uid 1000 --gid 1000 helios

# Copy Python dependencies from builder to helios user location
COPY --from=builder --chown=helios:helios /root/.local /home/helios/.local

# Make sure scripts in .local are usable
ENV PATH=/home/helios/.local/bin:$PATH

# Copy application code
COPY --chown=helios:helios . .

# Create directory for ML models
RUN mkdir -p /app/models && chown -R helios:helios /app

# Expose ports
EXPOSE 8000

# Health check — hits the real FastAPI mount under /api/v1/
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=2).status == 200 else 1)" || exit 1

USER helios

# Run the FastAPI app. Compose may override this for the detection-consumer
# variant to run `python -m app.consumers.detection_consumer`.
CMD ["python", "-m", "app.main"]
