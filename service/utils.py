from typing import Dict, List, Optional, Any
import logging
import kopf
from kubernetes import client

logger = logging.getLogger('utils')


def extract_id_from_status(status: Optional[Dict]) -> Optional[str]:
    """Extract the Compass ID from the resource status."""
    if not status or 'id' not in status:
        return None
    return status['id']


def extract_ari_id(ari_string: str) -> str:
    """Extract the ID portion from an ARI string."""
    parts = ari_string.split('/')
    if len(parts) >= 2:
        return parts[-1]
    return ari_string


def find_affected_resources(resource_type: str, label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
    """Find all resources of a given type, optionally filtered by labels."""
    try:
        k8s_api = client.CustomObjectsApi()
        resources = k8s_api.list_cluster_custom_object(
            group="catalog.onefootball.com",
            version="v1alpha1",
            plural=f"{resource_type}s",
            label_selector=label_selector
        )
        return resources.get('items', [])
    except Exception as e:
        logger.error(f"Error listing {resource_type}s: {e}")
        return []


def trigger_refresh(resource_type: str, name: str, namespace: Optional[str] = None) -> None:
    """Trigger a refresh by annotating the resource."""
    try:
        k8s_api = client.CustomObjectsApi()
        patch = {
            "metadata": {
                "annotations": {
                    "catalog.onefootball.com/refresh-triggered": str(kopf.unparse_rfc3339_timestamp())
                }
            }
        }

        if namespace:
            k8s_api.patch_namespaced_custom_object(
                group="catalog.onefootball.com",
                version="v1alpha1",
                namespace=namespace,
                plural=f"{resource_type}s",
                name=name,
                body=patch
            )
        else:
            k8s_api.patch_cluster_custom_object(
                group="catalog.onefootball.com",
                version="v1alpha1",
                plural=f"{resource_type}s",
                name=name,
                body=patch
            )
        logger.info(f"Triggered refresh for {resource_type}/{name}")
    except Exception as e:
        logger.error(f"Error triggering refresh for {resource_type}/{name}: {e}")


def trigger_related_resources(source_type: str, source_name: str) -> None:
    """Trigger refresh for resources that depend on the given source."""
    if source_type == 'metric':
        # Find scorecards that use this metric
        scorecards = find_affected_resources('scorecard')
        for scorecard in scorecards:
            scorecard_name = scorecard.get('metadata', {}).get('name')
            criteria = scorecard.get('spec', {}).get('criteria', [])

            for criterion in criteria:
                hasMetricValue = criterion.get('hasMetricValue', {})
                if hasMetricValue and hasMetricValue.get('metricName') == source_name:
                    trigger_refresh('scorecard', scorecard_name)

        # Find components that depend on this metric
        components = find_affected_resources('component')
        for component in components:
            component_name = component.get('metadata', {}).get('name')
            component_ns = component.get('metadata', {}).get('namespace')
            trigger_refresh('component', component_name, namespace=component_ns)

    elif source_type == 'scorecard':
        # Find components that might be evaluated by this scorecard
        components = find_affected_resources('component')
        for component in components:
            component_name = component.get('metadata', {}).get('name')
            component_ns = component.get('metadata', {}).get('namespace')
            trigger_refresh('component', component_name, namespace=component_ns)