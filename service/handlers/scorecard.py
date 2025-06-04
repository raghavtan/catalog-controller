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
        metrics_summary, metric_association = await validate_metrics(parent)
        logger.debug(f"Metrics associations for scorecard {scorecard_name}: {metric_association}")

        # Update parent with metric IDs BEFORE checking if it exists
        parent = update_payload_with_metric_ids(metric_association, parent)

        # Store a deep copy of the parent to use in case we need to create/update
        import copy
        parent_with_metrics = copy.deepcopy(parent)

        compass_id = await ensure_scorecard_exists(compass_client, parent, scorecard_name)

        if not compass_id:
            logger.error(f"Failed to ensure scorecard {scorecard_name} exists")
            return SyncResponse(status={"error": "Failed to create or import scorecard"}, children=[]).model_dump(
                by_alias=True), 500

        current_scorecard = await compass_client.get_by_id("scorecard", compass_id)

        if current_scorecard['status_code'] != 200:
            logger.error(f"Failed to retrieve scorecard {scorecard_name} after creation/import")
            return SyncResponse(status={"error": "Failed to retrieve scorecard"}, children=[]).model_dump(
                by_alias=True), 500

        if await scorecard_spec_differences(parent_with_metrics, current_scorecard['data']):
            logger.info(f"Spec differences detected for scorecard {scorecard_name}. Updating...")
            # Use the parent_with_metrics which has the metricDefinitionId
            update_response = await compass_client.update("scorecard", compass_id, parent_with_metrics)

            if update_response['status_code'] != 200:
                logger.error(f"Failed to update scorecard {scorecard_name}")
                logger.debug(f"Update response: {update_response}")
                return SyncResponse(status={"error": "Failed to update scorecard"}, children=[]).model_dump(
                    by_alias=True), 500

        response_status["id"] = compass_id

        if compass_id:
            response_status["metricsSummary"], response_status[
                "metricAssociation"] = metrics_summary, metric_association

        return SyncResponse(status=response_status, children=[]).model_dump(by_alias=True), 200

    except Exception as e:
        logger.error(f"Error SyncScoreCard {scorecard_name}: {str(e)}\nStack trace:\n{traceback.format_exc()}")
        return SyncResponse(status={"error": str(e)}, children=[]).model_dump(by_alias=True), 500


async def ensure_scorecard_exists(compass_client: CompassAPI, parent: dict, scorecard_name: str) -> str:
    """
    Ensure scorecard exists in Compass. Try import by name if no status ID, otherwise validate existing ID.
    Returns compass_id or None if failed.
    """
    try:
        status_id = parent.get('status', {}).get('id')

        if status_id:
            logger.debug(f"Found existing ID {status_id} for scorecard {scorecard_name}")
            response = await compass_client.get_by_id("scorecard", status_id)

            if response['status_code'] == 200:
                logger.debug(f"Scorecard {scorecard_name} exists in Compass with ID {status_id}")
                return status_id
            else:
                logger.warning(
                    f"Scorecard {scorecard_name} with ID {status_id} not found in Compass. Will try import by name.")

        logger.debug(f"Attempting to import scorecard {scorecard_name} by name")
        import_response = await compass_client.get_by_name("scorecard", scorecard_name)

        if import_response['status_code'] == 200:
            imported_id = import_response['data'].get('id')
            logger.info(f"Successfully imported existing scorecard {scorecard_name} with ID {imported_id}")
            return imported_id

        logger.debug(f"Scorecard {scorecard_name} not found in Compass. Creating new scorecard.")
        # Note that we're using the parent that already has metricDefinitionId
        create_response = await create_scorecard(compass_client, parent, scorecard_name)
        return create_response

    except Exception as e:
        logger.error(f"Error ensuring scorecard {scorecard_name} exists: {str(e)}")
        return None


async def create_scorecard(compass_client, parent, scorecard_name):
    """Create new scorecard in Compass"""
    try:
        response = await compass_client.create("scorecard", parent)

        if response['status_code'] == 201:
            logger.info(f"Created new scorecard {scorecard_name} with ID: {response['data'].get('id')}")
            return response['data'].get('id')
        else:
            logger.error(f"Failed to create scorecard {scorecard_name}. Status code: {response['status_code']}")
            return None

    except Exception as e:
        logger.error(f"Exception CreateScoreCard: {scorecard_name}: {str(e)}\nStack trace:\n{traceback.format_exc()}")
        raise


async def validate_metrics(parent: Dict[str, Any]) -> Tuple[str, List[Dict[str, str]]]:
    """Validate metrics referenced in scorecard criteria"""
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


def update_payload_with_metric_ids(metric_association, payload):
    metric_map = {item['metricName']: item['metricId'] for item in metric_association}
    for criterion in payload['spec']['criteria']:
        metric_name = criterion['hasMetricValue']['metricName']
        if metric_name in metric_map:
            criterion['hasMetricValue']['metricDefinitionId'] = metric_map[metric_name]
    return payload


async def scorecard_spec_differences(k8s_resource, compass_resource):
    k8s_resource_spec = k8s_resource.get('spec', {})
    if not k8s_resource_spec:
        logger.debug("K8s resource spec is empty or missing")
        return False

    if k8s_resource_spec.get('name') != compass_resource.get('name'):
        logger.debug(f"[ScoreCards] [{k8s_resource_spec.get('name')}] Name mismatch between K8s and Compass resources")
        return True
    if k8s_resource_spec.get('description') != compass_resource.get('description'):
        logger.debug(f"[ScoreCards] [{k8s_resource_spec.get('name')}] Description mismatch between K8s and Compass "
                     f"resources")
        return True
    if k8s_resource_spec.get('state') != compass_resource.get('state'):
        logger.debug(f"[ScoreCards] [{k8s_resource_spec.get('name')}]state mismatch between K8s and Compass resources")
        return True
    if k8s_resource_spec.get('componentTypeIds') != compass_resource.get('componentTypeIds'):
        logger.debug(f"[ScoreCards] [{k8s_resource_spec.get('name')}] ComponentTypeIds mismatch between K8s and "
                     f"Compass resources")
        return True
    if k8s_resource_spec.get('criteria') != compass_resource.get('criteria'):
        logger.debug(f"[ScoreCards] [{k8s_resource_spec.get('name')}] Criteria mismatch between K8s and Compass "
                     f"resources")
        return True
    return False