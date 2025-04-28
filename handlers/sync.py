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
    set_condition(desired_status["conditions"], "Ready", "Unknown", "Reconciling",
                  f"Starting reconciliation for {resource_kind}.")
    set_condition(desired_status["conditions"], "Synced", "Unknown", "Reconciling",
                  f"Starting synchronization for {resource_kind}.")

    compass_id = desired_status.get("id")
    compass_state, desired_status = fetch_compass_state(compass_id, resource_kind, resource_spec,
                                                        current_status, desired_status)

    if not compass_id or not compass_state:
        desired_status = create_compass_resource(resource_kind, resource_spec, current_status, desired_status)
    elif compass_state:
        desired_status = update_compass_resource(resource_kind, resource_spec, compass_id,
                                                 compass_state, current_status, desired_status)

    desired_children = generate_child_resources(resource_kind, parent, desired_status)

    if is_sync_successful(desired_status):
        desired_status["lastEvaluatedTime"] = datetime.now(timezone.utc).isoformat()

    return JSONResponse(
        content=SyncResponse(status=desired_status, children=desired_children).model_dump(by_alias=True),
        status_code=200
    )
