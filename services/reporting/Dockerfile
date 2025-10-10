# Multi-stage build for Python reporting service
FROM python:3.11-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY app/ ./app/

# Create reports directory
RUN mkdir -p /app/reports

# Run as non-root user
RUN addgroup --gid 1000 helios && \
    adduser --disabled-password --gecos '' --uid 1000 --gid 1000 helios && \
    chown -R helios:helios /app

USER helios

# Expose ports
EXPOSE 8002 8003

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8002/health')" || exit 1

# Default command (can be overridden)
CMD ["python", "-m", "app.main"]
