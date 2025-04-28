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

def call_compass_api(resource_kind: str, operation: str, spec: Dict[str, Any], status: Dict[str, Any], compass_id: Optional[str] = None) -> Dict[str, Any]:
    logger.info(f"Calling dummy Compass API: {resource_kind} {operation} id={compass_id}")

    # Call compass-service API here
    # This will be implemented later

    # Placeholder return for now
    if operation == "create":
        # Simulate a successful creation
        return {"success": True, "id": f"dummy-{resource_kind}-compass-id-123"}
    elif operation == "get":
        # Simulate a successful get where the resource exists
        # You might want to return a dummy state here if needed by fetch_compass_state
        return {"success": True, "exists": True, "state": {}}
    elif operation == "delete":
        # Simulate a successful deletion
        return {"success": True}
    else:
        # Default return for other operations or unknown cases
        return {"success": False, "message": "Unknown operation or not implemented"}
