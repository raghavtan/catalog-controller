# Catalog Controller API Reference

<div align="center">

</div>

## Overview

The Catalog Controller API provides endpoints for managing resources in Kubernetes using the Metacontroller pattern. This API synchronizes custom resources and manages their lifecycle.

## 📋 Contents

- [Endpoints](#endpoints)
- [Request & Response Models](#request--response-models)
- [Authentication](#authentication)
- [Examples](#examples)
- [Error Handling](#error-handling)

## 🔌 Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sync/{resource_type}` | Synchronize resources of the specified type |
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

### Resource Synchronization

```http
POST /sync/{resource_type}
```

Processes a resource of the specified type and synchronizes it.

**Path Parameters:**
- `resource_type` (string): The type of resource to synchronize

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

Represents the Kubernetes resource being processed.

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
    description: "Kind of resource"
  metadata:
    $ref: '#/components/schemas/KubernetesMetadata'
    description: "Kubernetes metadata"
  spec:
    type: object
    additionalProperties: true
    description: "Resource specification"
  status:
    type: object
    nullable: true
    additionalProperties: true
    description: "Current resource status (optional)"
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
    nullable: true
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
    nullable: true
    description: "When the resource was created"
  deletionTimestamp:
    type: string
    format: date-time
    nullable: true
    description: "When the resource was marked for deletion"
  annotations:
    type: object
    nullable: true
    additionalProperties:
      type: string
    description: "Resource annotations"
  labels:
    type: object
    nullable: true
    additionalProperties:
      type: string
    description: "Resource labels"
  finalizers:
    type: array
    nullable: true
    items:
      type: string
    description: "Resource finalizers"
```

### HTTPValidationError

Represents a validation error response.

```yaml
type: object
properties:
  detail:
    type: array
    items:
      $ref: '#/components/schemas/ValidationError'
    description: "List of validation errors"
```

### ValidationError

Represents an individual validation error.

```yaml
type: object
required:
  - loc
  - msg
  - type
properties:
  loc:
    type: array
    items:
      anyOf:
        - type: string
        - type: integer
    description: "Location of the error"
  msg:
    type: string
    description: "Error message"
  type:
    type: string
    description: "Error type"
```

## 🔐 Authentication

This API is intended to be used by Metacontroller within a Kubernetes cluster. Authentication is handled by Kubernetes service accounts and RBAC.

## 📝 Examples

### Resource Synchronization Request

```json
{
  "controller": {
    "apiVersion": "metacontroller.k8s.io/v1alpha1",
    "kind": "CompositeController",
    "name": "resource-controller"
  },
  "parent": {
    "apiVersion": "example.com/v1alpha1",
    "kind": "CustomResource",
    "metadata": {
      "name": "my-resource",
      "namespace": "my-namespace",
      "uid": "12345678-1234-1234-1234-123456789012",
      "resourceVersion": "42"
    },
    "spec": {
      "type": "service",
      "name": "My Resource",
      "description": "A custom resource example"
    }
  },
  "children": {},
  "related": {},
  "finalizing": false
}
```

### Resource Synchronization Response

```json
{
  "status": {
    "id": "my-resource::123456789",
    "synchronized": true
  },
  "children": []
}
```

## ⚠️ Error Handling

The API uses standard HTTP status codes:

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
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