import traceback
from typing import List, Dict

from kubernetes import client, config
from service.models.models import MetacontrollerRequest, SyncResponse
from service.utils.compass import CompassAPI
from service.utils.log import get_logger

logger = get_logger("ComponentHandler")


async def sync_component(request_data: MetacontrollerRequest):
    parent = request_data.parent.model_dump(by_alias=True)
    component_name = parent['metadata']['name']

    try:
        compass_client = CompassAPI()
        response_status = {"id": None, "ownerId": None, "metricAssociation": []}
        component_id = parent.get('status', {}).get('id')

        if component_id:
            logger.debug(f"Found existing ID {component_id} for component {component_name}")
            response = await compass_client.dummy_call("get", "component", parent)

            if response['status_code'] == 200 and response.get('id') == component_id:
                compass_id = response.get('id')
                response_status["id"] = compass_id
                response_status["ownerId"] = response.get('ownerId')
                current_metrics = response.get('metricAssociation', [])
                component_type_id = parent.get('spec', {}).get('typeId')
                applicable_metrics = await get_applicable_metrics(component_type_id)

                if not metrics_match(current_metrics, applicable_metrics):
                    logger.debug(
                        f"Metrics mismatch for component {component_name}. Recreating component with updated metrics.")
                    response_status = await create_component_with_metrics(compass_client, parent, component_name)
                else:
                    logger.debug(f"Metrics match for component {component_name}. Using existing metrics.")
                    response_status["metricAssociation"] = current_metrics 
            else:
                logger.debug(f"Component {component_name} not found in Compass or ID mismatch. Creating new resource.")
                response_status = await create_component_with_metrics(compass_client, parent, component_name)
        else:
            logger.debug(f"No ID found for component {component_name}. Creating new.")
            response_status = await create_component_with_metrics(compass_client, parent, component_name)

        return SyncResponse(status=response_status, children=[]).model_dump(by_alias=True), 200

    except Exception as e:
        logger.error(
            f"Error SyncComponent {component_name}: {str(e)}\nStack trace:\n{traceback.format_exc()}")
        return SyncResponse(status={"error": str(e)}, children=[]).model_dump(by_alias=True), 500


def metrics_match(current_metrics: List[Dict], applicable_metrics: List[Dict]) -> bool:
    if len(current_metrics) != len(applicable_metrics):
        return False

    current_dict = {m.get('metricName'): m.get('metricId') for m in current_metrics if
                    'metricName' in m and 'metricId' in m}
    applicable_dict = {m.get('metricName'): m.get('metricId') for m in applicable_metrics if
                       'metricName' in m and 'metricId' in m}
    for name, metric_id in applicable_dict.items():
        if name not in current_dict or current_dict[name] != metric_id:
            return False

    return True


async def create_component_with_metrics(compass_client, parent, component_name):
    try:
        component_type_id = parent.get('spec', {}).get('typeId')
        if not component_type_id:
            logger.error(f"Missing typeId for component {component_name}")
            return {"id": None, "ownerId": None, "metricAssociation": []}

        applicable_metrics = await get_applicable_metrics(component_type_id)
        request_data = {"component": parent, "metrics": applicable_metrics}

        response = await compass_client.dummy_call("create", "component_with_metrics", request_data)

        if response['status_code'] == 201:
            logger.debug(f"Created new component {component_name} with ID: {response.get('id')}")

            result = {"id": response.get('id'), "ownerId": response.get('ownerId'), "metricAssociation": []}

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
                                applicable_metrics.append({"metricName": metric_name, "metricId": metric_id})
                        except client.ApiException:
                            logger.warning(f"Metric {metric_name} referenced in scorecard but not found")

        return applicable_metrics

    except Exception as e:
        logger.error(f"Error getting applicable metrics: {str(e)}")
        return []