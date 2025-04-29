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
    Handles creation, updates, and status management with resource version tracking.
    """
    parent = request_data.parent.model_dump(by_alias=True)
    current_status = parent.get("status", {})
    desired_status = current_status.copy()

    # Initialize conditions if not present
    desired_status.setdefault("conditions", [])

    # Get key metadata
    current_generation = parent["metadata"]["generation"]
    observed_generation = current_status.get("observedGeneration", 0)
    compass_id = current_status.get("id")
    resource_name = parent["metadata"]["name"]
    current_resource_version = parent["metadata"].get("resourceVersion")
    last_resource_version = current_status.get("lastResourceVersion")

    logger.info(
        f"Processing {resource_kind}/{resource_name} - "
        f"Generation: {current_generation}, Observed: {observed_generation}, "
        f"ResourceVersion: {current_resource_version}, LastResourceVersion: {last_resource_version}"
    )

    # Check if this is a redundant update - same resource version and we've processed it before
    if current_resource_version == last_resource_version and compass_id:
        logger.info(
            f"Skipping redundant sync for {resource_kind}/{resource_name} - "
            f"Resource version unchanged: {current_resource_version}"
        )
        return JSONResponse(
            content=SyncResponse(
                status=current_status,
                children=[],  # No children updates needed
                resyncAfterSeconds=3600  # Longer resync time for unchanged resources
            ).model_dump(by_alias=True),
            status_code=200
        )

    # Track current reconciliation
    set_condition(desired_status["conditions"], "Synced", "Unknown", "Reconciling",
                  f"Starting synchronization for {resource_kind}.")

    # Determine if we need to do a full reconciliation
    need_reconciliation = (
            current_generation > observed_generation or  # Spec changed
            not compass_id  # No ID means not yet created in Compass
    )

    if need_reconciliation:
        logger.info(f"Full reconciliation needed for {resource_kind}/{resource_name}")

        if not compass_id:
            # No ID, so create the resource in Compass
            logger.info(f"No Compass ID found for {resource_kind}/{resource_name}. Creating new resource.")
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
                    f"Resource {resource_kind}/{resource_name} has ID but doesn't exist in Compass")
                desired_status.pop("id", None)  # Remove the invalid ID
                desired_status = create_compass_resource(resource_kind, parent, current_status, desired_status)

        # Update generation and timestamp if reconciliation was successful
        if is_sync_successful(desired_status):
            desired_status["observedGeneration"] = current_generation
            desired_status["lastEvaluatedTime"] = datetime.now(timezone.utc).isoformat()
    else:
        logger.info(
            f"Skipping spec reconciliation for {resource_kind}/{resource_name} - "
            f"Spec has not changed (generation {current_generation})"
        )

        # Still ensure we have the right conditions set
        set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                      f"{resource_kind} in sync with Compass.")
        set_condition(desired_status["conditions"], "Ready", "True", "AlreadyInSync",
                      f"{resource_kind} is already in sync with Compass.")

    # Update the resource version tracking to avoid future redundant syncs
    desired_status["lastResourceVersion"] = current_resource_version

    # Generate child resources based on resource type
    desired_children = []
    # if resource_kind.lower() == ResourceKind.METRIC:
    #     existing_children = request_data.children.get("batch/v1", {}).get("CronJob", {})
    #
    #     # Check if we have an existing CronJob child for this resource
    #     has_existing_cronjob = bool(existing_children)
    #
    #     # Only generate children if we need reconciliation or there are no existing children
    #     if need_reconciliation or not has_existing_cronjob:
    #         desired_children = generate_child_resources(resource_kind, parent, desired_status)
    #         logger.info(f"Generated {len(desired_children)} child resources for {resource_kind}/{resource_name}")
    #     else:
    #         logger.info(f"Reusing existing child resources for {resource_kind}/{resource_name}")

    # Set a longer resync period if no reconciliation was needed
    resync_seconds = 600
    if not need_reconciliation:
        resync_seconds = 3600  # 1 hour instead of 10 minutes

    # CRITICAL: Always return a full status object to ensure all fields are preserved
    return JSONResponse(
        content=SyncResponse(
            status=desired_status,
            children=desired_children,
            resyncAfterSeconds=resync_seconds
        ).model_dump(by_alias=True),
        status_code=200
    )