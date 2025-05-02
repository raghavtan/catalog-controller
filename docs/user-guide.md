# User Guide

## Table of Contents
- [Catalog Controller Documentation](#catalog-controller-documentation)
- [Introduction](#introduction)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Namespaces](#namespaces)
- [Creating Components](#creating-components)
  - [Component Definition Example](#component-definition-example)
  - [Creating a Component](#creating-a-component)
  - [Viewing Component Status](#viewing-component-status)
- [Defining Metrics](#defining-metrics)
  - [Metric Definition Example](#metric-definition-example)
  - [Creating a Metric](#creating-a-metric)
  - [Viewing Metric Status](#viewing-metric-status)
- [Creating Scorecards](#creating-scorecards)
  - [Scorecard Definition Example](#scorecard-definition-example)
  - [Creating a Scorecard](#creating-a-scorecard)
  - [Viewing Scorecard Status](#viewing-scorecard-status)
- [Viewing Results in Compass](#viewing-results-in-compass)
- [Common Use Cases](#common-use-cases)
  - [Adding a New Service to the Catalog](#adding-a-new-service-to-the-catalog)
  - [Creating a Custom Metric](#creating-a-custom-metric)
  - [Monitoring Metric Evaluation](#monitoring-metric-evaluation)

## Getting Started

The Catalog Controller provides a Kubernetes-native way to manage your organization's service catalog in Atlassian Compass. This guide will help you understand how to use the system effectively.

### Prerequisites

- A Kubernetes cluster with the Catalog Controller installed
- Access to Atlassian Compass
- `kubectl` configured to access your cluster
- Basic understanding of Kubernetes and YAML

### Namespaces

Catalog Controller resources are typically managed in dedicated namespaces:
- **Components** are created in namespaces that match your organizational structure
- **Metrics** and **Scorecards** are cluster-scoped resources, accessible across all namespaces

## Creating Components

Components represent services, libraries, or other technical assets in your organization.

### Component Definition Example

```yaml
apiVersion: catalog.onefootball.com/v1alpha1
kind: Component
metadata:
  name: my-service
  namespace: my-team
spec:
  componentType: service
  name: "My Service"
  typeId: SERVICE
  description: "A microservice that handles user authentication"
  tribe: "Platform"
  squad: "Auth"
  links:
    - name: "Source Code"
      type: REPOSITORY
      url: "https://github.com/org/my-service"
    - name: "API Documentation"
      type: API_DOCUMENTATION
      url: "https://docs.mycompany.com/my-service"
    - name: "Dashboard"
      type: DASHBOARD
      url: "https://grafana.mycompany.com/d/my-service"
    - name: "On-Call"
      type: ON_CALL
      url: "https://pagerduty.com/my-service"
  dependsOn:
    - "auth-database"
    - "logging-service"
```

### Creating a Component

Save the definition to a file (e.g., `my-service.yaml`) and apply it:

```bash
kubectl apply -f my-service.yaml
```

### Viewing Component Status

Check the status of your component:

```bash
kubectl get component my-service -n my-team -o yaml
```

Look for the `status` section which will include:
- `id`: The Compass ID of your component
- `ownerId`: The ID of the owning team in Compass
- `metricAssociation`: Metrics associated with this component

## Defining Metrics

Metrics define specific measurements for evaluating component quality.

### Metric Definition Example

```yaml
apiVersion: catalog.onefootball.com/v1alpha1
kind: Metric
metadata:
  name: observability-documentation
spec:
  description: "Checks for observability documentation"
  format:
    unit: "Observability Documentation"
  name: observability-documentation
  facts:
    - auth: null
      filePath: docs/observability.md
      id: extract-observability-md
      name: "Extract observability.md"
      repo: ${Metadata.Name}
      rule: notempty
      source: github
      type: extract
  componentType:
    - service
    - cloud-resource
  grading-system: observability
  cronSchedule: "0 * * * *"  # Run hourly
```

### Creating a Metric

Save the definition to a file (e.g., `observability-metric.yaml`) and apply it:

```bash
kubectl apply -f observability-metric.yaml
```

### Viewing Metric Status

Check the status of your metric:

```bash
kubectl get metric observability-documentation -o yaml
```

Look for the `status` section which will include:
- `id`: The Compass ID of your metric
- `cronJob`: Status of the scheduled evaluation job

## Creating Scorecards

Scorecards combine metrics to evaluate components on specific quality aspects.

### Scorecard Definition Example

```yaml
apiVersion: catalog.onefootball.com/v1alpha1
kind: Scorecard
metadata:
  name: observability
spec:
  componentTypeIds:
  - SERVICE
  criteria:
  - hasMetricValue:
      comparator: EQUALS
      comparatorValue: 1
      metricName: instrumentation-check
      name: instrumentation-check
      weight: 15
  - hasMetricValue:
      comparator: EQUALS
      comparatorValue: 1
      metricName: observability-documentation
      name: observability-documentation
      weight: 25
  description: "Evaluates observability practices"
  importance: REQUIRED
  name: observability
  scoringStrategyType: WEIGHT_BASED
  state: PUBLISHED
```

### Creating a Scorecard

Save the definition to a file (e.g., `observability-scorecard.yaml`) and apply it:

```bash
kubectl apply -f observability-scorecard.yaml
```

### Viewing Scorecard Status

Check the status of your scorecard:

```bash
kubectl get scorecard observability -o yaml
```

Look for the `status` section which will include:
- `id`: The Compass ID of your scorecard
- `metricsSummary`: A summary of metrics with validation status
- `metricAssociation`: Links between metrics and their Compass identifiers

## Viewing Results in Compass

After creating components, metrics, and scorecards in Kubernetes, you can view the results in Atlassian Compass:

1. Log in to your Atlassian Compass instance
2. Navigate to the "Components" section to see your components
3. Select a component to view its details and scorecard ratings
4. Navigate to the "Scorecards" section to see overall ratings

## Common Use Cases

### Adding a New Service to the Catalog

1. Create a Component resource for your service
2. Ensure your service repository has the necessary files:
   - README.md - General documentation
   - docs/observability.md - Observability documentation
   - app.toml - Configuration with proper resource settings
3. Verify that your service passes the relevant metrics
4. Check Compass to see your service's scores

### Creating a Custom Metric

1. Define the facts needed to evaluate your metric:
   - GitHub checks for specific files or patterns
   - Prometheus queries for operational metrics
   - API calls to relevant services
2. Create the Metric resource with appropriate facts and rules
3. Add the metric to a relevant scorecard
4. Test by manually triggering the evaluation

### Monitoring Metric Evaluation

To view the status of metric evaluations:

```bash
# List all metric evaluation cronjobs
kubectl get cronjobs -n catalog-controller

# View logs from a specific evaluation
kubectl logs -n catalog-controller job/observability-documentation-evaluator-1234567890
```

### Troubleshooting

If a metric isn't evaluating as expected:

1. Check that the CronJob exists and is running on schedule
2. Look at the logs from the evaluation job
3. Verify that all referenced files and resources exist
4. Check that authentication to external systems is working

## Best Practices

1. **Name Resources Consistently**: Use consistent naming conventions for components, metrics, and scorecards
2. **Document Components Thoroughly**: Complete all component fields to maximize visibility in Compass
3. **Test Metrics Carefully**: Validate that metrics evaluate correctly before adding them to scorecards
4. **Monitor Evaluation Results**: Regularly check evaluation results in Compass to catch issues early
5. **Keep Facts Simple**: Design metrics with simple, focused facts rather than complex combinations
6. **Version Control Resources**: Store your Kubernetes resource definitions in version control