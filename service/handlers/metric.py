from service.utils.log import get_logger
import traceback

from service.models.models import MetacontrollerRequest, SyncResponse
from service.scheduler.scheduler import build_metric_evaluator_cronjob
from service.utils.compass import CompassAPI

logger = get_logger("MetricHandler")


async def sync_metric(request_data: MetacontrollerRequest):
    parent = request_data.parent.model_dump(by_alias=True)
    metric_name = parent['metadata']['name']

    try:
        response_status = {"id": None, "cronJob": None}
        desired_children = []
        compass_client = CompassAPI()

        compass_id = await ensure_metric_exists(compass_client, parent, metric_name)

        if not compass_id:
            logger.error(f"Failed to ensure metric {metric_name} exists")
            return SyncResponse(status={"error": "Failed to create or import metric"}, children=[]).model_dump(
                by_alias=True), 500

        current_metric = await compass_client.get_by_id("metric", compass_id)

        if current_metric['status_code'] != 200:
            logger.error(f"Failed to retrieve metric {metric_name} after creation/import")
            return SyncResponse(status={"error": "Failed to retrieve metric"}, children=[]).model_dump(
                by_alias=True), 500

        if compass_client.has_spec_differences(parent, current_metric):
            logger.info(f"Spec differences detected for metric {metric_name}. Updating...")
            update_response = await compass_client.update("metric", compass_id, parent)

            if update_response['status_code'] != 200:
                logger.error(f"Failed to update metric {metric_name}")
                return SyncResponse(status={"error": "Failed to update metric"}, children=[]).model_dump(
                    by_alias=True), 500

        response_status["id"] = compass_id

        if compass_id:
            desired_children, response_status["cronJob"] = build_metric_evaluator_cronjob(parent)
            logger.debug(f"CronJob processing result for {metric_name}: {response_status['cronJob']}")

        return SyncResponse(status=response_status, children=desired_children).model_dump(by_alias=True), 200

    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Error syncing metric {metric_name}: {str(e)}\nStack trace:\n{stack_trace}")
        return SyncResponse(status={"error": str(e)}, children=[]).model_dump(by_alias=True), 500


async def ensure_metric_exists(compass_client: CompassAPI, parent: dict, metric_name: str) -> str:
    """
    Ensure metric exists in Compass. Try import by name if no status ID, otherwise validate existing ID.
    Returns compass_id or None if failed.
    """
    try:
        status_id = parent.get('status', {}).get('id')

        if status_id:
            logger.debug(f"Found existing ID {status_id} for metric {metric_name}")
            response = await compass_client.get_by_id("metric", status_id)

            if response['status_code'] == 200:
                logger.debug(f"Metric {metric_name} exists in Compass with ID {status_id}")
                return status_id
            else:
                logger.warning(
                    f"Metric {metric_name} with ID {status_id} not found in Compass. Will try import by name.")

        logger.debug(f"Attempting to import metric {metric_name} by name")
        import_response = await compass_client.get_by_name("metric", metric_name)

        if import_response['status_code'] == 200:
            imported_id = import_response.get('id')
            logger.info(f"Successfully imported existing metric {metric_name} with ID {imported_id}")
            return imported_id

        logger.debug(f"Metric {metric_name} not found in Compass. Creating new metric.")
        create_response = await create_metric(compass_client, parent, metric_name)
        return create_response

    except Exception as e:
        logger.error(f"Error ensuring metric {metric_name} exists: {str(e)}")
        return None


async def create_metric(compass_client, parent, metric_name):
    """Create new metric in Compass"""
    try:
        response = await compass_client.create("metric", parent)

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
