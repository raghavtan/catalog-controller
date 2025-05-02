# Catalog Controller Documentation

## Introduction

The Catalog Controller is a Kubernetes-based solution that manages service quality metrics, scorecards, and components by integrating with Atlassian Compass. It provides a framework for defining, evaluating, and tracking the health of microservices and other components across your organization.

![Catalog controller Helm Chart](https://github.com/motain/catalog-controller/actions/workflows/chart-release.yml/badge.svg?branch=main)

![Catalog controller service](https://github.com/motain/catalog-controller/actions/workflows/controller-release.yml/badge.svg?branch=main)



## Documentation Contents

1. [Architecture Overview](architecture-overview.md)
   - System Components
   - Integration Flow
   - Data Model
   - Architecture Diagram

2. [Design Documentation](design-documentation.md)
   - Custom Resource Definitions (CRDs)
   - Controller Design
   - Reconciliation Process
   - Design Decision Records
   - Design Diagrams

3. [User Guide](user-guide.md)
   - Getting Started
   - Creating Components
   - Defining Metrics
   - Creating Scorecards
   - Viewing Results in Compass
   - Common Use Cases

4. [Maintainer Guide](maintainer-guide.md)
   - Setup and Prerequisites
   - Development Environment
   - Project Structure
   - Testing
   - Deployment Process
   - Troubleshooting
   - Contributing Guidelines

## Quick Start

If you're new to the Catalog Controller, start with the [User Guide](user-guide.md) for an introduction to basic concepts and operations.

For developers and maintainers, the [Maintainer Guide](maintainer-guide.md) provides detailed information on development and deployment processes.

For a deeper understanding of the system architecture, refer to the [Architecture Overview](architecture-overview.md) and [Design Documentation](design-documentation.md).