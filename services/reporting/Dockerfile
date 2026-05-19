# Multi-stage build for Python reporting service
FROM python:3.11-slim as builder

# Install system dependencies (including WeasyPrint requirements)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libsnappy-dev \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-dev \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

# Install runtime dependencies (including WeasyPrint runtime libs)
RUN apt-get update && apt-get install -y \
    libpq5 \
    libsnappy1v5 \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Run as non-root user - create user first
RUN addgroup --gid 1000 helios && \
    adduser --disabled-password --gecos '' --uid 1000 --gid 1000 helios

# Copy Python packages from builder to helios user location
COPY --from=builder --chown=helios:helios /root/.local /home/helios/.local

# Make sure scripts in .local are usable
ENV PATH=/home/helios/.local/bin:$PATH

# Copy application code
COPY --chown=helios:helios app/ ./app/

# Create reports directory
RUN mkdir -p /app/reports && chown -R helios:helios /app

USER helios

# Expose ports
EXPOSE 8002 8003

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8002/health')" || exit 1

# Default command (can be overridden)
CMD ["python", "-m", "app.main"]
