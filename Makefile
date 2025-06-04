ifneq ($(shell command -v tput 2> /dev/null),)
    YELLOW := $(shell tput setaf 3)
    GREEN := $(shell tput setaf 2)
    RED := $(shell tput setaf 1)
    BLUE := $(shell tput setaf 4)
    RESET := $(shell tput sgr0)
else
    YELLOW := ""
    GREEN := ""
    RED := ""
    BLUE := ""
    RESET := ""
endif

# Virtual environment directory
VENV := venv

ifdef GITHUB_ACTIONS
  PYTHON := python3
  PIP := pip
  PYTEST := pytest
  RUN_TESTS := python3 run_tests.py
else
  PYTHON := $(VENV)/bin/python3
  PIP := $(VENV)/bin/pip
  PYTEST := $(VENV)/bin/pytest
  RUN_TESTS := $(VENV)/bin/python3 run_tests.py
endif

# Docker image name
IMAGE_NAME := catalog-controller
PORT := $(or $(PORT),7070)

# Test directories
TEST_DIR := tests
UNIT_TEST_DIR := $(TEST_DIR)/unit
INTEGRATION_TEST_DIR := $(TEST_DIR)/integration

.PHONY: help virtualenv clean install activate run docker-build lint ci setup pre-commit clean \
        install-test test test-unit test-integration test-e2e test-coverage test-file test-pattern \
        test-report test-comprehensive test-health test-performance clean-test format security \
        test-all test-verbose test-debug

help:  ## Show this help message
	@echo "$(YELLOW)Available commands:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(RESET) %s\n", $1, $2}'

# Setup virtual environment
virtualenv:  ## Setup the python virtual environment
	@echo "$(BLUE)Setting up virtual environment...$(RESET)"
	@python3 -m venv $(VENV)
	@echo "$(GREEN)Virtual environment created.$(RESET)"

clean:  ## Clean up virtual environment and all temporary files
	@echo "$(RED)Cleaning up...$(RESET)"
	@rm -rf $(VENV) __pycache__ *.pyc *.pyo .pytest_cache .mypy_cache .coverage htmlcov
	@rm -rf .coverage
	@rm -rf htmlcov/
	@rm -rf reports/
	@rm -rf .pytest_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} +
	@find . -name "*.pyc" -delete
	@echo "$(GREEN)Cleanup done.$(RESET)"

install:   ## Install requirements in the virtual environment
	@echo "$(BLUE)Installing requirements...$(RESET)"
	@$(PIP) install -r requirements.txt
	@echo "$(GREEN)Requirements installed.$(RESET)"
	@$(MAKE) pre-commit-setup

# Install test dependencies
install-test:  ## Install test dependencies
	@echo "$(BLUE)Installing test dependencies...$(RESET)"
	@$(PIP) install pytest pytest-asyncio pytest-cov pytest-html
	@echo "$(GREEN)Test dependencies installed.$(RESET)"

pre-commit-setup:  ## Setup pre-commit hooks and generate OpenAPI YAML
	@echo "$(BLUE)Setting up pre-commit hooks...$(RESET)"
	@$(PIP) install pre-commit pyyaml
	@pre-commit install
	cp hooks/pre-commit-config.yaml .pre-commit-config.yaml
	@pre-commit autoupdate
	@echo "$(GREEN)Pre-commit setup complete.$(RESET)"

activate:  ## Activate the virtual environment
	@echo "$(YELLOW)To activate the virtual environment, run:$(RESET)"
	@echo "source $(VENV)/bin/activate"

run:  ## Run the application in the virtual environment
	@echo "$(BLUE)Running the application...$(RESET)"
	fastapi run main.py --port $(PORT)

run-dev:  ## Run the application in the local environment without OTEL
	@echo "$(BLUE)Running the application...$(RESET)"
	fastapi run main.py --port $(PORT)

docker-build:  ## Build the Docker image
	@echo "$(BLUE)Building Docker image...$(RESET)"
	@docker build -t $(IMAGE_NAME) .
	@echo "$(GREEN)Docker image built: $(IMAGE_NAME).$(RESET)"

lint:  ## Lint the application with flake8
	@echo "$(BLUE)Linting the application...$(RESET)"
	@$(VENV)/bin/flake8 . --exclude=$(VENV)
	@$(VENV)/bin/flake8 service/ tests/
	@$(VENV)/bin/black --check service/ tests/
	@$(VENV)/bin/isort --check-only service/ tests/
	@echo "$(GREEN)Linting complete.$(RESET)"

# Format code
format:  ## Format code with black and isort
	@echo "$(BLUE)Formatting code...$(RESET)"
	@$(VENV)/bin/black service/ tests/
	@$(VENV)/bin/isort service/ tests/
	@echo "$(GREEN)Code formatting complete.$(RESET)"

# Security checks
security:  ## Run security checks
	@echo "$(BLUE)Running security checks...$(RESET)"
	@$(VENV)/bin/bandit -r service/
	@$(VENV)/bin/safety check
	@echo "$(GREEN)Security checks complete.$(RESET)"

# ============================================================================
# TEST COMMANDS
# ============================================================================

# Run all tests using the run_tests.py script
test: install-test  ## Run all tests
	@echo "$(BLUE)Running all tests...$(RESET)"
	@$(RUN_TESTS)
	@echo "$(GREEN)All tests completed.$(RESET)"

# Run unit tests only
test-unit: install-test  ## Run unit tests only
	@echo "$(BLUE)Running unit tests...$(RESET)"
	@$(RUN_TESTS) --unit
	@echo "$(GREEN)Unit tests completed.$(RESET)"

# Run integration tests only
test-integration: install-test  ## Run integration tests only
	@echo "$(BLUE)Running integration tests...$(RESET)"
	@$(RUN_TESTS) --integration
	@echo "$(GREEN)Integration tests completed.$(RESET)"

# Run end-to-end tests only
test-e2e: install-test  ## Run end-to-end tests only
	@echo "$(BLUE)Running end-to-end tests...$(RESET)"
	@$(RUN_TESTS) --e2e
	@echo "$(GREEN)End-to-end tests completed.$(RESET)"

# Run comprehensive scenario tests
test-comprehensive: install-test  ## Run comprehensive scenario tests
	@echo "$(BLUE)Running comprehensive scenario tests...$(RESET)"
	@$(PYTEST) tests/test_comprehensive_scenarios.py -v --tb=short --disable-warnings
	@echo "$(GREEN)Comprehensive tests completed.$(RESET)"

# Run tests with coverage
test-coverage: install-test  ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(RESET)"
	@$(RUN_TESTS) --coverage
	@echo "$(GREEN)Coverage report generated in htmlcov/$(RESET)"

# Run tests with HTML coverage report
test-html: install-test  ## Run tests with HTML coverage report
	@echo "$(BLUE)Running tests with HTML coverage...$(RESET)"
	@$(RUN_TESTS) --coverage --html
	@echo "$(GREEN)HTML coverage report generated in htmlcov/$(RESET)"

# Run specific test file
test-file: install-test  ## Run specific test file (usage: make test-file FILE=tests/unit/test_metric.py)
	@echo "$(BLUE)Running test file: $(FILE)...$(RESET)"
	@$(RUN_TESTS) --file $(FILE)
	@echo "$(GREEN)Test file $(FILE) completed.$(RESET)"

# Run tests matching pattern
test-pattern: install-test  ## Run tests matching pattern (usage: make test-pattern PATTERN="metric_sync")
	@echo "$(BLUE)Running tests matching pattern: $(PATTERN)...$(RESET)"
	@$(RUN_TESTS) --pattern "$(PATTERN)"
	@echo "$(GREEN)Pattern tests completed.$(RESET)"

# Run tests and generate HTML report
test-report: install-test  ## Generate HTML test report
	@echo "$(BLUE)Generating test report...$(RESET)"
	@mkdir -p reports
	@$(PYTEST) --html=reports/test-report.html --self-contained-html --tb=short
	@echo "$(GREEN)Test report generated in reports/test-report.html$(RESET)"

# Run health check tests
test-health: install-test  ## Run health check and monitoring tests
	@echo "$(BLUE)Running health check tests...$(RESET)"
	@$(PYTEST) tests/test_comprehensive_scenarios.py::TestHealthAndMonitoring -v --tb=short
	@echo "$(GREEN)Health check tests completed.$(RESET)"

# Run performance tests
test-performance: install-test  ## Run performance tests
	@echo "$(BLUE)Running performance tests...$(RESET)"
	@$(PYTEST) -m "slow" -v --tb=short
	@echo "$(GREEN)Performance tests completed.$(RESET)"

# Run tests in verbose mode
test-verbose: install-test  ## Run tests with verbose output
	@echo "$(BLUE)Running tests with verbose output...$(RESET)"
	@$(RUN_TESTS) --verbose
	@echo "$(GREEN)Verbose tests completed.$(RESET)"

# Run tests with debug output
test-debug: install-test  ## Run tests with debug output
	@echo "$(BLUE)Running tests with debug output...$(RESET)"
	@$(PYTEST) -v -s --tb=long --capture=no
	@echo "$(GREEN)Debug tests completed.$(RESET)"

# Run full test suite with all scenarios
test-all: install-test  ## Run complete test suite (all test types) with coverage
	@echo "$(BLUE)Running complete test suite...$(RESET)"
	@echo "$(YELLOW)1/5: Running unit tests...$(RESET)"
	@$(RUN_TESTS) --unit || true
	@echo "$(YELLOW)2/5: Running integration tests...$(RESET)"
	@$(RUN_TESTS) --integration || true
	@echo "$(YELLOW)3/5: Running end-to-end tests...$(RESET)"
	@$(RUN_TESTS) --e2e || true
	@echo "$(YELLOW)4/5: Running comprehensive tests...$(RESET)"
	@$(PYTEST) tests/test_comprehensive_scenarios.py -v --tb=short --disable-warnings || true
	@echo "$(YELLOW)5/5: Generating coverage report...$(RESET)"
	@$(RUN_TESTS) --coverage --html || true
	@echo "$(GREEN)Complete test suite finished. Check reports for details.$(RESET)"

# Clean test artifacts
clean-test:  ## Clean test artifacts and reports
	@echo "$(BLUE)Cleaning test artifacts...$(RESET)"
	@rm -rf .coverage
	@rm -rf htmlcov/
	@rm -rf reports/
	@rm -rf .pytest_cache/
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@echo "$(GREEN)Test cleanup complete.$(RESET)"

# Quick test for development
test-quick: install-test  ## Quick test run for development (no slow tests)
	@echo "$(BLUE)Running quick tests...$(RESET)"
	@$(PYTEST) -m "not slow" --tb=short --disable-warnings -x
	@echo "$(GREEN)Quick tests completed.$(RESET)"

# Validate test environment
test-validate:  ## Validate test environment setup
	@echo "$(BLUE)Validating test environment...$(RESET)"
	@$(PYTHON) -c "import pytest; import httpx; import fastapi; print('✅ Core test dependencies available')"
	@$(PYTHON) -c "import service.handlers.metric; import service.handlers.scorecard; print('✅ Application modules importable')"
	@$(PYTEST) --collect-only -q
	@echo "$(GREEN)Test environment validation complete.$(RESET)"

# ============================================================================
# COMBINED COMMANDS
# ============================================================================

# CI/CD pipeline - typically used in automation to install, lint, and run the app
ci: clean install lint test-coverage  ## Clean, install, lint, and test with coverage (for CI/CD)

# Setup and run for new developers
setup: virtualenv install install-test  ## Complete setup for new developers

# Pre-commit validation (run before committing)
pre-commit: lint test-quick  ## Run linting and quick tests (for pre-commit)

# Development workflow
dev: clean setup test-quick  ## Complete development setup and validation

# Release preparation
release: clean setup lint test-all security  ## Full validation for release preparation