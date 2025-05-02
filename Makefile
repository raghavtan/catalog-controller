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

# Python commands
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

# Docker image name
IMAGE_NAME := catalog-controller
PORT := $(or $(PORT),7070)

# Test directories
TEST_DIR := tests
UNIT_TEST_DIR := $(TEST_DIR)/unit
INTEGRATION_TEST_DIR := $(TEST_DIR)/integration

.PHONY: help virtualenv clean install activate run docker-build lint ci setup pre-commit test test-unit test-integration test-coverage

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
	@find . -name "__pycache__" -type d -exec rm -rf {} +
	@find . -name "*.pyc" -delete
	@echo "$(GREEN)Cleanup done.$(RESET)"

install:   ## Install requirements in the virtual environment
	@echo "$(BLUE)Installing requirements...$(RESET)"
	@$(PIP) install -r requirements.txt
	@echo "$(GREEN)Requirements installed.$(RESET)"
	@$(MAKE) pre-commit-setup

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
	@echo "$(GREEN)Linting complete.$(RESET)"

# CI/CD pipeline - typically used in automation to install, lint, and run the app
ci: clean install lint test  ## Clean, install, lint, and test (for CI/CD)

# Setup and run for new developers
setup: virtualenv activate install

# Install test dependencies
test-deps:  ## Install test dependencies
	@echo "$(BLUE)Installing test dependencies...$(RESET)"
	@$(PIP) install pytest pytest-asyncio pytest-cov httpx jinja2
	@echo "$(GREEN)Test dependencies installed.$(RESET)"

# Run all tests
test:
	@echo "$(BLUE)Running all tests...$(RESET)"
	@$(PYTEST) --cov=service $(TEST_DIR)
	@echo "$(GREEN)All tests completed.$(RESET)"

# Run unit tests only
test-unit:
	@echo "$(BLUE)Running unit tests...$(RESET)"
	@$(PYTEST) --cov=service $(UNIT_TEST_DIR)
	@echo "$(GREEN)Unit tests completed.$(RESET)"

# Run integration tests only
test-integration:
	@echo "$(BLUE)Running integration tests...$(RESET)"
	@$(PYTEST) --cov=service $(INTEGRATION_TEST_DIR)
	@echo "$(GREEN)Integration tests completed.$(RESET)"

# Generate test coverage report
test-coverage: test  ## Generate detailed test coverage report
	@echo "$(BLUE)Generating test coverage report...$(RESET)"
	@$(VENV)/bin/coverage report -m
	@$(VENV)/bin/coverage html
	@echo "$(GREEN)Coverage report generated. Open htmlcov/index.html to view.$(RESET)"