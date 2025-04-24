import kopf
import logging
from typing import Dict, Any
from compass import get_compass_client
from utils import extract_id_from_status, find_affected_resources, trigger_related_resources

logger = logging.getLogger('scorecard-handler')


@kopf.on.create('catalog.onefootball.com', 'v1alpha1', 'scorecards')
def create_scorecard(spec: Dict[str, Any], meta: Dict[str, Any], **_) -> Dict[str, Any]:
    """Handle scorecard creation."""
    name = meta.get('name')
    logger.info(f"Creating scorecard {name}")

    compass_client = get_compass_client()

    # Transform Kubernetes resource to Compass API format
    scorecard_data = {
        'name': spec.get('name', name),
        'description': spec.get('description', ''),
        'ownerId': spec.get('ownerId'),
        'state': spec.get('state', 'DRAFT'),
        'componentTypeIds': spec.get('componentTypeIds', []),
        'importance': spec.get('importance', 'REQUIRED'),
        'scoringStrategyType': spec.get('scoringStrategyType', 'WEIGHT_BASED'),
        'criteria': spec.get('criteria', [])
    }

    try:
        result = compass_client.create_scorecard(scorecard_data)
        scorecard_id = result.get('id')
        logger.info(f"Created scorecard {name} with ID {scorecard_id}")

        # Create criteria status mappings
        criteria_status = {}
        for criterion in spec.get('criteria', []):
            hasMetricValue = criterion.get('hasMetricValue', {})
            if hasMetricValue:
                criterion_name = hasMetricValue.get('name')
                metric_name = hasMetricValue.get('metricName')

                # Find the corresponding metric to get its ID
                metrics = find_affected_resources('metric')
                for metric in metrics:
                    if metric.get('metadata', {}).get('name') == metric_name:
                        metric_id = extract_id_from_status(metric.get('status'))
                        if metric_id:
                            criteria_status[criterion_name] = {
                                'metricDefinitionId': metric_id
                            }

        return {
            'id': scorecard_id,
            'criteria': criteria_status
        }
    except Exception as e:
        logger.error(f"Error creating scorecard {name}: {e}")
        raise kopf.PermanentError(f"Failed to create scorecard in Compass: {e}")


@kopf.on.update('catalog.onefootball.com', 'v1alpha1', 'scorecards')
def update_scorecard(spec: Dict[str, Any], meta: Dict[str, Any], status: Dict[str, Any], **_) -> Dict[str, Any]:
    """Handle scorecard updates."""
    name = meta.get('name')
    scorecard_id = extract_id_from_status(status)

    if not scorecard_id:
        logger.warning(f"Cannot update scorecard {name} without ID in status")
        return {'id': None}

    logger.info(f"Updating scorecard {name} with ID {scorecard_id}")
    compass_client = get_compass_client()

    # Transform Kubernetes resource to Compass API format
    scorecard_data = {
        'name': spec.get('name', name),
        'description': spec.get('description', ''),
        'ownerId': spec.get('ownerId'),
        'state': spec.get('state', 'DRAFT'),
        'componentTypeIds': spec.get('componentTypeIds', []),
        'importance': spec.get('importance', 'REQUIRED'),
        'scoringStrategyType': spec.get('scoringStrategyType', 'WEIGHT_BASED'),
        'criteria': spec.get('criteria', [])
    }

    try:
        compass_client.update_scorecard(scorecard_id, scorecard_data)
        logger.info(f"Updated scorecard {name}")

        # Update criteria status mappings
        criteria_status = status.get('criteria', {}) if status else {}
        for criterion in spec.get('criteria', []):
            hasMetricValue = criterion.get('hasMetricValue', {})
            if hasMetricValue:
                criterion_name = hasMetricValue.get('name')
                metric_name = hasMetricValue.get('metricName')

                # Find the corresponding metric to get its ID
                metrics = find_affected_resources('metric')
                for metric in metrics:
                    if metric.get('metadata', {}).get('name') == metric_name:
                        metric_id = extract_id_from_status(metric.get('status'))
                        if metric_id:
                            if criterion_name not in criteria_status:
                                criteria_status[criterion_name] = {}
                            criteria_status[criterion_name]['metricDefinitionId'] = metric_id

        # Trigger refresh for related components
        trigger_related_resources('scorecard', name)

        return {
            'id': scorecard_id,
            'criteria': criteria_status
        }
    except Exception as e:
        logger.error(f"Error updating scorecard {name}: {e}")
        raise kopf.PermanentError(f"Failed to update scorecard in Compass: {e}")


@kopf.on.delete('catalog.onefootball.com', 'v1alpha1', 'scorecards')
def delete_scorecard(meta: Dict[str, Any], status: Dict[str, Any], **_) -> None:
    """Handle scorecard deletion."""
    name = meta.get('name')
    scorecard_id = extract_id_from_status(status)

    if not scorecard_id:
        logger.warning(f"Cannot delete scorecard {name} without ID in status")
        return

    logger.info(f"Deleting scorecard {name} with ID {scorecard_id}")
    compass_client = get_compass_client()

    try:
        compass_client.delete_scorecard(scorecard_id)
        logger.info(f"Deleted scorecard {name}")
    except Exception as e:
        logger.error(f"Error deleting scorecard {name}: {e}")