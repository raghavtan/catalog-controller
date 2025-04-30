import logging
import traceback

from service.models.models import MetacontrollerRequest, SyncResponse
from service.scheduler.scheduler import build_metric_evaluator_cronjob
from service.utils.compass import CompassAPI

logger = logging.getLogger("MetricHandler")


async def sync_metric(request_data: MetacontrollerRequest):
    parent = request_data.parent.model_dump(by_alias=True)

    metric_name = parent['metadata']['name']
    try:
        response_status = {"id": None, "cronJob": None}
        compass_client = CompassAPI()

        if parent.get('status', {}).get('id'):
            metric_id = parent['status']['id']
            logger.info(f"Found existing ID {metric_id} for metric {metric_name}")
            response = await compass_client.dummy_call("get", "metric", parent)

            if response['status_code'] == 200:
                compass_id = response.get('id')
                if compass_id:
                    response_status["id"] = compass_id
                    if compass_id != metric_id:
                        logger.warning(
                            f"Metric ID mismatch for {metric_name}. Expected: {metric_id}, Found: {compass_id}")
                else:
                    logger.warning(
                        f"Metric {metric_name} not found in Compass despite having ID. Creating new resource.")
                    response_status["id"] = await create_metric(compass_client, parent, metric_name)
            else:
                logger.error(f"Failed to retrieve metric {metric_name}. Status code: {response['status_code']}")
        else:
            logger.info(f"No ID found for metric {metric_name}. Creating new.")
            response_status["id"] = await create_metric(compass_client, parent, metric_name)

        if response_status["id"]:

            desired_children, response_status["cronJob"] = build_metric_evaluator_cronjob(parent)
            logger.info(f"CronJob processing result for {metric_name}: {response_status["cronJob"]}")

        return SyncResponse(status=response_status, children=desired_children).model_dump(by_alias=True), 200
    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Error syncing metric {parent['metadata']['name']}: {str(e)}\nStack trace:\n{stack_trace}")
        return SyncResponse(status={"error": str(e)}, children=[]).model_dump(by_alias=True), 500


async def create_metric(compass_client, parent, metric_name):
    try:
        response = await compass_client.dummy_call("create", "metric", parent)
        if response['status_code'] == 201:
            logger.info(f"Created new metric {metric_name} with ID: {response.get('id')}")
            return response.get('id')
        else:
            logger.error(f"Failed to create metric {metric_name}. Status code: {response['status_code']}")
            return None
    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Exception in create_metric for {metric_name}: {str(e)}\nStack trace:\n{stack_trace}")
        raise
