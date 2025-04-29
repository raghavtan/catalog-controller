import logging
from typing import Dict, Any, Optional, Tuple
from handlers.update_validation import needs_update, handle_no_update_needed
from models import ResourceKind
from utils import set_condition, call_compass_api, handle_transient_error, handle_persistent_error

logger = logging.getLogger("CompassSubHandler")


def fetch_compass_state(compass_id: str, resource_kind: str, parent: Dict[str, Any],
                        current_status: Dict[str, Any], desired_status: Dict[str, Any]) -> Tuple[Optional[Dict], Dict]:
    """
    Fetches the current state of a resource from Compass.
    Returns the compass state and updated desired status.
    """
    resource_name = parent["metadata"]["name"]
    logger.info(f"Fetching state for {resource_kind}/{resource_name} with ID: {compass_id}")

    # Call Compass API to get the resource state
    get_result = call_compass_api(resource_kind, "get", parent, status=current_status, compass_id=compass_id)

    if get_result["success"]:
        if get_result.get("exists", False):
            # Resource exists in Compass
            compass_state = get_result.get("state", {})
            logger.info(f"Successfully fetched state for {resource_kind}/{resource_name}")

            # Update resource-specific status based on Compass state
            if resource_kind.lower() == ResourceKind.SCORECARD:
                if "criteria" in compass_state:
                    desired_status["criteria"] = compass_state["criteria"]
                if "metricsSummary" in compass_state:
                    desired_status["metricsSummary"] = compass_state["metricsSummary"]

            elif resource_kind.lower() == ResourceKind.COMPONENT:
                if "metricSources" in compass_state:
                    desired_status["metricSources"] = compass_state["metricSources"]
                if "ownerId" in compass_state:
                    desired_status["ownerId"] = compass_state["ownerId"]

            # Update conditions
            set_condition(desired_status["conditions"], "Synced", "True", "FetchedState",
                          f"Fetched current state from Compass for {resource_kind}")

            return compass_state, desired_status
        else:
            # Resource doesn't exist in Compass despite having an ID
            logger.warning(
                f"Compass ID {compass_id} found but resource {resource_kind}/{resource_name} doesn't exist in Compass")

            # Clean up status fields that would be invalid
            desired_status.pop("id", None)

            if resource_kind.lower() == ResourceKind.COMPONENT:
                desired_status.pop("metricSources", None)
                desired_status.pop("ownerId", None)
            elif resource_kind.lower() == ResourceKind.SCORECARD:
                desired_status.pop("criteria", None)
                desired_status.pop("metricsSummary", None)

            # Update conditions
            set_condition(desired_status["conditions"], "Synced", "False", "ResourceNotFound",
                          f"Resource {resource_kind} with ID {compass_id} not found in Compass")
            set_condition(desired_status["conditions"], "Ready", "False", "ResourceNotFound",
                          f"Resource {resource_kind} with ID {compass_id} not found in Compass")

            return None, desired_status
    elif get_result.get("transient", False):
        # Handle transient errors
        handle_transient_error(desired_status,
                               f"Transient error fetching {resource_kind} state: {get_result.get('message', 'Unknown error')}")
        return None, desired_status
    else:
        # Handle persistent errors
        handle_persistent_error(desired_status,
                                f"Failed to fetch {resource_kind} state: {get_result.get('message', 'Unknown error')}")
        return None, desired_status


def create_compass_resource(resource_kind: str, parent: Dict[str, Any],
                            current_status: Dict[str, Any], desired_status: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a resource in Compass and updates the desired status with the result.
    """
    resource_name = parent["metadata"]["name"]
    resource_spec = parent.get("spec", {})

    logger.info(f"Creating {resource_kind} in Compass: {resource_name}")

    # Call the Compass API to create the resource
    api_result = call_compass_api(resource_kind, "create", parent, status=current_status)

    if api_result["success"]:
        # Set the ID in the status
        desired_status["id"] = api_result["id"]
        logger.info(f"Successfully created {resource_kind}/{resource_name} with ID: {api_result['id']}")

        # Handle resource-specific responses
        if resource_kind.lower() == ResourceKind.COMPONENT and "metricSources" in api_result:
            desired_status["metricSources"] = api_result["metricSources"]
            logger.info(f"Added {len(api_result['metricSources'])} metric sources to component status")

        elif resource_kind.lower() == ResourceKind.SCORECARD and "criteria" in api_result:
            desired_status["criteria"] = api_result["criteria"]

            # Generate metrics summary
            metric_names = [
                c.get("hasMetricValue", {}).get("metricName", "unknown")
                for c in resource_spec.get("criteria", [])
                if "hasMetricValue" in c
            ]
            desired_status["metricsSummary"] = ", ".join(metric_names)
            logger.info(f"Added criteria with metrics: {desired_status['metricsSummary']}")

        # Update conditions
        set_condition(desired_status["conditions"], "Ready", "True", "ResourceCreated",
                      f"{resource_kind} created in Compass with ID: {api_result['id']}")
        set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                      f"{resource_kind} synced with Compass")
    elif api_result.get("transient", False):
        # Handle transient errors
        handle_transient_error(desired_status,
                               f"Transient error creating {resource_kind}: {api_result.get('message', 'Unknown error')}")
    else:
        # Handle persistent errors
        handle_persistent_error(desired_status,
                                f"Failed to create {resource_kind}: {api_result.get('message', 'Unknown error')}")

    return desired_status


def update_compass_resource(resource_kind: str, parent: Dict[str, Any], compass_id: str,
                            compass_state: Dict[str, Any], current_status: Dict[str, Any],
                            desired_status: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates a resource in Compass if needed.
    Returns the updated desired status.
    """
    resource_name = parent["metadata"]["name"]
    resource_spec = parent.get("spec", {})

    # Check if the resource needs an update
    needs_update_result = needs_update(resource_kind, parent, compass_state)

    if not needs_update_result["needs_update"]:
        logger.info(f"No update needed for {resource_kind}/{resource_name} - already in sync")
        return handle_no_update_needed(resource_kind, compass_id, compass_state, parent, desired_status)

    # Resource needs updating
    update_fields = needs_update_result.get("update_fields", [])
    logger.info(f"Updating {resource_kind}/{resource_name} with ID {compass_id} - Fields to update: {update_fields}")

    # Call Compass API to update the resource
    api_result = call_compass_api(resource_kind, "update", parent, status=current_status, compass_id=compass_id)

    if api_result["success"]:
        # Handle resource-specific responses
        if resource_kind.lower() == ResourceKind.COMPONENT and "metricSources" in api_result:
            desired_status["metricSources"] = api_result["metricSources"]

        elif resource_kind.lower() == ResourceKind.SCORECARD:
            if "criteria" in api_result:
                desired_status["criteria"] = api_result["criteria"]

            # Generate metrics summary
            metric_names = [
                c.get("hasMetricValue", {}).get("metricName", "unknown")
                for c in resource_spec.get("criteria", [])
                if "hasMetricValue" in c
            ]
            desired_status["metricsSummary"] = ", ".join(metric_names)

        # Update conditions
        set_condition(desired_status["conditions"], "Ready", "True", "ResourceUpdated",
                      f"{resource_kind} updated in Compass")
        set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                      f"{resource_kind} synced with Compass")
    elif api_result.get("transient", False):
        # Handle transient errors
        handle_transient_error(desired_status,
                               f"Transient error updating {resource_kind}: {api_result.get('message', 'Unknown error')}")
    else:
        # Handle persistent errors
        handle_persistent_error(desired_status,
                                f"Failed to update {resource_kind}: {api_result.get('message', 'Unknown error')}")

    return desired_status