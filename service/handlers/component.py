import logging
import traceback
from typing import List, Dict, Any, Tuple, Optional

from service.models.models import MetacontrollerRequest, SyncResponse
from service.utils.compass import CompassAPI
from kubernetes import client, config

logger = logging.getLogger("ComponentHandler")


async def sync_component(request_data: MetacontrollerRequest):
    parent = request_data.parent.model_dump(by_alias=True)

    component_name = parent['metadata']['name']
    try:
        response_status = {"id": None, "ownerId": None, "metricAssociation": []}
        compass_client = CompassAPI()

        if parent.get('status', {}).get('id'):
            component_id = parent['status']['id']
            logger.info(f"Found existing ID {component_id} for component {component_name}")
            response = await compass_client.dummy_call("get", "component", parent)

            if response['status_code'] == 200:
                compass_id = response.get('id')
                if compass_id:
                    response_status["id"] = compass_id
                    response_status["ownerId"] = response.get('ownerId')
                    if compass_id != component_id:
                        logger.warning(
                            f"Component ID mismatch for {component_name}. Expected: {component_id}, Found: {compass_id}")
                else:
                    logger.warning(
                        f"Component {component_name} not found in Compass despite having ID. Creating new resource.")
                    response_status = await create_component_with_metrics(compass_client, parent, component_name)
            else:
                logger.error(f"Failed to retrieve component {component_name}. Status code: {response['status_code']}")
        else:
            logger.info(f"No ID found for component {component_name}. Creating new.")
            response_status = await create_component_with_metrics(compass_client, parent, component_name)

        return SyncResponse(status=response_status, children=[]).model_dump(by_alias=True), 200

    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Error syncing component {parent['metadata']['name']}: {str(e)}\nStack trace:\n{stack_trace}")
        return SyncResponse(status={"error": str(e)}, children=[]).model_dump(by_alias=True), 500


async def create_component_with_metrics(compass_client, parent, component_name):
    try:
        component_type_id = parent.get('spec', {}).get('typeId')
        if not component_type_id:
            logger.error(f"Missing typeId for component {component_name}")
            return {"id": None, "ownerId": None, "metricAssociation": []}

        applicable_metrics = await get_applicable_metrics(component_type_id)

        request_data = {
            "component": parent,
            "metrics": applicable_metrics
        }

        response = await compass_client.dummy_call("create", "component_with_metrics", request_data)

        if response['status_code'] == 201:
            logger.info(f"Created new component {component_name} with ID: {response.get('id')}")

            result = {
                "id": response.get('id'),
                "ownerId": response.get('ownerId'),
                "metricAssociation": []
            }

            if 'metricSources' in response:
                for metric_source in response['metricSources']:
                    result['metricAssociation'].append({
                        "metricName": metric_source.get('metricName'),
                        "metricId": metric_source.get('metricId'),
                        "metricSourceId": metric_source.get('metricSourceId')
                    })

            return result
        else:
            logger.error(f"Failed to create component {component_name}. Status code: {response['status_code']}")
            return {"id": None, "ownerId": None, "metricAssociation": []}

    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(
            f"Exception in create_component_with_metrics for {component_name}: {str(e)}\nStack trace:\n{stack_trace}")
        raise


async def get_applicable_metrics(component_type_id: str) -> List[Dict[str, str]]:
    try:
        config.load_incluster_config()
        custom_api = client.CustomObjectsApi()

        scorecards = custom_api.list_cluster_custom_object(
            group="catalog.onefootball.com",
            version="v1alpha1",
            plural="scorecards"
        )

        applicable_metrics = []

        for scorecard in scorecards.get('items', []):
            component_type_ids = scorecard.get('spec', {}).get('componentTypeIds', [])

            if component_type_id in component_type_ids:
                criteria = scorecard.get('spec', {}).get('criteria', [])

                for criterion in criteria:
                    has_metric = criterion.get('hasMetricValue', {})
                    if has_metric and 'metricName' in has_metric:
                        metric_name = has_metric['metricName']
                        try:
                            metric = custom_api.get_cluster_custom_object(
                                group="catalog.onefootball.com",
                                version="v1alpha1",
                                plural="metrics",
                                name=metric_name
                            )

                            metric_id = metric.get('status', {}).get('id')
                            if metric_id:
                                applicable_metrics.append({
                                    "metricName": metric_name,
                                    "metricId": metric_id
                                })
                        except client.ApiException:
                            logger.warning(f"Metric {metric_name} referenced in scorecard but not found")

        return applicable_metrics

    except Exception as e:
        logger.error(f"Error getting applicable metrics: {str(e)}")
        return []


async def update_component(compass_client, parent, component_name):
    try:
        response = await compass_client.dummy_call("update", "component", parent)
        if response['status_code'] == 200:
            logger.info(f"Updated component {component_name} with ID: {response.get('id')}")
            return {
                "id": response.get('id'),
                "ownerId": response.get('ownerId'),
                "metricAssociation": response.get('metricAssociation', [])
            }
        else:
            logger.error(f"Failed to update component {component_name}. Status code: {response['status_code']}")
            return None
    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Exception in update_component for {component_name}: {str(e)}\nStack trace:\n{stack_trace}")
        raise