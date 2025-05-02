# Maintainer Guide

# Table of Contents

- [Setup and Prerequisites](#setup-and-prerequisites)
  - [Development Prerequisites](#development-prerequisites)
  - [Required Services](#required-services)
- [Development Environment](#development-environment)
  - [Setting Up Local Development](#setting-up-local-development)
  - [Running the Service Locally](#running-the-service-locally)
  - [Building and Running with Docker](#building-and-running-with-docker)
  - [Testing Against a Kubernetes Cluster](#testing-against-a-kubernetes-cluster)
- [Project Structure](#project-structure)
  - [Key Files and Directories](#key-files-and-directories)
- [CI/CD and Deployment Process](#cicd-and-deployment-process)
  - [CI/CD Workflows](#cicd-workflows)
    - [Controller CI/CD Workflow](#controller-cicd-workflow)
    - [Chart Release Workflow](#chart-release-workflow)
  - [Building the Image Manually](#building-the-image-manually)
  - [Deploying with Helm](#deploying-with-helm)
  - [Configuration Options](#configuration-options)
  - [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)
  - [Common Issues](#common-issues)
    - [Controller Not Processing Resources](#controller-not-processing-resources)
    - [Metrics Not Being Evaluated](#metrics-not-being-evaluated)
  - [Debug Tools](#debug-tools)
- [Contributing Guidelines](#contributing-guidelines)
  - [Adding New Features](#adding-new-features)
  - [Adding New Metrics](#adding-new-metrics)
  - [Code Style and Quality](#code-style-and-quality)
    - [Pre-commit Hooks](#pre-commit-hooks)
    - [Linting](#linting)
  - [Release Process](#release-process)
    - [Automated Releases](#automated-releases)
    - [Manual Release (if needed)](#manual-release-if-needed)


This guide is intended for developers and maintainers working on the Catalog Controller project. It provides detailed information about the project structure, development environment, and deployment processes.

## Setup and Prerequisites

### Development Prerequisites

- Python 3.12 or newer (project uses Python 3.13 in production)
- Make
- Pip and Virtualenv
- Docker
- Kubernetes cluster for testing (minikube or kind)
- kubectl configured to access your cluster
- Helm 3

### Required Services

For a complete development environment, you'll need:
- Metacontroller installed in your Kubernetes cluster
- A mock Compass Service or access to the real one
- A mock Metric Evaluation Service or access to the real one

## Development Environment

### Setting Up Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/yourorgnization/catalog-controller.git
   cd catalog-controller
   ```

2. Use the provided Makefile to set up your development environment:
   ```bash
   # View all available commands
   make help
   
   # Set up everything (creates virtualenv, activates it, installs requirements)
   make setup
   
   # Activate the virtual environment
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. The setup process will also install pre-commit hooks for code quality:
   ```bash
   # If you need to set up pre-commit hooks separately
   make pre-commit-setup
   ```

### Running the Service Locally

You can run the FastAPI service locally for development using the Makefile:

```bash
# Run with default configuration
make run

# Run in development mode without OpenTelemetry
make run-dev

# Specify a custom port
PORT=8080 make run
```

### Building and Running with Docker

1. Build the Docker image using the Makefile:
   ```bash
   make docker-build
   ```

2. Run the container:
   ```bash
   docker run -p 7070:7070 catalog-controller
   ```

### Testing Against a Kubernetes Cluster

For complete testing, you'll need to:

1. Build and push the Docker image:
   ```bash
   docker build -t your-registry/catalog-controller:dev .
   docker push your-registry/catalog-controller:dev
   ```

2. Install the Helm chart with your local image:
   ```bash
   helm upgrade --install catalog-controller ./charts/catalog-controller \
     --set image.repository=your-registry/catalog-controller \
     --set image.tag=dev
   ```

## Project Structure

The project is organized into the following structure:

```
catalog-controller/
├── charts/                  # Helm chart for deployment
│   └── catalog-controller/
│       ├── crds/            # Custom Resource Definitions
│       ├── templates/       # Kubernetes manifest templates
│       │   ├── catalogs/    # Default metric and scorecard definitions
│       │   │   ├── metrics/
│       │   │   └── scorecards/
│       │   └── ...
│       ├── Chart.yaml       # Chart metadata
│       └── values.yaml      # Default configuration values
├── service/                 # Python service code
│   ├── handlers/            # Request handlers for each resource type
│   ├── models/              # Pydantic models for API requests/responses
│   ├── scheduler/           # CronJob generation logic
│   └── utils/               # Utility functions and API clients
├── main.py                  # FastAPI application entry point
├── Dockerfile               # Container build definition
├── requirements.txt         # Python dependencies
└── openapi.py               # OpenAPI schema generator
```

### Key Files and Directories

- **CRDs (`charts/catalog-controller/crds/`)**: Define the Custom Resource Definitions for Components, Metrics, and Scorecards
- **Resource Handlers (`service/handlers/`)**: Implement the reconciliation logic for each resource type
- **Models (`service/models/`)**: Define the data structures for API requests and responses
- **Utility Modules (`service/utils/`)**: Provide common functionality like Compass API integration

## CI/CD and Deployment Process

The project uses GitHub Actions for continuous integration and deployment.

### CI/CD Workflows

#### Controller CI/CD Workflow

This workflow is triggered on pushes to the `main` branch (excluding changes to charts, GitHub workflows, docs, and markdown files):

1. Sets up Python 3.12
2. Generates a new version using the `bump-release` action
3. Builds and pushes a Docker image
4. Performs security checks
5. Creates a GitHub release with automatically generated release notes
6. Deletes the tag if any step fails

#### Chart Release Workflow

This workflow is triggered on pushes to the `main` branch that affect files in the `charts/` directory:

1. Configures Git with the GitHub actor
2. Sets up Helm
3. Uses the Helm chart-releaser action to create a new chart release

### Building the Image Manually

```bash
# Using the Makefile
make docker-build

# Or using Docker directly
docker build -t your-registry/catalog-controller:latest .
docker push your-registry/catalog-controller:latest
```

### Deploying with Helm

```bash
helm upgrade --install catalog-controller ./charts/catalog-controller \
  --namespace catalog-controller \
  --create-namespace \
  --set image.repository=your-registry/catalog-controller \
  --set image.tag=latest
```

### Configuration Options

Key configuration values in `values.yaml`:

- `image.repository` and `image.tag`: Docker image settings
- `autoscaling`: HPA configuration
- `resources`: CPU and memory requests/limits
- `controllers`: Controller configurations for each resource type
- `env`: Environment variables for the container

### Environment Variables

- `COMPASS_SERVICE_ENDPOINT`: URL of the Compass Service
- `METRIC_EVALUATION_SERVICE_URL`: URL of the Metric Evaluation Service
- `CONTROLLER_PREFIX`: Prefix for controller labels and annotations
- `PORT`: Port for the FastAPI service (defaults to 7070)

## Troubleshooting

### Common Issues

#### Controller Not Processing Resources

1. Check that Metacontroller is running:
   ```bash
   kubectl get pods -n metacontroller
   ```

2. Check controller logs:
   ```bash
   kubectl logs -n catalog-controller deploy/catalog-controller
   ```

3. Verify webhook configuration:
   ```bash
   kubectl get compositecontrollers -o yaml
   ```

#### Metrics Not Being Evaluated

1. Check if CronJobs are being created:
   ```bash
   kubectl get cronjobs -n catalog-controller
   ```

2. Check CronJob logs:
   ```bash
   kubectl logs -n catalog-controller job/metric-name-evaluator-1234567890
   ```

3. Verify metric definition, especially the `facts` section

#### Compass Integration Issues

1. Check if the Compass Service is accessible
2. Verify authentication configuration
3. Look for API errors in the catalog-controller logs

### Debug Tools

1. Enable debug logging by setting the environment variable:
   ```yaml
   env:
     - name: LOG_LEVEL
       value: DEBUG
   ```

2. Use port-forwarding to directly access the API:
   ```bash
   kubectl port-forward -n catalog-controller svc/catalog-controller 7070:80
   ```

3. Access the OpenAPI documentation:
   ```
   http://localhost:7070/docs
   ```

## Contributing Guidelines

### Adding New Features

1. For significant changes, create an issue to discuss the approach first
2. Fork the repository and create a feature branch
3. Implement the feature with appropriate tests
4. Update documentation to reflect your changes
5. Submit a pull request with a clear description of the changes

### Adding New Metrics

To add a new metric:

1. Create a YAML file in `charts/catalog-controller/templates/catalogs/metrics/`
2. Define the metric with appropriate facts and rules
3. Test the metric with real components
4. Add the metric to a scorecard if appropriate

### Code Style and Quality

- Follow PEP 8 for Python code
- Use type hints for function parameters and return values
- Document functions and classes with docstrings
- Format YAML files with consistent indentation (2 spaces)

#### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality. These are automatically installed by the setup process:

```bash
# If needed, set up pre-commit hooks manually
make pre-commit-setup
```

The pre-commit hooks handle:
- Code formatting
- Linting
- Type checking
- Security checks

#### Linting

You can run linting manually using the Makefile:

```bash
make lint
```

This runs flake8 on the codebase to check for style and quality issues.

### Release Process

#### Automated Releases

The project uses automated releases through GitHub Actions:

1. **Controller Releases:**
   - Push changes to the `main` branch
   - The CI/CD workflow automatically:
     - Generates a new version
     - Builds and pushes the Docker image
     - Creates a GitHub release with release notes

2. **Chart Releases:**
   - Update `Chart.yaml` with a new version
   - Push changes to the `main` branch
   - The chart-release workflow automatically:
     - Packages the Helm chart
     - Creates a new chart release

#### Manual Release (if needed)

1. Update version numbers in:
   - `Chart.yaml`
   - `values.yaml`
   - Any other version references

2. Update the CHANGELOG.md with significant changes

3. Tag the release:
   ```bash
   git tag -a v0.x.y -m "Release v0.x.y"
   git push origin v0.x.y
   ```

4. Build and push the Docker image with the release tag:
   ```bash
   docker build -t your-registry/catalog-controller:v0.x.y .
   docker push your-registry/catalog-controller:v0.x.y
   ```

5. Package and update the Helm chart:
   ```bash
   helm package ./charts/catalog-controller
   # Update the Helm repository as needed
   ```