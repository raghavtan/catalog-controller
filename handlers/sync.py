import logging
import sys
from datetime import datetime, timezone

from fastapi.responses import JSONResponse

from handlers.children import generate_child_resources
from handlers.compass import fetch_compass_state, create_compass_resource, update_compass_resource
from models import MetacontrollerRequest, SyncResponse
from utils import set_condition, is_sync_successful

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SyncHandler")


def sync_resource(request_data: MetacontrollerRequest, resource_kind: str) -> JSONResponse:
    parent = request_data.parent.model_dump(by_alias=True)
    resource_spec = parent["spec"]
    current_status = parent.get("status", {})
    desired_status = current_status.copy()

    desired_status.setdefault("conditions", [])
    set_condition(desired_status["conditions"], "Synced", "Unknown", "Reconciling",
                  f"Starting synchronization for {resource_kind}.")

    current_generation = parent["metadata"]["generation"]
    observed_generation = current_status.get("observedGeneration", 0)
    compass_id_in_status = current_status.get("id")

    if current_generation > observed_generation or not compass_id_in_status:
        logger.info(
            f"Reconciling generation {current_generation} (observed: {observed_generation}) "
            f"for {resource_kind}/{parent['metadata']['name']}. "
            f"Compass ID present in status: {bool(compass_id_in_status)}")

        compass_id = desired_status.get("id")
        compass_state, desired_status = fetch_compass_state(compass_id, resource_kind, resource_spec,
                                                            current_status, desired_status)

        if not compass_id or not compass_state:
            desired_status = create_compass_resource(resource_kind, resource_spec, current_status, desired_status)
        elif compass_state:
            desired_status = update_compass_resource(resource_kind, resource_spec, compass_id,
                                                     compass_state, current_status, desired_status)

        if is_sync_successful(desired_status):
            desired_status["observedGeneration"] = current_generation
            desired_status["lastEvaluatedTime"] = datetime.now(
                timezone.utc).isoformat()
    else:
        logger.info(
            f"Skipping reconciliation for generation {current_generation} (observed: {observed_generation}) "
            f"for {resource_kind}/{parent['metadata']['name']} - spec has not changed.")
        if is_sync_successful(current_status):
            set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                          f"{resource_kind} in sync with Compass.")

    desired_children = generate_child_resources(resource_kind, parent, desired_status)

    logger.info(f"Desired children: {desired_children}")
    logger.info(f"Desired status: {desired_status}")

    if desired_status != current_status:
        logger.info(f"Returning Updated status {resource_kind}/{parent['metadata']['name']}.")
        return JSONResponse(
            content=SyncResponse(status=desired_status, children=desired_children).model_dump(by_alias=True),
            status_code=200
        )
    else:
        logger.info(f"No status update required for {resource_kind}/{parent['metadata']['name']}.")
        return JSONResponse(
            content=SyncResponse(status={}, children=desired_children).model_dump(by_alias=True),
            status_code=200
        )
