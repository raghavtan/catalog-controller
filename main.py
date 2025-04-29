import logging
import sys
import typing as t

from fastapi import FastAPI, Path

from handlers.cleanup import finalize_resource
from handlers.sync import sync_resource
from models import (
    MetacontrollerRequest,
    ResourceKind
)

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger("CatalogController")

app = FastAPI(swagger_ui_parameters={"syntaxHighlight.theme": "obsidian"})

logger.info(":::::::::::::::::::::::::Starting Catalog Controller::::::::::::::::::::::::::::::::")


@app.post("/sync/{resource_kind}")
async def sync_generic(
        request_data: MetacontrollerRequest,
        resource_kind: ResourceKind = Path(...,
                                           description="Resource kind to sync (e.g., 'components', 'scorecards', 'metrics')"
                                           )):
    logger.info(f"Received sync request for {resource_kind}: {request_data.parent.metadata.name}")
    logger.info(f"Request data: {request_data}")
    return sync_resource(request_data, resource_kind)


@app.post("/finalize/{resource_kind}")
async def finalize_generic(
        request_data: MetacontrollerRequest,
        resource_kind: ResourceKind = Path(...,
                                           description="Resource kind to sync (e.g., 'components', 'scorecards', 'metrics')"
                                           )):
    logger.info(f"Received finalize request for {resource_kind}: {request_data.parent.metadata.name}")
    return finalize_resource(request_data, resource_kind)


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}


class EndpointFilter(logging.Filter):
    def __init__(
            self,
            path: str,
            *args: t.Any,
            **kwargs: t.Any,
    ):
        super().__init__(*args, **kwargs)
        self._path = path

    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find(self._path) == -1


uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(EndpointFilter(path="/healthz"))
uvicorn_logger.addFilter(EndpointFilter(path="/"))