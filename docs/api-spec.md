# Catalog Controller API Reference

<div align="center">

</div>

## Overview

The Catalog Controller API provides endpoints for managing Components, Metrics, and Scorecards in Kubernetes using the Metacontroller pattern. This API synchronizes custom resources with Atlassian Compass and manages their lifecycle.

## 📋 Contents

- [Endpoints](#endpoints)
- [Request & Response Models](#request--response-models)
- [Authentication](#authentication)
- [Examples](#examples)
- [Error Handling](#error-handling)

## 🔌 Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/component/sync` | Synchronize component resources with Compass |
| `POST` | `/metric/sync` | Synchronize metric resources with Compass |
| `POST` | `/scorecard/sync` | Synchronize scorecard resources with Compass |
| `POST` | `/finalize` | Handle resource finalization when deleted |
| `GET`  | `/healthz` | Health check endpoint |

### Health Check

```http
GET /healthz
```

Returns a simple status response to confirm the API is operational.

**Response:**

```json
{
  "status": "ok"
}
```

### Component Synchronization

```http
POST /component/sync
```

Processes a component resource and synchronizes it with Compass.

**Request Body:**
- MetacontrollerRequest (see schema below)

**Response:**
- JSON object with status and child resources (if any)

### Metric Synchronization

```http
POST /metric/sync
```

Processes a metric resource and synchronizes it with Compass. Creates or updates CronJob resources for scheduled evaluation.

**Request Body:**
- MetacontrollerRequest (see schema below)

**Response:**
- JSON object with status and child resources (CronJobs)

### Scorecard Synchronization

```http
POST /scorecard/sync
```

Processes a scorecard resource and synchronizes it with Compass.

**Request Body:**
- MetacontrollerRequest (see schema below)

**Response:**
- JSON object with status and child resources (if any)

### Resource Finalization

```http
POST /finalize
```

Handles cleanup when a resource is deleted.

**Request Body:**
- MetacontrollerRequest (see schema below)

**Response:**
- JSON object with finalization status

## 📊 Request & Response Models

### MetacontrollerRequest

This is the main request format used by Metacontroller to communicate with the API.

```yaml
type: object
required:
  - controller
  - parent
  - finalizing
properties:
  controller:
    type: object
    additionalProperties: true
    description: "Information about the controller"
  parent:
    $ref: '#/components/schemas/ParentResource'
    description: "The parent resource being processed"
  children:
    type: object
    additionalProperties:
      type: object
      additionalProperties: true
    description: "Child resources managed by this controller"
  related:
    type: object
    additionalProperties:
      type: object
      additionalProperties: true
    description: "Related resources"
  finalizing:
    type: boolean
    description: "Whether the resource is being deleted"
```

### ParentResource

Represents the Kubernetes resource being processed (Component, Metric, or Scorecard).

```yaml
type: object
required:
  - apiVersion
  - kind
  - metadata
  - spec
properties:
  apiVersion:
    type: string
    description: "API version of the resource"
  kind:
    type: string
    description: "Kind of resource (Component, Metric, Scorecard)"
  metadata:
    $ref: '#/components/schemas/KubernetesMetadata'
    description: "Kubernetes metadata"
  spec:
    type: object
    additionalProperties: true
    description: "Resource specification"
  status:
    type: object
    additionalProperties: true
    description: "Current resource status"
```

### KubernetesMetadata

Standard Kubernetes resource metadata.

```yaml
type: object
required:
  - name
  - uid
properties:
  name:
    type: string
    description: "Resource name"
  namespace:
    type: string
    description: "Resource namespace (if namespaced)"
  uid:
    type: string
    description: "Unique identifier"
  resourceVersion:
    type: string
    description: "Resource version for optimistic concurrency"
  generation:
    type: integer
    description: "Generation count for tracking changes"
  creationTimestamp:
    type: string
    format: date-time
    description: "When the resource was created"
  deletionTimestamp:
    type: string
    format: date-time
    description: "When the resource was marked for deletion"
  annotations:
    type: object
    additionalProperties:
      type: string
    description: "Resource annotations"
  labels:
    type: object
    additionalProperties:
      type: string
    description: "Resource labels"
  finalizers:
    type: array
    items:
      type: string
    description: "Resource finalizers"
```

## 🔐 Authentication

This API is intended to be used by Metacontroller within a Kubernetes cluster. Authentication is handled by Kubernetes service accounts and RBAC.

## 📝 Examples

### Component Synchronization Request

```json
{
  "controller": {
    "apiVersion": "metacontroller.k8s.io/v1alpha1",
    "kind": "CompositeController",
    "name": "components-controller"
  },
  "parent": {
    "apiVersion": "catalog.onefootball.com/v1alpha1",
    "kind": "Component",
    "metadata": {
      "name": "my-service",
      "namespace": "my-team",
      "uid": "12345678-1234-1234-1234-123456789012",
      "resourceVersion": "42"
    },
    "spec": {
      "componentType": "service",
      "name": "My Service",
      "typeId": "SERVICE",
      "description": "A microservice for authentication",
      "tribe": "Platform",
      "squad": "Auth"
    }
  },
  "children": {},
  "related": {},
  "finalizing": false
}
```

### Component Synchronization Response

```json
{
  "status": {
    "id": "my-service/component::123456789",
    "ownerId": "team-my-service::123456789",
    "metricAssociation": [
      {
        "metricName": "instrumentation-check",
        "metricId": "instrumentation-check/metric::123456789",
        "metricSourceId": "my-service-instrumentation-check/metricSource:::123456789"
      }
    ]
  },
  "children": []
}
```

### Metric Synchronization Response

```json
{
  "status": {
    "id": "observability-documentation/metric::123456789",
    "cronJob": "Created"
  },
  "children": [
    {
      "apiVersion": "batch/v1",
      "kind": "CronJob",
      "metadata": {
        "name": "observability-documentation-evaluator",
        "namespace": "catalog-controller"
      },
      "spec": {
        "schedule": "0 * * * *",
        "jobTemplate": {
          "spec": {
            "template": {
              "spec": {
                "containers": [
                  {
                    "name": "compute-caller",
                    "image": "alpine/curl",
                    "command": [
                      "/bin/sh",
                      "-c",
                      "curl -X POST metric-evaluation-service/evaluate/observability-documentation -H 'Content-Type: application/json' -d '{\"spec\": {}}'"
                    ]
                  }
                ],
                "restartPolicy": "Never"
              }
            }
          }
        }
      }
    }
  ]
}
```

## ⚠️ Error Handling

The API uses standard HTTP status codes:

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid input parameters |
| 422 | Validation Error - Request body validation failed |
| 500 | Internal Server Error - Processing failed |

### Validation Error Response

```json
{
  "detail": [
    {
      "loc": [
        "body",
        "parent",
        "metadata",
        "name"
      ],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## 📦 Models Reference Table

| Model | Description | Required Fields |
|-------|-------------|----------------|
| MetacontrollerRequest | Main request format from Metacontroller | controller, parent, finalizing |
| ParentResource | The Kubernetes resource being processed | apiVersion, kind, metadata, spec |
| KubernetesMetadata | Standard Kubernetes resource metadata | name, uid |
| HTTPValidationError | Validation error response | detail |
| ValidationError | Individual validation error | loc, msg, type |