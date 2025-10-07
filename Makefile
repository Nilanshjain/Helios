.PHONY: help build test clean up down logs ps restart

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

## help: Display this help message
help:
	@echo "$(BLUE)Helios - Available Commands:$(NC)"
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  /' | column -t -s ':'

## setup: Initial project setup (install dependencies, create configs)
setup:
	@echo "$(GREEN)Setting up Helios project...$(NC)"
	@./scripts/setup.sh

## build: Build all Docker images
build:
	@echo "$(GREEN)Building Docker images...$(NC)"
	docker-compose build

## build-go: Build Go ingestion service
build-go:
	@echo "$(GREEN)Building Go ingestion service...$(NC)"
	cd services/ingestion && go build -o ingestion .

## build-python: Build Python detection service
build-python:
	@echo "$(GREEN)Setting up Python environment...$(NC)"
	cd services/detection && poetry install

## up: Start all services
up:
	@echo "$(GREEN)Starting all services...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)Services started!$(NC)"
	@echo "Ingestion API: http://localhost:8080"
	@echo "Kafka UI: http://localhost:9000"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Prometheus: http://localhost:9090"

## down: Stop all services
down:
	@echo "$(YELLOW)Stopping all services...$(NC)"
	docker-compose down

## down-volumes: Stop all services and remove volumes
down-volumes:
	@echo "$(RED)Stopping all services and removing volumes...$(NC)"
	docker-compose down -v

## restart: Restart all services
restart: down up

## logs: Tail logs from all services
logs:
	docker-compose logs -f

## logs-ingestion: Tail logs from ingestion service
logs-ingestion:
	docker-compose logs -f ingestion

## logs-detection: Tail logs from detection service
logs-detection:
	docker-compose logs -f detection

## logs-kafka: Tail logs from Kafka
logs-kafka:
	docker-compose logs -f kafka

## ps: Show status of all services
ps:
	docker-compose ps

## test: Run all tests
test: test-unit test-integration

## test-unit: Run unit tests
test-unit:
	@echo "$(GREEN)Running unit tests...$(NC)"
	@echo "Testing Go services..."
	cd services/ingestion && go test -v -cover ./...
	@echo "Testing Python services..."
	cd services/detection && poetry run pytest tests/unit -v

## test-integration: Run integration tests
test-integration:
	@echo "$(GREEN)Running integration tests...$(NC)"
	cd services/detection && poetry run pytest tests/integration -v

## test-load: Run load tests (requires running services)
test-load:
	@echo "$(YELLOW)Running load tests...$(NC)"
	@echo "Make sure services are running (make up)"
	cd scripts && python load_test.py

## coverage: Generate test coverage reports
coverage:
	@echo "$(GREEN)Generating coverage reports...$(NC)"
	cd services/ingestion && go test -coverprofile=coverage.out ./... && go tool cover -html=coverage.out -o coverage.html
	cd services/detection && poetry run pytest --cov=. --cov-report=html

## lint: Run linters on all code
lint:
	@echo "$(GREEN)Running linters...$(NC)"
	cd services/ingestion && golangci-lint run ./...
	cd services/detection && poetry run flake8 . && poetry run black --check . && poetry run mypy .

## format: Format code
format:
	@echo "$(GREEN)Formatting code...$(NC)"
	cd services/ingestion && gofmt -w .
	cd services/detection && poetry run black . && poetry run isort .

## generate-events: Generate synthetic events for testing
generate-events:
	@echo "$(GREEN)Generating synthetic events...$(NC)"
	cd scripts && go run generate_events.go

## seed-data: Seed database with test data
seed-data:
	@echo "$(GREEN)Seeding database with test data...$(NC)"
	./scripts/seed_data.sh

## train-model: Train anomaly detection model
train-model:
	@echo "$(GREEN)Training ML model...$(NC)"
	cd services/detection && poetry run python -m models.train

## db-shell: Open PostgreSQL shell
db-shell:
	docker exec -it helios-timescaledb psql -U postgres -d helios

## kafka-topics: List Kafka topics
kafka-topics:
	docker exec helios-kafka kafka-topics --bootstrap-server localhost:9092 --list

## kafka-create-topics: Create required Kafka topics
kafka-create-topics:
	@echo "$(GREEN)Creating Kafka topics...$(NC)"
	docker exec helios-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic events --partitions 10 --replication-factor 1 --if-not-exists
	docker exec helios-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic metrics --partitions 10 --replication-factor 1 --if-not-exists
	docker exec helios-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic traces --partitions 10 --replication-factor 1 --if-not-exists
	docker exec helios-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic anomaly-alerts --partitions 10 --replication-factor 1 --if-not-exists

## kafka-consume-events: Consume events from Kafka (Ctrl+C to stop)
kafka-consume-events:
	docker exec -it helios-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic events --from-beginning

## kafka-consume-anomalies: Consume anomalies from Kafka (Ctrl+C to stop)
kafka-consume-anomalies:
	docker exec -it helios-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic anomaly-alerts --from-beginning

## clean: Clean build artifacts
clean:
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	rm -f services/ingestion/ingestion
	rm -f services/ingestion/coverage.out
	rm -f services/ingestion/coverage.html
	rm -rf services/detection/.pytest_cache
	rm -rf services/detection/htmlcov
	rm -rf services/detection/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

## tf-init: Initialize Terraform
tf-init:
	cd infrastructure/terraform/environments/dev && terraform init

## tf-plan: Terraform plan for dev environment
tf-plan:
	cd infrastructure/terraform/environments/dev && terraform plan

## tf-apply: Apply Terraform changes for dev environment
tf-apply:
	cd infrastructure/terraform/environments/dev && terraform apply

## tf-destroy: Destroy Terraform infrastructure
tf-destroy:
	@echo "$(RED)WARNING: This will destroy all infrastructure!$(NC)"
	cd infrastructure/terraform/environments/dev && terraform destroy

## k8s-deploy: Deploy to Kubernetes
k8s-deploy:
	kubectl apply -f infrastructure/k8s/

## k8s-delete: Delete from Kubernetes
k8s-delete:
	kubectl delete -f infrastructure/k8s/

## docker-prune: Remove unused Docker resources
docker-prune:
	@echo "$(YELLOW)Pruning Docker resources...$(NC)"
	docker system prune -af --volumes

## benchmark: Run performance benchmarks
benchmark:
	@echo "$(GREEN)Running benchmarks...$(NC)"
	cd services/ingestion && go test -bench=. -benchmem ./...

## metrics: Show current system metrics
metrics:
	@echo "$(BLUE)=== System Metrics ===$(NC)"
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana: http://localhost:3000"
	@curl -s http://localhost:8081/metrics | grep -E "^helios_" | head -20

## health: Check health of all services
health:
	@echo "$(BLUE)=== Service Health Check ===$(NC)"
	@echo "Ingestion API:"
	@curl -s http://localhost:8080/health || echo "$(RED)DOWN$(NC)"
	@echo "\nDetection API:"
	@curl -s http://localhost:8000/health || echo "$(RED)DOWN$(NC)"
	@echo "\nPrometheus:"
	@curl -s http://localhost:9090/-/healthy || echo "$(RED)DOWN$(NC)"
	@echo "\nKafka:"
	@docker exec helios-kafka kafka-broker-api-versions --bootstrap-server localhost:9092 > /dev/null 2>&1 && echo "$(GREEN)UP$(NC)" || echo "$(RED)DOWN$(NC)"

## install-tools: Install development tools
install-tools:
	@echo "$(GREEN)Installing development tools...$(NC)"
	go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
	curl -sSfL https://install.python-poetry.org | python3 -

## docs: Generate documentation
docs:
	@echo "$(GREEN)Generating documentation...$(NC)"
	cd services/ingestion && godoc -http=:6060 &
	@echo "Go docs available at http://localhost:6060"
