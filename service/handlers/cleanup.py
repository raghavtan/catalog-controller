import logging
import traceback

from service.models.models import MetacontrollerRequest, FinalizeResponse
from service.utils.compass import CompassAPI

logger = logging.getLogger("FinalizeHandler")


async def finalize_resource(request_data: MetacontrollerRequest):
    try:
        parent = request_data.parent.model_dump(by_alias=True)
        name = parent["metadata"]["name"]
        kind = parent["kind"].lower()
        compass_id = parent["status"].get('id')

        if not compass_id:
            logger.info(f"No Compass ID for {kind} {name}. Nothing to delete.")
            return FinalizeResponse(finalized=True).model_dump(by_alias=True), 200

        delete_result = CompassAPI().dummy_call("delete", kind, parent)

        if delete_result["success"]:
            logger.info(f"{kind} {compass_id} deleted successfully from Compass.")
            return FinalizeResponse(finalized=True).model_dump(by_alias=True), 200

        is_transient = delete_result.get("transient", False)
        log_func = logger.warning if is_transient else logger.error
        error_type = "Transient" if is_transient else "Persistent"
        log_func(f"{error_type} error finalizing {kind} {name}: {delete_result.get('message')}")

        return FinalizeResponse(finalized=False).model_dump(by_alias=True), 500
    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Error deleting {parent['metadata']['name']}: {str(e)}\nStack trace:\n{stack_trace}")
        return FinalizeResponse(finalized=False, status={"error": str(e)}).model_dump(by_alias=True), 500