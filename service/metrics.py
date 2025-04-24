import kopf
import logging
from typing import Dict, Any
from compass import get_compass_client
from utils import extract_id_from_status, find_affected_resources, trigger_refresh, trigger_related_resources

logger = logging.getLogger('metrics-handler')


@kopf.on.create('catalog.onefootball.com', 'v1alpha1', 'metrics')
def create_metric(spec: Dict[str, Any], meta: Dict[str, Any], **_) -> Dict[str, Any]:
    """Handle metric creation."""
    name = meta.get('name')
    logger.info(f"Creating metric {name}")

    # Get singleton compass client
    compass_client = get_compass_client()

    # Transform Kubernetes resource to Compass API format
    metric_data = {
        'name': spec.get('name', name),
        'description': spec.get('description', ''),
        'componentType': meta.get('componentType', []),
        'facts': meta.get('facts', []),
        'format': spec.get('format', {})
    }

    try:
        result = compass_client.create_metric(metric_data)
        metric_id = result.get('id')
        logger.info(f"Created metric {name} with ID {metric_id}")

        # Trigger refresh for related scorecards
        affected_scorecards = find_affected_resources('scorecard')
        for scorecard in affected_scorecards:
            scorecard_name = scorecard.get('metadata', {}).get('name')
            if scorecard_name:
                criteria = scorecard.get('spec', {}).get('criteria', [])
                for criterion in criteria:
                    hasMetricValue = criterion.get('hasMetricValue', {})
                    if hasMetricValue and hasMetricValue.get('metricName') == name:
                        trigger_refresh('scorecard', scorecard_name)

        return {'id': metric_id}
    except Exception as e:
        logger.error(f"Error creating metric {name}: {e}")
        raise kopf.PermanentError(f"Failed to create metric in Compass: {e}")


@kopf.on.update('catalog.onefootball.com', 'v1alpha1', 'metrics')
def update_metric(spec: Dict[str, Any], meta: Dict[str, Any], status: Dict[str, Any], **_) -> Dict[str, Any]:
    """Handle metric updates."""
    name = meta.get('name')
    metric_id = extract_id_from_status(status)

    if not metric_id:
        logger.warning(f"Cannot update metric {name} without ID in status")
        return {'id': None}

    logger.info(f"Updating metric {name} with ID {metric_id}")
    compass_client = get_compass_client()

    # Transform Kubernetes resource to Compass API format
    metric_data = {
        'name': spec.get('name', name),
        'description': spec.get('description', ''),
        'componentType': meta.get('componentType', []),
        'facts': meta.get('facts', []),
        'format': spec.get('format', {})
    }

    try:
        compass_client.update_metric(metric_id, metric_data)
        logger.info(f"Updated metric {name}")

        # Trigger refresh for related resources
        trigger_related_resources('metric', name)

        return {'id': metric_id}
    except Exception as e:
        logger.error(f"Error updating metric {name}: {e}")
        raise kopf.PermanentError(f"Failed to update metric in Compass: {e}")


@kopf.on.delete('catalog.onefootball.com', 'v1alpha1', 'metrics')
def delete_metric(meta: Dict[str, Any], status: Dict[str, Any], **_) -> None:
    """Handle metric deletion."""
    name = meta.get('name')
    metric_id = extract_id_from_status(status)

    if not metric_id:
        logger.warning(f"Cannot delete metric {name} without ID in status")
        return

    logger.info(f"Deleting metric {name} with ID {metric_id}")
    compass_client = get_compass_client()

    try:
        compass_client.delete_metric(metric_id)
        logger.info(f"Deleted metric {name}")
    except Exception as e:
        logger.error(f"Error deleting metric {name}: {e}")