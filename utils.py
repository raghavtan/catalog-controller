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
    logger.info(f"Calling dummy Compass API: {resource_kind} {operation} id={compass_id}")

    # Get resource name based on the type
    if resource_kind.lower() == "component":
        resource_name = spec.get("name", "unknown")
    elif resource_kind.lower() == "metric":
        resource_name = spec.get("name", "unknown")
    elif resource_kind.lower() == "scorecard":
        resource_name = spec.get("name", "unknown")
    else:
        resource_name = "unknown"

    if operation == "create":
        dummy_id = f"dummy-{resource_kind.lower()}-{resource_name}-123"
        response = {"success": True, "id": dummy_id}

        # For components, add metricSources with dummy IDs
        if resource_kind.lower() == "component":
            metric_sources = {}
            # Generate dummy metric sources - in a real implementation, this would come from Compass
            metrics = ["security-as-pipeline", "vulnerability-management", "high-availability"]
            for metric_name in metrics:
                metric_sources[metric_name] = {
                    "id": f"ms-{dummy_id}-{metric_name}",
                    "name": metric_name,
                    "metric": f"dummy-metric-{metric_name}-123",
                    "facts": []  # Add facts structure if needed
                }
            response["metricSources"] = metric_sources

        return response

    elif operation == "get":
        dummy_id = compass_id or f"dummy-{resource_kind.lower()}-{resource_name}-123"
        state = {
            "id": dummy_id,
            "name": resource_name
        }

        # Add resource-specific dummy state
        if resource_kind.lower() == "metric":
            state.update({
                "description": spec.get("description", ""),
                "format": spec.get("format", {}),
                "grading-system": spec.get("grading-system", ""),
                "facts": spec.get("facts", [])
            })
        elif resource_kind.lower() == "scorecard":
            criteria_state = {}
            # Generate dummy criteria state with metricDefinitionIds
            for criterion in spec.get("criteria", []):
                metric_value = criterion.get("hasMetricValue", {})
                metric_name = metric_value.get("metricName", "unknown")
                criteria_state[metric_name] = {
                    "metricDefinitionId": f"dummy-metric-{metric_name}-123"
                }
            state["criteria"] = criteria_state

            # Generate metrics summary for scorecard
            metric_names = [c.get("hasMetricValue", {}).get("metricName", "unknown")
                            for c in spec.get("criteria", [])]
            state["metricsSummary"] = ", ".join(metric_names)

        elif resource_kind.lower() == "component":
            metric_sources = {}
            # Generate dummy metric sources - match the structure in CRD
            metrics = ["security-as-pipeline", "vulnerability-management", "high-availability"]
            for metric_name in metrics:
                metric_sources[metric_name] = {
                    "id": f"ms-{dummy_id}-{metric_name}",
                    "name": metric_name,
                    "metric": f"dummy-metric-{metric_name}-123",
                    "facts": []  # Add dummy facts
                }
            state["metricSources"] = metric_sources

        return {"success": True, "exists": True, "state": state}

    elif operation == "update":
        response = {"success": True}

        # For components, add metricSources with dummy IDs
        if resource_kind.lower() == "component":
            metric_sources = {}
            metrics = ["security-as-pipeline", "vulnerability-management", "high-availability"]
            for metric_name in metrics:
                metric_sources[metric_name] = {
                    "id": f"ms-{compass_id}-{metric_name}",
                    "name": metric_name,
                    "metric": f"dummy-metric-{metric_name}-123",
                    "facts": []  # Add dummy facts
                }
            response["metricSources"] = metric_sources

        # For scorecards, include criteria with metricDefinitionIds
        elif resource_kind.lower() == "scorecard":
            criteria_state = {}
            for criterion in spec.get("criteria", []):
                metric_value = criterion.get("hasMetricValue", {})
                metric_name = metric_value.get("metricName", "unknown")
                criteria_state[metric_name] = {
                    "metricDefinitionId": f"dummy-metric-{metric_name}-123"
                }
            response["criteria"] = criteria_state

        return response

    elif operation == "delete":
        return {"success": True}

    else:
        return {"success": False, "message": "Unknown operation or not implemented"}