import logging
import sys

from fastapi import JSONResponse

from compass import call_compass_api
from models import MetacontrollerRequest, FinalizeResponse

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SyncLogger")


def finalize_resource(request_data: MetacontrollerRequest, resource_kind: str) -> JSONResponse:
    parent = request_data.parent.model_dump(by_alias=True)
    resource_name = parent["metadata"]["name"]
    compass_id = parent.get("status", {}).get("id")

    logger.info(f"Finalizing {resource_kind}: {resource_name}")

    if not compass_id:
        logger.info(f"No Compass ID for {resource_kind} {resource_name}. Nothing to delete.")
        return JSONResponse(
            content=FinalizeResponse(finalized=True).model_dump(by_alias=True),
            status_code=200
        )

    delete_result = call_compass_api(
        resource_kind,
        "delete",
        spec={},
        status=parent.get("status", {}),
        compass_id=compass_id
    )

    if delete_result["success"]:
        logger.info(f"{resource_kind} {compass_id} deleted successfully.")
        return JSONResponse(
            content=FinalizeResponse(finalized=True).model_dump(by_alias=True),
            status_code=200
        )

    log_func = logger.warning if delete_result.get("transient") else logger.error
    error_type = "Transient" if delete_result.get("transient") else "Persistent"
    log_func(f"{error_type} error finalizing {resource_kind} {resource_name}: {delete_result.get('message')}")

    return JSONResponse(
        content=FinalizeResponse(finalized=False).model_dump(by_alias=True),
        status_code=500
    )
