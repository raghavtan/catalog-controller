import logging
from typing import Dict, Any, Optional, Tuple
from handlers.update_validation import needs_update, handle_no_update_needed
from utils import set_condition, call_compass_api, handle_transient_error, handle_persistent_error

logger = logging.getLogger("CompassSubHandler")


def fetch_compass_state(compass_id: Optional[str], resource_kind: str, parent: Dict[str, Any],
                        current_status: Dict[str, Any], desired_status: Dict[str, Any]) -> Tuple[Optional[Dict], Dict]:
    resource_spec = parent.get("spec", {})
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

            # Resource-specific state handling
            if resource_kind.lower() == "scorecard" and "criteria" in compass_state:
                desired_status["criteria"] = compass_state["criteria"]
                desired_status["metricsSummary"] = compass_state.get("metricsSummary", "")
            elif resource_kind.lower() == "component" and "metricSources" in compass_state:
                desired_status["metricSources"] = compass_state["metricSources"]

            set_condition(desired_status["conditions"], "Synced", "True", "FetchedState",
                          f"Fetched state from Compass for {resource_kind}.")
            return compass_state, desired_status
        else:
            logger.warning(f"Compass ID {compass_id} found but resource doesn't exist. Re-creating.")
            desired_status.pop("id", None)

            # Resource-specific cleanups
            if resource_kind.lower() == "component":
                desired_status.pop("metricSources", None)
            elif resource_kind.lower() == "scorecard":
                desired_status.pop("criteria", None)
                desired_status.pop("metricsSummary", None)

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


def create_compass_resource(resource_kind: str, parent: Dict[str, Any],
                            current_status: Dict[str, Any], desired_status: Dict[str, Any]) -> Dict[str, Any]:
    resource_spec = parent.get("spec", {})
    logger.info(f"Creating {resource_kind} in Compass for {parent['metadata']['name']}")
    api_result = call_compass_api(resource_kind, "create", resource_spec, status=current_status)

    if api_result["success"]:
        desired_status["id"] = api_result["id"]

        # Resource-specific responses
        if resource_kind.lower() == "component" and "metricSources" in api_result:
            desired_status["metricSources"] = api_result["metricSources"]
        elif resource_kind.lower() == "scorecard" and "criteria" in api_result:
            desired_status["criteria"] = api_result["criteria"]
            # Add metrics summary for scorecard from criteria
            if "criteria" not in desired_status:
                metric_names = [c.get("hasMetricValue", {}).get("metricName", "unknown")
                                for c in resource_spec.get("criteria", [])]
                desired_status["metricsSummary"] = ", ".join(metric_names)

        set_condition(desired_status["conditions"], "Ready", "True", f"{resource_kind}CreatedInCompass",
                      f"{resource_kind} created with ID: {api_result['id']}")
        set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                      f"{resource_kind} synced (created).")
    elif api_result.get("transient"):
        handle_transient_error(desired_status, f"Transient error during creation: {api_result.get('message')}")
    else:
        handle_persistent_error(desired_status, f"Failed to create: {api_result.get('message', 'Unknown error')}")

    return desired_status


def update_compass_resource(resource_kind: str, parent: Dict[str, Any], compass_id: str,
                          compass_state: Dict[str, Any], current_status: Dict[str, Any],
                          desired_status: Dict[str, Any]) -> Dict[str, Any]:
    resource_spec = parent.get("spec", {})
    if not needs_update(resource_kind, resource_spec, compass_state):
        return handle_no_update_needed(resource_kind, compass_id, compass_state, resource_spec, desired_status)

    logger.info(f"Updating {resource_kind} with ID {compass_id} in Compass for {parent['metadata']['name']}")
    api_result = call_compass_api(resource_kind, "update", resource_spec, status=current_status, compass_id=compass_id)

    if api_result["success"]:
        # Resource-specific responses
        if resource_kind.lower() == "component" and "metricSources" in api_result:
            desired_status["metricSources"] = api_result["metricSources"]
        elif resource_kind.lower() == "scorecard":
            if "criteria" in api_result:
                desired_status["criteria"] = api_result["criteria"]
            # Add metrics summary
            metric_names = [c.get("hasMetricValue", {}).get("metricName", "unknown")
                          for c in resource_spec.get("criteria", [])]
            desired_status["metricsSummary"] = ", ".join(metric_names)

        set_condition(desired_status["conditions"], "Ready", "True", f"{resource_kind}UpdatedInCompass",
                      f"{resource_kind} updated")
        set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                      f"{resource_kind} synced (updated).")
    elif api_result.get("transient"):
        handle_transient_error(desired_status, f"Transient error during Compass update: {api_result.get('message')}")
    else:
        handle_persistent_error(desired_status, f"Update failed: {api_result.get('message')}")

    return desired_status