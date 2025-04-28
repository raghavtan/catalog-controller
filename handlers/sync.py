import logging
import sys
from datetime import datetime, timezone

from fastapi.responses import JSONResponse

from models import MetacontrollerRequest, SyncResponse
from utils import set_condition, get_condition

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SyncLogger")

COMPASS_API_SERVICE_ENDPOINT = "compass-api.compass-api.svc.cluster.local:80"

def sync_resource(request_data: MetacontrollerRequest, resource_kind: str) -> JSONResponse:
    """Generic sync logic for different resource kinds."""
    parent = request_data.parent.model_dump(by_alias=True)
    resource_name = parent["metadata"]["name"]
    resource_spec = parent["spec"]
    current_status = parent.get("status", {})
    desired_status = current_status.copy()

    # Initialize conditions
    desired_status.setdefault("conditions", [])
    set_condition(desired_status["conditions"], "Ready", "Unknown", "Reconciling",
                  f"Starting reconciliation for {resource_kind}.")
    set_condition(desired_status["conditions"], "Synced", "Unknown", "Reconciling",
                  f"Starting synchronization for {resource_kind}.")

    compass_id = desired_status.get("id")
    compass_state = None

    # Step 1: Check if resource exists in Compass
    if compass_id:
        logger.info(f"Fetching state for {resource_kind} with ID: {compass_id}")
        get_result = call_compass_api(resource_kind, "get", resource_spec, status=current_status, compass_id=compass_id)

        if get_result["success"]:
            if get_result.get("exists"):
                compass_state = get_result.get("state")
                set_condition(desired_status["conditions"], "Synced", "True", "FetchedState",
                              f"Fetched state from Compass for {resource_kind}.")
            else:
                # Resource doesn't exist in Compass despite having ID in status
                logger.warning(f"Compass ID {compass_id} found but resource doesn't exist. Re-creating.")
                desired_status.pop("id", None)
                if resource_kind == "Component":
                    desired_status.pop("metricSources", None)
                compass_id = None
                set_condition(desired_status["conditions"], "Synced", "False", "StateMismatch",
                              f"Resource doesn't exist in Compass. Re-creating.")
                set_condition(desired_status["conditions"], "Ready", "False", "StateMismatch",
                              f"Resource doesn't exist in Compass. Re-creating.")
        elif get_result.get("transient"):
            logger.warning(f"Transient error fetching state: {get_result.get('message')}")
            set_condition(desired_status["conditions"], "Synced", "Unknown", "TransientError",
                          f"Transient error: {get_result.get('message')}")
            set_condition(desired_status["conditions"], "Ready", "Unknown", "TransientError",
                          f"Transient error: {get_result.get('message')}")
            return JSONResponse(content=SyncResponse(status=desired_status).model_dump(by_alias=True), status_code=200)
        else:
            logger.error(f"Persistent error fetching state: {get_result.get('message')}")
            set_condition(desired_status["conditions"], "Synced", "False", "FetchFailed",
                          f"Failed to fetch state: {get_result.get('message')}")
            set_condition(desired_status["conditions"], "Ready", "False", "ReconciliationFailed",
                          f"Failed to fetch state: {get_result.get('message')}")
            return JSONResponse(content=SyncResponse(status=desired_status).model_dump(by_alias=True), status_code=500)
    else:
        logger.info(f"No Compass ID found for {resource_kind}. Resource doesn't exist.")
        set_condition(desired_status["conditions"], "Synced", "False", "NotCreated",
                      f"{resource_kind} not created in Compass yet.")

    # Step 2: Create or update resource
    if not compass_id:
        # Create resource
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
            logger.warning(f"Transient error during creation: {api_result.get('message')}")
            set_condition(desired_status["conditions"], "Synced", "Unknown", "TransientError",
                          f"Transient error: {api_result.get('message')}")
            set_condition(desired_status["conditions"], "Ready", "Unknown", "TransientError",
                          f"Transient error: {api_result.get('message')}")
            return JSONResponse(content=SyncResponse(status=desired_status).model_dump(by_alias=True), status_code=200)
        else:
            logger.error(f"Persistent error during creation: {api_result.get('message')}")
            set_condition(desired_status["conditions"], "Ready", "False", f"CreationFailed",
                          f"Failed to create: {api_result.get('message', 'Unknown error')}")
            set_condition(desired_status["conditions"], "Synced", "False", "SyncFailed",
                          f"Sync failed: {api_result.get('message', 'Unknown error')}")
            return JSONResponse(content=SyncResponse(status=desired_status).model_dump(by_alias=True), status_code=500)

    elif compass_state:
        # Check if update needed
        needs_update = False

        # Resource-specific diff logic
        diff_fields = {
            "Metric": ["description", "format", "grading-system"],
            "Scorecard": ["description", "importance", "state"],
            "Component": ["description", "componentType", "slug", "typeId"]
        }.get(resource_kind, [])

        for field in diff_fields:
            if resource_spec.get(field) != compass_state.get(field):
                needs_update = True
                break

        if needs_update:
            # Update resource
            logger.info(f"Updating {resource_kind} with ID {compass_id}")
            api_result = call_compass_api(resource_kind, "update", resource_spec, status=current_status,
                                          compass_id=compass_id)

            if api_result["success"]:
                # Handle resource-specific updates
                if resource_kind == "Component" and "metricSources" in api_result:
                    desired_status["metricSources"] = api_result["metricSources"]
                if resource_kind == "Scorecard":
                    desired_status["metricsSummary"] = ", ".join(
                        [c.get("metricName", "unknown") for c in resource_spec.get("criteria", [])])

                set_condition(desired_status["conditions"], "Ready", "True", f"{resource_kind}UpdatedInCompass",
                              f"{resource_kind} updated")
                set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                              f"{resource_kind} synced (updated).")
            elif api_result.get("transient"):
                logger.warning(f"Transient error during update: {api_result.get('message')}")
                set_condition(desired_status["conditions"], "Synced", "Unknown", "TransientError",
                              f"Transient error: {api_result.get('message')}")
                set_condition(desired_status["conditions"], "Ready", "Unknown", "TransientError",
                              f"Transient error: {api_result.get('message')}")
                return JSONResponse(content=SyncResponse(status=desired_status).model_dump(by_alias=True),
                                    status_code=200)
            else:
                logger.error(f"Persistent error during update: {api_result.get('message')}")
                set_condition(desired_status["conditions"], "Ready", "False", f"UpdateFailed",
                              f"Update failed: {api_result.get('message')}")
                set_condition(desired_status["conditions"], "Synced", "False", "SyncFailed",
                              f"Sync failed: {api_result.get('message')}")
                return JSONResponse(content=SyncResponse(status=desired_status).model_dump(by_alias=True),
                                    status_code=500)
        else:
            logger.info(f"No differences detected for {resource_kind} {compass_id}")

            if resource_kind == "Scorecard":
                desired_status["metricsSummary"] = ", ".join(
                    [c.get("metricName", "unknown") for c in resource_spec.get("criteria", [])])
                if compass_state and "criteria" in compass_state:
                    desired_status["criteria"] = compass_state["criteria"]
            elif resource_kind == "Component" and compass_state and "metricSources" in compass_state:
                desired_status["metricSources"] = compass_state["metricSources"]

            set_condition(desired_status["conditions"], "Ready", "True", "InSync", f"{resource_kind} in sync")
            set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess", f"{resource_kind} in sync")

    if get_condition(desired_status["conditions"], "Synced"):
        desired_status["lastEvaluatedTime"] = datetime.now(timezone.utc).isoformat()

    return JSONResponse(content=SyncResponse(status=desired_status).model_dump(by_alias=True), status_code=200)
