import logging
from typing import Dict, Any, Optional, Tuple
from models import ResourceKind
from utils import set_condition, call_compass_api, handle_transient_error, handle_persistent_error

logger = logging.getLogger("CompassSubHandler")


def fetch_compass_state(compass_id: Optional[str], resource_kind: str, resource_spec: Dict[str, Any],
                        current_status: Dict[str, Any], desired_status: Dict[str, Any]) -> Tuple[Optional[Dict], Dict]:
    if not compass_id:
        logger.info(f"No Compass ID found for {resource_kind}. Resource doesn't exist.")
        set_condition(desired_status["conditions"], "Synced", "False", "NotCreated",
                      f"{resource_kind} not created in Compass yet.")
        return None, desired_status

    logger.info(f"Fetching state for {resource_kind} with ID: {compass_id}")
    get_result = call_compass_api(resource_kind, "get", resource_spec, status=current_status, compass_id=compass_id)

    if get_result["success"]:
        if get_result.get("exists"):
            compass_state = get_result.get("state")
            set_condition(desired_status["conditions"], "Synced", "True", "FetchedState",
                          f"Fetched state from Compass for {resource_kind}.")
            return compass_state, desired_status
        else:
            logger.warning(f"Compass ID {compass_id} found but resource doesn't exist. Re-creating.")
            desired_status.pop("id", None)
            if resource_kind == ResourceKind.COMPONENT :
                desired_status.pop("metricSources", None)
            set_condition(desired_status["conditions"], "Synced", "False", "StateMismatch",
                          f"Resource doesn't exist in Compass. Re-creating.")
            set_condition(desired_status["conditions"], "Ready", "False", "StateMismatch",
                          f"Resource doesn't exist in Compass. Re-creating.")
            return None, desired_status
    elif get_result.get("transient"):
        handle_transient_error(desired_status, f"Transient error fetching state: {get_result.get('message')}")
        return None, desired_status
    else:
        handle_persistent_error(desired_status, f"Failed to fetch state: {get_result.get('message')}")
        return None, desired_status


def create_compass_resource(resource_kind: str, resource_spec: Dict[str, Any],
                            current_status: Dict[str, Any], desired_status: Dict[str, Any]) -> Dict[str, Any]:
    logger.info(f"Creating {resource_kind} in Compass")
    api_result = call_compass_api(resource_kind, "create", resource_spec, status=current_status)

    if api_result["success"]:
        desired_status["id"] = api_result["id"]
        if resource_kind == "Component" and "metricSources" in api_result:
            desired_status["metricSources"] = api_result["metricSources"]

        set_condition(desired_status["conditions"], "Ready", "True", f"{resource_kind}CreatedInCompass",
                      f"{resource_kind} created with ID: {api_result['id']}")
        set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                      f"{resource_kind} synced (created).")
    elif api_result.get("transient"):
        handle_transient_error(desired_status, f"Transient error during creation: {api_result.get('message')}")
    else:
        handle_persistent_error(desired_status, f"Failed to create: {api_result.get('message', 'Unknown error')}")

    return desired_status


def update_compass_resource(resource_kind: str, resource_spec: Dict[str, Any], compass_id: str,
                            compass_state: Dict[str, Any], current_status: Dict[str, Any],
                            desired_status: Dict[str, Any]) -> Dict[str, Any]:
    if not needs_update(resource_kind, resource_spec, compass_state):
        return handle_no_update_needed(resource_kind, compass_id, compass_state, resource_spec, desired_status)

    logger.info(f"Updating {resource_kind} with ID {compass_id} in Compass")
    api_result = call_compass_api(resource_kind, "update", resource_spec, status=current_status, compass_id=compass_id)

    if api_result["success"]:
        if resource_kind == ResourceKind.COMPONENT and "metricSources" in api_result:
            desired_status["metricSources"] = api_result["metricSources"]
        if resource_kind == ResourceKind.SCORECARD:
            desired_status["metricsSummary"] = ", ".join(
                [c.get("metricName", "unknown") for c in resource_spec.get("criteria", [])])

        set_condition(desired_status["conditions"], "Ready", "True", f"{resource_kind}UpdatedInCompass",
                      f"{resource_kind} updated")
        set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                      f"{resource_kind} synced (updated).")
    elif api_result.get("transient"):
        handle_transient_error(desired_status, f"Transient error during Compass update: {api_result.get('message')}")
    else:
        handle_persistent_error(desired_status, f"Update failed: {api_result.get('message')}")

    return desired_status


def needs_update(resource_kind: str, resource_spec: Dict[str, Any], compass_state: Dict[str, Any]) -> bool:
    diff_fields = {
        "metric": ["description", "format", "grading-system"],
        "scorecard": ["description", "importance", "state"],
        "component": ["description", "componentType", "slug", "typeId"]
    }.get(resource_kind, [])

    return any(resource_spec.get(field) != compass_state.get(field) for field in diff_fields)


def handle_no_update_needed(resource_kind: str, compass_id: str, compass_state: Dict[str, Any],
                            resource_spec: Dict[str, Any], desired_status: Dict[str, Any]) -> Dict[str, Any]:
    logger.info(f"No differences detected for {resource_kind} {compass_id} in Compass state")

    if resource_kind == ResourceKind.SCORECARD:
        desired_status["metricsSummary"] = ", ".join(
            [c.get("metricName", "unknown") for c in resource_spec.get("criteria", [])])
        if compass_state and "criteria" in compass_state:
            desired_status["criteria"] = compass_state["criteria"]
    elif resource_kind == ResourceKind.COMPONENT and compass_state and "metricSources" in compass_state:
        desired_status["metricSources"] = compass_state["metricSources"]

    set_condition(desired_status["conditions"], "Ready", "True", "InSync",
                  f"{resource_kind} in sync with Compass")
    set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                  f"{resource_kind} in sync with Compass.")

    return desired_status
