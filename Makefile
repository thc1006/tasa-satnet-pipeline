# TASA SatNet Pipeline - Makefile

.PHONY: help setup test parse scenario metrics schedule clean lint typecheck all docker-build docker-run k8s-deploy k8s-clean

# Default target
help:
	@echo "TASA SatNet Pipeline - Available Commands:"
	@echo ""
	@echo "  make setup       - Create venv and install dependencies"
	@echo "  make test        - Run all tests with coverage"
	@echo "  make parse       - Parse sample OASIS log"
	@echo "  make scenario    - Generate NS-3 scenario from parsed data"
	@echo "  make metrics     - Calculate KPIs from scenario"
	@echo "  make schedule    - Run beam scheduler"
	@echo "  make lint        - Run code linters (flake8, black)"
	@echo "  make typecheck   - Run mypy type checking"
	@echo "  make clean       - Remove generated files and caches"
	@echo "  make all         - Run full pipeline (parse -> scenario -> metrics)"
	@echo "  make docker-build- Build the tasa-satnet-pipeline:latest image"
	@echo "  make docker-run  - Run the image's healthcheck once"
	@echo "  make k8s-deploy  - Build, import to containerd, apply ns/configmap/job-test-real"
	@echo "  make k8s-clean   - Remove k8s resources created by k8s-deploy"
	@echo ""

# Python and venv settings
PYTHON := python3
VENV := venv
BIN := $(VENV)/bin
PIP := $(BIN)/pip
PYTEST := $(BIN)/pytest
MYPY := $(BIN)/mypy
BLACK := $(BIN)/black
FLAKE8 := $(BIN)/flake8

# Directories
SCRIPTS := scripts
DATA := data
CONFIG := config
REPORTS := reports
TESTS := tests

# Files
SAMPLE_LOG := $(DATA)/sample_oasis.log
WINDOWS_JSON := $(DATA)/oasis_windows.json
SCENARIO_JSON := $(CONFIG)/ns3_scenario.json
METRICS_CSV := $(REPORTS)/metrics.csv
SCHEDULE_CSV := $(REPORTS)/schedule.csv

# Setup virtual environment and install dependencies
setup:
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	@echo "Installing dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "Setup complete! Activate with: source $(BIN)/activate"

# Run tests with coverage
test:
	@echo "Running tests with coverage..."
	$(PYTEST) $(TESTS)/ -v --cov=$(SCRIPTS) --cov-report=term-missing --cov-report=html
	@echo "Coverage report generated in htmlcov/"

# Run tests with benchmarks
test-bench:
	@echo "Running benchmark tests..."
	$(PYTEST) $(TESTS)/ -v --benchmark-only

# Parse OASIS log
parse:
	@echo "Parsing OASIS log..."
	@if [ ! -f $(SAMPLE_LOG) ]; then \
		echo "Error: $(SAMPLE_LOG) not found!"; \
		exit 1; \
	fi
	$(BIN)/python $(SCRIPTS)/parse_oasis_log.py $(SAMPLE_LOG) -o $(WINDOWS_JSON)
	@echo "Output: $(WINDOWS_JSON)"

# Generate scenario from parsed windows
scenario: $(WINDOWS_JSON)
	@echo "Generating NS-3 scenario..."
	$(BIN)/python $(SCRIPTS)/gen_scenario.py $(WINDOWS_JSON) -o $(SCENARIO_JSON)
	@echo "Output: $(SCENARIO_JSON)"

# Calculate metrics from scenario
metrics: $(SCENARIO_JSON)
	@echo "Calculating KPIs..."
	$(BIN)/python $(SCRIPTS)/metrics.py $(SCENARIO_JSON) -o $(METRICS_CSV)
	@echo "Output: $(METRICS_CSV)"

# Run beam scheduler
schedule: $(SCENARIO_JSON)
	@echo "Running beam scheduler..."
	$(BIN)/python $(SCRIPTS)/scheduler.py $(SCENARIO_JSON) -o $(SCHEDULE_CSV)
	@echo "Output: $(SCHEDULE_CSV)"

# Run code linters
lint:
	@echo "Running flake8..."
	-$(FLAKE8) $(SCRIPTS) $(TESTS) --max-line-length=100
	@echo "Running black (check only)..."
	-$(BLACK) --check $(SCRIPTS) $(TESTS)
	@echo "Running isort (check only)..."
	-$(BIN)/isort --check-only $(SCRIPTS) $(TESTS)

# Fix code formatting
format:
	@echo "Formatting code with black..."
	$(BLACK) $(SCRIPTS) $(TESTS)
	@echo "Sorting imports with isort..."
	$(BIN)/isort $(SCRIPTS) $(TESTS)

# Run type checking
typecheck:
	@echo "Running mypy type checker..."
	$(MYPY) $(SCRIPTS) --strict --ignore-missing-imports

# Run full pipeline
all: parse scenario metrics
	@echo "Full pipeline complete!"
	@echo "Results:"
	@echo "  - Windows: $(WINDOWS_JSON)"
	@echo "  - Scenario: $(SCENARIO_JSON)"
	@echo "  - Metrics: $(METRICS_CSV)"

# Build Docker image
docker-build:
	@echo "Building Docker image..."
	docker build -t tasa-satnet-pipeline:latest .
	@docker images tasa-satnet-pipeline:latest

# Run pipeline once in a one-shot container
docker-run: docker-build
	docker run --rm tasa-satnet-pipeline:latest python scripts/healthcheck.py

# Deploy job-test-real to current kubectl context.
# On clusters where the runtime is NOT Docker (e.g. kubeadm + containerd),
# the image must be present in the cluster's image store. This target handles
# the common case (containerd k8s.io namespace) by saving and importing.
# For Docker Desktop / minikube docker-env, this import is a no-op-ish but harmless.
k8s-deploy: docker-build
	@echo "Importing image into containerd k8s.io namespace (skipped if no ctr)..."
	@if command -v ctr >/dev/null 2>&1; then \
		docker save tasa-satnet-pipeline:latest -o /tmp/tasa-satnet-pipeline.tar; \
		sudo ctr --namespace=k8s.io images import /tmp/tasa-satnet-pipeline.tar; \
		rm -f /tmp/tasa-satnet-pipeline.tar; \
	else \
		echo "ctr not found; assuming docker-shim or registry handles image distribution"; \
	fi
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/configmap.yaml
	kubectl apply -f k8s/job-test-real.yaml
	@echo "Deployed. Tail logs with: kubectl logs -n tasa-satnet job/tasa-test-pipeline -f"

# Tear down k8s resources
k8s-clean:
	-kubectl delete -f k8s/job-test-real.yaml --ignore-not-found
	-kubectl delete -f k8s/job-integrated-pipeline.yaml --ignore-not-found
	-kubectl delete -f k8s/configmap.yaml --ignore-not-found
	-kubectl delete -f k8s/namespace.yaml --ignore-not-found

# Clean generated files and caches
clean:
	@echo "Cleaning up..."
	rm -rf $(VENV)
	rm -rf __pycache__ .pytest_cache .mypy_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.egg-info" -exec rm -rf {} +
	@echo "Clean complete!"

# Create necessary directories
dirs:
	@mkdir -p $(DATA) $(CONFIG) $(REPORTS) $(TESTS)

# Check if venv exists
check-venv:
	@if [ ! -d $(VENV) ]; then \
		echo "Error: Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi

# Ensure targets depend on venv
$(WINDOWS_JSON): check-venv
$(SCENARIO_JSON): check-venv
$(METRICS_CSV): check-venv
$(SCHEDULE_CSV): check-venv
