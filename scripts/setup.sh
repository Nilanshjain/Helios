#!/bin/bash

# Helios Setup Script
# Initializes the development environment

set -e  # Exit on error

echo "======================================"
echo "  Helios - Setup Script"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running on Windows (Git Bash)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo -e "${YELLOW}Detected Windows environment${NC}"
    IS_WINDOWS=true
else
    IS_WINDOWS=false
fi

# Function to print success messages
success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to print warning messages
warning() {
    echo -e "${YELLOW}!${NC} $1"
}

# Function to print error messages
error() {
    echo -e "${RED}✗${NC} $1"
}

# Check Docker
echo "Checking prerequisites..."
if command -v docker &> /dev/null; then
    success "Docker is installed ($(docker --version))"
else
    error "Docker is not installed. Please install Docker Desktop first."
    exit 1
fi

# Check Docker Compose
if command -v docker-compose &> /dev/null; then
    success "Docker Compose is installed ($(docker-compose --version))"
else
    error "Docker Compose is not installed."
    exit 1
fi

# Check Go (optional)
if command -v go &> /dev/null; then
    success "Go is installed ($(go version))"
else
    warning "Go is not installed (optional for local development)"
fi

# Check Python (optional)
if command -v python3 &> /dev/null; then
    success "Python 3 is installed ($(python3 --version))"
else
    warning "Python 3 is not installed (optional for local development)"
fi

echo ""
echo "Creating configuration files..."

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Helios Environment Configuration

# Kafka Configuration
KAFKA_BROKERS=localhost:9092
KAFKA_TOPIC=events

# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=helios
DB_USER=postgres
DB_PASSWORD=postgres

# Service Ports
SERVER_PORT=8080
METRICS_PORT=8081

# Logging
LOG_LEVEL=info

# OpenAI API (for reporting service)
OPENAI_API_KEY=your-api-key-here

# AWS Configuration (for production)
AWS_REGION=us-east-1
REPORT_S3_BUCKET=helios-incident-reports
EOF
    success "Created .env file"
else
    warning ".env file already exists, skipping"
fi

# Create Prometheus configuration
mkdir -p config/prometheus
if [ ! -f config/prometheus/prometheus.yml ]; then
    cat > config/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'helios-ingestion'
    static_configs:
      - targets: ['ingestion:8081']
        labels:
          service: 'ingestion'

  - job_name: 'helios-detection'
    static_configs:
      - targets: ['detection:8000']
        labels:
          service: 'detection'

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
EOF
    success "Created Prometheus configuration"
else
    warning "Prometheus config already exists, skipping"
fi

# Create Grafana datasources directory
mkdir -p config/grafana/datasources
mkdir -p config/grafana/dashboards

echo ""
echo "Initializing services..."

# Pull Docker images
echo "Pulling Docker images (this may take a few minutes)..."
docker-compose pull

success "Docker images pulled successfully"

echo ""
echo -e "${GREEN}======================================"
echo "  Setup Complete!"
echo "======================================${NC}"
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your OpenAI API key (if using reporting service)"
echo "2. Start services: docker-compose up -d"
echo "3. View logs: docker-compose logs -f"
echo "4. Access services:"
echo "   - Ingestion API: http://localhost:8080"
echo "   - Kafka UI: http://localhost:9000"
echo "   - Grafana: http://localhost:3000 (admin/admin)"
echo "   - Prometheus: http://localhost:9090"
echo ""
echo "For more information, see README.md"
echo ""
