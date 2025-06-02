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
        response_status = {"id": None, "metricAssociation": []}
        compass_id = await ensure_component_exists(compass_client, parent, component_name)

        if not compass_id:
            logger.error(f"Failed to ensure component {component_name} exists")
            return SyncResponse(status={"error": "Failed to create or import component"}, children=[]).model_dump(
                by_alias=True), 500

        current_component = await compass_client.get_by_id("component", compass_id)

        if current_component['status_code'] != 200:
            logger.error(f"Failed to retrieve component {component_name} after creation/import")
            return SyncResponse(status={"error": "Failed to retrieve component"}, children=[]).model_dump(
                by_alias=True), 500

        if compass_client.has_spec_differences(parent, current_component):
            logger.info(f"Spec differences detected for component {component_name}. Updating...")
            update_response = await compass_client.update("component", compass_id, parent)

            if update_response['status_code'] != 200:
                logger.error(f"Failed to update component {component_name}")
                return SyncResponse(status={"error": "Failed to update component"}, children=[]).model_dump(
                    by_alias=True), 500

            current_component = update_response

        response_status["id"] = compass_id
        current_metrics = current_component.get('metricAssociation', [])
        component_type_id = parent.get('spec', {}).get('typeId')
        applicable_metrics = await get_applicable_metrics(component_type_id)

        if not metrics_match(current_metrics, applicable_metrics):
            logger.debug(f"Metrics mismatch for component {component_name}. Recreating component with updated metrics.")
            response_status = await create_component_with_metrics(compass_client, parent, component_name)
        else:
            logger.debug(f"Metrics match for component {component_name}. Using existing metrics.")
            response_status["metricAssociation"] = current_metrics

        return SyncResponse(status=response_status, children=[]).model_dump(by_alias=True), 200

    except Exception as e:
        logger.error(f"Error SyncComponent {component_name}: {str(e)}\nStack trace:\n{traceback.format_exc()}")
        return SyncResponse(status={"error": str(e)}, children=[]).model_dump(by_alias=True), 500


async def ensure_component_exists(compass_client: CompassAPI, parent: dict, component_name: str) -> str:
    """
    Ensure component exists in Compass. Try import by name if no status ID, otherwise validate existing ID.
    Returns compass_id or None if failed.
    """
    try:
        status_id = parent.get('status', {}).get('id')

        if status_id:
            logger.debug(f"Found existing ID {status_id} for component {component_name}")
            response = await compass_client.get_by_id("component", status_id)

            if response['status_code'] == 200:
                logger.debug(f"Component {component_name} exists in Compass with ID {status_id}")
                return status_id
            else:
                logger.warning(
                    f"Component {component_name} with ID {status_id} not found in Compass. Will try import by name.")

        logger.debug(f"Attempting to import component {component_name} by name")
        import_response = await compass_client.get_by_name("component", component_name)

        if import_response['status_code'] == 200:
            imported_id = import_response['data'].get('id')
            logger.info(f"Successfully imported existing component {component_name} with ID {imported_id}")
            return imported_id

        logger.debug(f"Component {component_name} not found in Compass. Creating new component.")
        create_response = await create_component_with_metrics(compass_client, parent, component_name)
        return create_response['data'].get('id')

    except Exception as e:
        logger.error(f"Error ensuring component {component_name} exists: {str(e)}")
        return None


def metrics_match(current_metrics: List[Dict], applicable_metrics: List[Dict]) -> bool:
    """Compare current metrics with applicable metrics"""
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
    """Create component with associated metrics"""
    try:
        component_type_id = parent.get('spec', {}).get('typeId')
        if not component_type_id:
            logger.error(f"Missing typeId for component {component_name}")
            return {"id": None, "metricAssociation": []}

        applicable_metrics = await get_applicable_metrics(component_type_id)
        request_data = {"component": parent, "metrics": applicable_metrics}

        response = await compass_client.create("component", request_data)

        if response['status_code'] == 201:
            logger.info(f"Created new component {component_name} with ID: {response['data'].get('id')}")

            result = {"id": response['data'].get('id'), "metricAssociation": []}

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
            return {"id": None, "metricAssociation": []}

    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(
            f"Exception in create_component_with_metrics for {component_name}: {str(e)}\nStack trace:\n{stack_trace}")
        raise


async def get_applicable_metrics(component_type_id: str) -> List[Dict[str, str]]:
    """Get metrics applicable to this component type from scorecards"""
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