from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger("Utils")

def get_condition(conditions: List[Dict[str, Any]], condition_type: str) -> Optional[Dict[str, Any]]:
    return next((c for c in conditions if c and c.get("type") == condition_type), None)

def set_condition(conditions: List[Dict[str, Any]], condition_type: str, status: str, reason: str, message: str):
    now = datetime.now(timezone.utc).isoformat()
    condition = get_condition(conditions, condition_type)
    if not condition:
        conditions.append({
            "type": condition_type,
            "status": status,
            "lastTransitionTime": now,
            "reason": reason,
            "message": message
        })
    else:
        condition["lastTransitionTime"] = now if condition.get("status") != status else condition["lastTransitionTime"]
        condition.update({ "status": status,"reason": reason, "message": message })

def handle_transient_error(desired_status: Dict[str, Any], message: str) -> None:
    logger.warning(message)
    set_condition(desired_status["conditions"], "Synced", "Unknown", "TransientError", f"Transient error: {message}")
    set_condition(desired_status["conditions"], "Ready", "Unknown", "TransientError", f"Transient error: {message}")


def handle_persistent_error(desired_status: Dict[str, Any], message: str) -> None:
    logger.error(message)
    set_condition(desired_status["conditions"], "Ready", "False", "ReconciliationFailed", message)
    set_condition(desired_status["conditions"], "Synced", "False", "SyncFailed", message)


def is_sync_successful(desired_status: Dict[str, Any]) -> bool:
    synced_condition = get_condition(desired_status["conditions"], "Synced")
    return synced_condition and synced_condition["status"] == "True"


def call_compass_api(resource_kind: str, operation: str, spec: Dict[str, Any], status: Dict[str, Any],
                     compass_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Dummy implementation of Compass API client.
    Generates consistent responses based on resource type and operation.
    """
    logger.info(f"Calling dummy Compass API: {resource_kind} {operation} id={compass_id}")

    # Normalize resource kind to lowercase for consistency
    resource_kind = resource_kind.lower()

    # Extract resource name based on resource kind
    resource_name = None
    if "metadata" in spec and "name" in spec["metadata"]:
        resource_name = spec["metadata"]["name"]
    elif "name" in spec:
        resource_name = spec["name"]
    else:
        resource_name = "unknown"

    # CREATE operation
    if operation == "create":
        # Generate consistent ID for the resource
        dummy_id = f"dummy-{resource_kind}-{resource_name}-123"
        response = {"success": True, "id": dummy_id}

        # Handle component-specific response
        if resource_kind == "component":
            # Extract metric names from spec if available, otherwise use empty list
            metric_sources = {}
            # For components, we'd use the actual metrics associated with the component
            # Since this is a dummy implementation, we'll create sources based on component type
            component_type = spec.get("componentType", "service").lower()

            # Dynamically determine metrics based on what's in status or create dummy ones
            metric_names = []
            if status and "metricSources" in status:
                # Use existing metric names from status
                metric_names = list(status["metricSources"].keys())

            # If we don't have metrics from status, generate some based on component type
            if not metric_names:
                if component_type == "service":
                    # Just generate 3 generic metrics as an example
                    metric_names = [f"metric-{i}" for i in range(3)]

            # Generate metric sources
            for metric_name in metric_names:
                metric_sources[metric_name] = {
                    "id": f"ms-{dummy_id}-{metric_name}",
                    "name": metric_name,
                    "metric": f"dummy-metric-{metric_name}-123",
                    "facts": []
                }

            response["metricSources"] = metric_sources

        # Handle scorecard-specific response
        elif resource_kind == "scorecard":
            # Extract criteria from spec
            criteria_state = {}
            for criterion in spec.get("criteria", []):
                if "hasMetricValue" in criterion:
                    metric_value = criterion["hasMetricValue"]
                    metric_name = metric_value.get("metricName", "unknown")
                    criteria_state[metric_name] = {
                        "metricDefinitionId": f"dummy-metric-{metric_name}-123"
                    }

            if criteria_state:
                response["criteria"] = criteria_state

        return response

    # GET operation
    elif operation == "get":
        # If compass_id provided, use it, otherwise generate one
        dummy_id = compass_id or f"dummy-{resource_kind}-{resource_name}-123"

        # Create base state for all resource types
        state = {
            "id": dummy_id,
            "name": resource_name
        }

        # Handle metric-specific state
        if resource_kind == "metric":
            state.update({
                "description": spec.get("description", ""),
                "format": spec.get("format", {}),
                "grading-system": spec.get("grading-system", ""),
                "cronSchedule": spec.get("cronSchedule", ""),
                "componentType": spec.get("componentType", []),
                "facts": spec.get("facts", [])
            })

        # Handle scorecard-specific state
        elif resource_kind == "scorecard":
            # Extract criteria from spec to generate dummy state
            criteria_state = {}
            for criterion in spec.get("criteria", []):
                if "hasMetricValue" in criterion:
                    metric_value = criterion["hasMetricValue"]
                    metric_name = metric_value.get("metricName", "unknown")
                    criteria_state[metric_name] = {
                        "metricDefinitionId": f"dummy-metric-{metric_name}-123",
                        "comparator": metric_value.get("comparator", "EQUALS"),
                        "comparatorValue": metric_value.get("comparatorValue", 1),
                        "weight": metric_value.get("weight", 50)
                    }

            state["criteria"] = criteria_state

            # Generate metrics summary
            metric_names = [c.get("hasMetricValue", {}).get("metricName", "unknown")
                            for c in spec.get("criteria", []) if "hasMetricValue" in c]
            state["metricsSummary"] = ", ".join(metric_names)
            state["componentTypeIds"] = spec.get("componentTypeIds", [])
            state["importance"] = spec.get("importance", "REQUIRED")
            state["state"] = spec.get("state", "PUBLISHED")
            state["scoringStrategyType"] = spec.get("scoringStrategyType", "WEIGHT_BASED")

        # Handle component-specific state
        elif resource_kind == "component":
            # For components, we'd need to extract sources from status or spec
            metric_sources = {}

            # Check if we already have metric sources in status
            if status and "metricSources" in status:
                # Reuse existing sources from status
                metric_sources = status["metricSources"]
            else:
                # If not, generate some dummy ones based on component type
                component_type = spec.get("componentType", "service").lower()
                # Just generate 3 generic metrics as an example
                for i in range(3):
                    metric_name = f"metric-{i}"
                    metric_sources[metric_name] = {
                        "id": f"ms-{dummy_id}-{metric_name}",
                        "name": metric_name,
                        "metric": f"dummy-metric-{metric_name}-123",
                        "facts": []
                    }

            state["metricSources"] = metric_sources
            state["componentType"] = spec.get("componentType", "")
            state["typeId"] = spec.get("typeId", "")
            state["description"] = spec.get("description", "")
            state["slug"] = spec.get("slug", "")

            # If we have an owner ID in status, preserve it
            if status and "ownerId" in status:
                state["ownerId"] = status["ownerId"]

        return {"success": True, "exists": True, "state": state}

    # UPDATE operation
    elif operation == "update":
        response = {"success": True}

        # Component-specific update response
        if resource_kind == "component":
            # If we have existing metric sources in status, preserve them
            metric_sources = {}
            if status and "metricSources" in status:
                metric_sources = status["metricSources"]
            else:
                # If not, generate some dummy ones based on component type
                component_type = spec.get("componentType", "service").lower()
                # Generate 3 generic metrics
                for i in range(3):
                    metric_name = f"metric-{i}"
                    metric_sources[metric_name] = {
                        "id": f"ms-{compass_id}-{metric_name}",
                        "name": metric_name,
                        "metric": f"dummy-metric-{metric_name}-123",
                        "facts": []
                    }

            response["metricSources"] = metric_sources

        # Scorecard-specific update response
        elif resource_kind == "scorecard":
            criteria_state = {}
            for criterion in spec.get("criteria", []):
                if "hasMetricValue" in criterion:
                    metric_value = criterion["hasMetricValue"]
                    metric_name = metric_value.get("metricName", "unknown")
                    criteria_state[metric_name] = {
                        "metricDefinitionId": f"dummy-metric-{metric_name}-123",
                        "comparator": metric_value.get("comparator", "EQUALS"),
                        "comparatorValue": metric_value.get("comparatorValue", 1),
                        "weight": metric_value.get("weight", 50)
                    }

            if criteria_state:
                response["criteria"] = criteria_state

        return response

    # DELETE operation
    elif operation == "delete":
        return {"success": True}

    # Unknown operation
    else:
        return {"success": False, "message": f"Unknown operation '{operation}' or not implemented"}