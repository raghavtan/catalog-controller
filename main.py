import logging

from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse

from service.handlers.cleanup import finalize_resource
from service.handlers.metric import sync_metric
from service.handlers.scorecard import sync_scorecard
from service.handlers.component import sync_component
from service.models.models import MetacontrollerRequest
from service.utils.endpoint_filter import EndpointFilter
from service.utils.log import get_logger

logger = get_logger("CatalogController")

app = FastAPI(swagger_ui_parameters={"syntaxHighlight.theme": "obsidian"})
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(EndpointFilter(path="/healthz"))


@app.post("/sync/{resource_type}")
async def sync_resource(resource_type: str, request_data: MetacontrollerRequest = Body(...)):
    logger.info(f"Received sync request for {resource_type}: {request_data.parent.metadata.name}")
    logger.debug(f"Request data: {request_data}")

    if resource_type == "metric":
        response_content, status_code = await sync_metric(request_data)
    elif resource_type == "scorecard":
        response_content, status_code = await sync_scorecard(request_data)
    elif resource_type == "component":
        response_content, status_code = await sync_component(request_data)
    else:
        logger.error(f"Unsupported resource type: {resource_type}")
        return JSONResponse({"error": "Unsupported resource type"}, status_code=400)

    logger.debug(f"Response content: {response_content}, status code: {status_code}")
    return JSONResponse(response_content, status_code)


@app.post("/finalize")
async def finalize(request_data: MetacontrollerRequest = Body(...)):
    logger.info(f"Received finalize request for {request_data.parent.kind}:{request_data.parent.metadata.name}")
    response_content, status_code = await finalize_resource(request_data)
    return JSONResponse(response_content, status_code)


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}
