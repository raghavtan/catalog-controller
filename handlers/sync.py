import logging
import sys
from datetime import datetime, timezone

from fastapi.responses import JSONResponse


from handlers.compass import fetch_compass_state, create_compass_resource, update_compass_resource
from models import MetacontrollerRequest, SyncResponse, ResourceKind
from utils import set_condition, is_sync_successful, get_condition

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SyncHandler")


def sync_resource(request_data: MetacontrollerRequest, resource_kind: str) -> JSONResponse:
    parent = request_data.parent.model_dump(by_alias=True)
    current_status = parent.get("status", {})
    desired_status = current_status.copy()
    desired_status.setdefault("conditions", [])
    current_generation = parent["metadata"]["generation"]
    observed_generation = current_status.get("observedGeneration", 0)
    compass_id = current_status.get("id")
    resource_name = parent["metadata"]["name"]
    current_resource_version = parent["metadata"].get("resourceVersion")

    logger.info(
        f"Processing {resource_kind}/{resource_name} - "
        f"Generation: {current_generation}, Observed: {observed_generation}, "
        f"ResourceVersion: {current_resource_version}"
    )

    need_reconciliation = (
            current_generation > observed_generation or
            not compass_id
    )

    if need_reconciliation:
        logger.info(f"Full reconciliation needed for {resource_kind}/{resource_name}")

        set_condition(desired_status["conditions"], "Synced", "Unknown", "Reconciling",
                      f"Starting synchronization for {resource_kind}.")

        if not compass_id:
            logger.info(f"No Compass ID found for {resource_kind}/{resource_name}. Creating new resource.")
            desired_status = create_compass_resource(resource_kind, parent, current_status, desired_status)
        else:
            compass_state, desired_status = fetch_compass_state(
                compass_id, resource_kind, parent, current_status, desired_status
            )

            if compass_state:
                desired_status = update_compass_resource(
                    resource_kind, parent, compass_id, compass_state, current_status, desired_status
                )
            else:
                logger.warning(
                    f"Resource {resource_kind}/{resource_name} has ID '{compass_id}' but doesn't exist in Compass. Attempting recreation.")
                desired_status.pop("id", None)
                desired_status = create_compass_resource(resource_kind, parent, current_status, desired_status)

        if is_sync_successful(desired_status):
            desired_status["observedGeneration"] = current_generation
            desired_status["lastEvaluatedTime"] = datetime.now(timezone.utc).isoformat()
            set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                          f"ResourceKind.{resource_kind.upper()} synced with Compass.")
            set_condition(desired_status["conditions"], "Ready", "True", "ReconciliationComplete",
                          f"ResourceKind.{resource_kind.upper()} reconciliation complete.")

    else:
        logger.info(
            f"Skipping spec reconciliation for {resource_kind}/{resource_name} - "
            f"Spec has not changed (generation {current_generation})"
        )
        set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                      f"{resource_kind} in sync with Compass.")
        set_condition(desired_status["conditions"], "Ready", "True", "AlreadyInSync",
                      f"{resource_kind} is already in sync with Compass.")

    desired_children = []
    # if resource_kind.lower() == ResourceKind.METRIC:
    #     existing_children = request_data.children.get("batch/v1", {}).get("CronJob", {})
    #     has_existing_cronjob = bool(existing_children)
    #     if need_reconciliation or not has_existing_cronjob:
    #         desired_children = generate_child_resources(resource_kind, parent, desired_status)
    #         logger.info(f"Generated {len(desired_children)} child resources for {resource_kind}/{resource_name}")
    #     else:
    #         logger.info(f"Reusing existing child resources for {resource_kind}/{resource_name}")

    resync_seconds = 600
    ready_condition = get_condition(desired_status.get("conditions", []), "Ready")
    synced_condition = get_condition(desired_status.get("conditions", []), "Synced")

    # Check if both Ready and Synced conditions are present and True
    if (ready_condition is not None and ready_condition.get("status") == "True" and
        synced_condition is not None and synced_condition.get("status") == "True"):
        resync_seconds = 3600
    return JSONResponse(
        content=SyncResponse(
            status=desired_status,
            children=desired_children,
            resyncAfterSeconds=resync_seconds
        ).model_dump(by_alias=True),
        status_code=200
    )
