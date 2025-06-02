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
        compass_id = parent.get("status", {}).get('id')

        if not compass_id:
            logger.debug(f"No Compass ID for {kind} {name}. Nothing to delete.")
            return FinalizeResponse(finalized=True).model_dump(by_alias=True), 200

        delete_result = await CompassAPI().delete(kind, compass_id)

        if 200 <= delete_result["status_code"] < 300:
            logger.info(f"{kind} {compass_id} deleted successfully from Compass.")
            return FinalizeResponse(finalized=True).model_dump(by_alias=True), 200
        elif delete_result["status_code"] == 404:
            logger.warning(f"{kind} {compass_id} not found in Compass. Already deleted or never existed.")
            return FinalizeResponse(finalized=True).model_dump(by_alias=True), 200
        else:
            logger.error(
                f"Finalize Failed {kind} {name}. Status: {delete_result.get('status_code')}, Message: {delete_result.get('message', 'Unknown error')}")
            return FinalizeResponse(finalized=False).model_dump(by_alias=True), 500

    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Error deleting {parent['metadata']['name']}: {str(e)}\nStack trace:\n{stack_trace}")
        return FinalizeResponse(finalized=False, status={"error": str(e)}).model_dump(by_alias=True), 500