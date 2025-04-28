import logging
import sys

from fastapi import FastAPI, Path

from handlers.cleanup import finalize_resource
from handlers.sync import sync_resource
from models import (
    MetacontrollerRequest,
    ResourceKind
)

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger("basecontroller")

app = FastAPI()

@app.post("/sync/{resource_kind}")
async def sync_generic(
        request_data: MetacontrollerRequest,
        resource_kind: ResourceKind = Path(...,
                                           description="Resource kind to sync (e.g., 'components', 'scorecards', 'metrics')"
                                           )):
    logger.info(f"Received sync request for {resource_kind}: {request_data.parent.metadata.name}")
    return sync_resource(request_data, resource_kind)


@app.post("/finalize/{resource_kind}")
async def finalize_generic(
        request_data: MetacontrollerRequest,
        resource_kind: ResourceKind = Path(...,
                                           description="Resource kind to sync (e.g., 'components', 'scorecards', 'metrics')"
                                           )):
    logger.info(f"Received finalize request for {resource_kind}: {request_data.parent.metadata.name}")
    return finalize_resource(request_data, resource_kind)
