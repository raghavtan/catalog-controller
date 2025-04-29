import logging
import sys
from datetime import datetime, timezone

from fastapi.responses import JSONResponse

from handlers.children import generate_child_resources
from handlers.compass import fetch_compass_state, create_compass_resource, update_compass_resource
from models import MetacontrollerRequest, SyncResponse, ResourceKind
from utils import set_condition, is_sync_successful

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SyncHandler")


def sync_resource(request_data: MetacontrollerRequest, resource_kind: str) -> JSONResponse:
    """
    Sync handler for resources managed by the catalog controller.
    Handles creation, updates, and status management.
    """
    parent = request_data.parent.model_dump(by_alias=True)
    current_status = parent.get("status", {})
    desired_status = current_status.copy()

    # Initialize conditions if not present
    desired_status.setdefault("conditions", [])

    # Track current reconciliation
    set_condition(desired_status["conditions"], "Synced", "Unknown", "Reconciling",
                  f"Starting synchronization for {resource_kind}.")

    # Get key metadata
    current_generation = parent["metadata"]["generation"]
    observed_generation = current_status.get("observedGeneration", 0)
    compass_id = current_status.get("id")

    logger.info(
        f"Processing {resource_kind}/{parent['metadata']['name']} - "
        f"Generation: {current_generation}, Observed: {observed_generation}, Compass ID: {compass_id}"
    )

    # Determine if we need to do a full reconciliation
    need_reconciliation = (
            current_generation > observed_generation or  # Spec changed
            not compass_id  # No ID means not yet created in Compass
    )

    if need_reconciliation:
        logger.info(f"Full reconciliation needed for {resource_kind}/{parent['metadata']['name']}")

        if not compass_id:
            # No ID, so create the resource in Compass
            logger.info(f"No Compass ID found for {resource_kind}/{parent['metadata']['name']}. Creating new resource.")
            desired_status = create_compass_resource(resource_kind, parent, current_status, desired_status)
        else:
            # We have an ID, so fetch the current state from Compass
            compass_state, desired_status = fetch_compass_state(
                compass_id, resource_kind, parent, current_status, desired_status
            )

            if compass_state:
                # Resource exists in Compass, check if it needs updates
                desired_status = update_compass_resource(
                    resource_kind, parent, compass_id, compass_state, current_status, desired_status
                )
            else:
                # Resource doesn't exist in Compass despite having an ID, recreate it
                logger.warning(
                    f"Resource {resource_kind}/{parent['metadata']['name']} has ID but doesn't exist in Compass")
                desired_status.pop("id", None)  # Remove the invalid ID
                desired_status = create_compass_resource(resource_kind, parent, current_status, desired_status)

        # Update generation and timestamp if reconciliation was successful
        if is_sync_successful(desired_status):
            desired_status["observedGeneration"] = current_generation
            desired_status["lastEvaluatedTime"] = datetime.now(timezone.utc).isoformat()
    else:
        logger.info(
            f"Skipping reconciliation for {resource_kind}/{parent['metadata']['name']} - "
            f"Spec has not changed (generation {current_generation})"
        )

        # Still ensure we have the right conditions set
        set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                      f"{resource_kind} in sync with Compass.")
        set_condition(desired_status["conditions"], "Ready", "True", "AlreadyInSync",
                      f"{resource_kind} is already in sync with Compass.")

    # Generate child resources based on resource type
    desired_children = []
    if resource_kind.lower() == ResourceKind.METRIC:
        desired_children = generate_child_resources(resource_kind, parent, desired_status)

    # CRITICAL: Always return a full status object to ensure all fields are preserved
    # Even if nothing changed, returning a full status ensures we don't lose any fields
    return JSONResponse(
        content=SyncResponse(status=desired_status, children=desired_children, resyncAfterSeconds=300).model_dump(by_alias=True),
        status_code=200
    )