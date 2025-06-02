import traceback

from service.utils.log import get_logger
from service.models.models import MetacontrollerRequest, FinalizeResponse
from service.utils.compass import CompassAPI

logger = get_logger("FinalizeHandler")


async def finalize_resource(request_data: MetacontrollerRequest):
    parent = request_data.parent.model_dump(by_alias=True)
    try:
        name = parent["metadata"]["name"]
        kind = parent["kind"].lower()
        compass_id = parent["status"].get('id')

        if not compass_id:
            logger.debug(f"No Compass ID for {kind} {name}. Nothing to delete.")
            return FinalizeResponse(finalized=True).model_dump(by_alias=True), 200

        delete_result = await CompassAPI().dummy_call("delete", kind, parent)

        if delete_result["status_code"] >= 200:
            logger.debug(f"{kind} {compass_id} deleted successfully from Compass.")
            return FinalizeResponse(finalized=True).model_dump(by_alias=True), 200
        elif delete_result["status_code"] == 404:
            logger.warning(f"{kind} {compass_id} not found in Compass. Already deleted or never existed.")
            return FinalizeResponse(finalized=True).model_dump(by_alias=True), 200

        logger.error(f"Finalize Failed {kind} {name}. {delete_result.get('status_code'), delete_result.get('message')}")

        return FinalizeResponse(finalized=False).model_dump(by_alias=True), 500
    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Error deleting {parent['metadata']['name']}: {str(e)}\nStack trace:\n{stack_trace}")
        return FinalizeResponse(finalized=False, status={"error": str(e)}).model_dump(by_alias=True), 500