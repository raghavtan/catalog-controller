import logging
import sys

from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse

from service.handlers.cleanup import finalize_resource
from service.handlers.metric import sync_metric
from service.handlers.scorecard import sync_scorecard
from service.handlers.component import sync_component
from service.models.models import MetacontrollerRequest
from service.utils.endpoint_filter import EndpointFilter

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format='%(asctime)s [%(levelname)s] [%(name)s] - %(message)s')
logger = logging.getLogger("CatalogController")

app = FastAPI(swagger_ui_parameters={"syntaxHighlight.theme": "obsidian"})
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(EndpointFilter(path="/healthz"))


@app.post("/metric/sync")
async def metric(request_data: MetacontrollerRequest = Body(...)):
    logger.info(f"Received sync request for metric: {request_data.parent.metadata.name}")
    response_content, status_code = await sync_metric(request_data)
    return JSONResponse(response_content, status_code)


@app.post("/scorecard/sync")
async def metric(request_data: MetacontrollerRequest = Body(...)):
    logger.info(f"Received sync request for scorecard: {request_data.parent.metadata.name}")
    response_content, status_code = await sync_scorecard(request_data)
    return JSONResponse(response_content, status_code)


@app.post("/component/sync")
async def metric(request_data: MetacontrollerRequest = Body(...)):
    logger.info(f"Received sync request for component: {request_data.parent.metadata.name}")
    response_content, status_code = await sync_component(request_data)
    return JSONResponse(response_content, status_code)


@app.post("/finalize")
async def finalize(request_data: MetacontrollerRequest = Body(...)):
    logger.info(f"Received finalize request for {request_data.parent.kind}:{request_data.parent.metadata.name}")
    response_content, status_code = await finalize_resource(request_data)
    return JSONResponse(response_content, status_code)


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}
