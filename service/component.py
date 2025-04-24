import kopf
import logging
from typing import Dict, Any
from compass import get_compass_client
from utils import extract_id_from_status

logger = logging.getLogger('component-handler')


@kopf.on.create('catalog.onefootball.com', 'v1alpha1', 'components')
def create_component(spec: Dict[str, Any], meta: Dict[str, Any], **_) -> Dict[str, Any]:
    """Handle component creation."""
    name = meta.get('name')
    logger.info(f"Creating component {name}")

    compass_client = get_compass_client()

    # Transform Kubernetes resource to Compass API format
    component_data = {
        'name': spec.get('name', name),
        'description': spec.get('description', ''),
        'typeId': spec.get('typeId'),
        'ownerId': spec.get('ownerId'),
        'dependsOn': spec.get('dependsOn', []),
        'tribe': spec.get('tribe'),
        'squad': spec.get('squad'),
        'links': spec.get('links', []),
        'labels': spec.get('labels', []),
    }

    if spec.get('slug'):
        component_data['slug'] = spec.get('slug')

    try:
        result = compass_client.create_component(component_data)
        component_id = result.get('id')
        logger.info(f"Created component {name} with ID {component_id}")

        # Build initial metric sources info (empty, will be populated on refresh)
        metric_sources = {}

        return {
            'id': component_id,
            'metricSources': metric_sources
        }
    except Exception as e:
        logger.error(f"Error creating component {name}: {e}")
        raise kopf.PermanentError(f"Failed to create component in Compass: {e}")


@kopf.on.update('catalog.onefootball.com', 'v1alpha1', 'components')
def update_component(spec: Dict[str, Any], meta: Dict[str, Any], status: Dict[str, Any], **_) -> Dict[str, Any]:
    """Handle component updates."""
    name = meta.get('name')
    component_id = extract_id_from_status(status)

    if not component_id:
        logger.warning(f"Cannot update component {name} without ID in status")
        return {'id': None}

    logger.info(f"Updating component {name} with ID {component_id}")
    compass_client = get_compass_client()

    # Transform Kubernetes resource to Compass API format
    component_data = {
        'name': spec.get('name', name),
        'description': spec.get('description', ''),
        'typeId': spec.get('typeId'),
        'ownerId': spec.get('ownerId'),
        'dependsOn': spec.get('dependsOn', []),
        'tribe': spec.get('tribe'),
        'squad': spec.get('squad'),
        'links': spec.get('links', []),
        'labels': spec.get('labels', []),
    }

    if spec.get('slug'):
        component_data['slug'] = spec.get('slug')

    try:
        compass_client.update_component(component_id, component_data)
        logger.info(f"Updated component {name}")

        # Keep the existing metric sources info
        metric_sources = status.get('metricSources', {}) if status else {}

        return {
            'id': component_id,
            'metricSources': metric_sources
        }
    except Exception as e:
        logger.error(f"Error updating component {name}: {e}")
        raise kopf.PermanentError(f"Failed to update component in Compass: {e}")


@kopf.on.delete('catalog.onefootball.com', 'v1alpha1', 'components')
def delete_component(meta: Dict[str, Any], status: Dict[str, Any], **_) -> None:
    """Handle component deletion."""
    name = meta.get('name')
    component_id = extract_id_from_status(status)

    if not component_id:
        logger.warning(f"Cannot delete component {name} without ID in status")
        return

    logger.info(f"Deleting component {name} with ID {component_id}")
    compass_client = get_compass_client()

    try:
        compass_client.delete_component(component_id)
        logger.info(f"Deleted component {name}")
    except Exception as e:
        logger.error(f"Error deleting component {name}: {e}")