from service.utils.log import get_logger
import traceback
from typing import List, Dict, Any, Tuple, Optional

from service.models.models import MetacontrollerRequest, SyncResponse
from service.utils.compass import CompassAPI
from kubernetes import client, config

logger = get_logger("ScorecardHandler")


async def sync_scorecard(request_data: MetacontrollerRequest):
    parent = request_data.parent.model_dump(by_alias=True)

    scorecard_name = parent['metadata']['name']
    try:
        response_status = {"id": None, "metricsSummary": None, "metricAssociation": []}
        compass_client = CompassAPI()

        if parent.get('status', {}).get('id'):
            scorecard_id = parent['status']['id']
            logger.debug(f"Found existing ID {scorecard_id} for scorecard {scorecard_name}")
            response = await compass_client.dummy_call("get", "scorecard", parent)

            if response['status_code'] == 200:
                compass_id = response.get('id')
                if compass_id:
                    response_status["id"] = compass_id
                    if compass_id != scorecard_id:
                        logger.warning(
                            f"Scorecard ID mismatch for {scorecard_name}. Expected: {scorecard_id}, Found: {compass_id}")
                else:
                    logger.warning(
                        f"Scorecard {scorecard_name} not found in Compass despite having ID. Creating new resource.")
                    response_status["id"] = await create_scorecard(compass_client, parent, scorecard_name)
            else:
                logger.error(f"Failed to retrieve scorecard {scorecard_name}. Status code: {response['status_code']}")
        else:
            logger.debug(f"No ID found for scorecard {scorecard_name}. Creating new.")
            response_status["id"] = await create_scorecard(compass_client, parent, scorecard_name)

        if response_status["id"]:
            response_status["metricsSummary"], response_status["metricAssociation"] = await validate_metrics(parent)

        return SyncResponse(status=response_status, children=[]).model_dump(by_alias=True), 200

    except Exception as e:
        logger.error(f"Error SyncScoreCard {parent['metadata']['name']}: {str(e)}\nStack trace:\n{traceback.format_exc()}")
        return SyncResponse(status={"error": str(e)}, children=[]).model_dump(by_alias=True), 500


async def create_scorecard(compass_client, parent, scorecard_name):
    try:
        response = await compass_client.dummy_call("create", "scorecard", parent)
        if response['status_code'] == 201:
            logger.debug(f"Created new scorecard {scorecard_name} with ID: {response.get('id')}")
            return response.get('id', None)
        else:
            logger.error(f"Failed to create scorecard {scorecard_name}. Status code: {response['status_code']}")
            return None
    except Exception as e:
        logger.error(f"Exception CreateScoreCard: {scorecard_name}: {str(e)}\nStack trace:\n{traceback.format_exc()}")
        raise


async def validate_metrics(parent: Dict[str, Any]) -> Tuple[str, List[Dict[str, str]]]:
    try:
        config.load_incluster_config()
        custom_api = client.CustomObjectsApi()

        metric_names, valid_metrics, invalid_metrics, metric_associations = [], [], [], []

        for criterion in parent.get('spec', {}).get('criteria', []):
            has_metric = criterion.get('hasMetricValue', {})
            if has_metric and 'metricName' in has_metric:
                metric_names.append(has_metric['metricName'])

        for metric_name in metric_names:
            try:
                metric = custom_api.get_cluster_custom_object(
                    group="catalog.onefootball.com",
                    version="v1alpha1",
                    plural="metrics",
                    name=metric_name
                )

                metric_id = metric.get('status', {}).get('id')
                if metric_id:
                    valid_metrics.append(metric_name)
                    metric_associations.append({
                        "metricName": metric_name,
                        "metricId": metric_id
                    })
                else:
                    valid_metrics.append(f"{metric_name}(PENDING)")
            except client.ApiException:
                invalid_metrics.append(f"{metric_name}(INVALID)")

        metrics_summary = ", ".join(valid_metrics + invalid_metrics)

        return metrics_summary, metric_associations

    except Exception as e:
        logger.error(f"Error validating metrics: {str(e)}")
        return f"Error validating metrics: {str(e)}", []