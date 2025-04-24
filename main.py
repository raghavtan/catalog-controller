import kopf
import logging
import kubernetes
from kubernetes import config
from service.compass import CompassClient
from service.utils import trigger_refresh

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('catalog-controller')


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    """Initialize operator settings and resources."""
    logger.info("Starting Compass Catalog Controller")

    # Configure operator settings
    settings.posting.level = logging.INFO
    settings.watching.connect_timeout = 30
    settings.watching.server_timeout = 600

    # Initialize Kubernetes client
    try:
        config.load_incluster_config()  # Load in-cluster config when running in Kubernetes
        logger.info("Using in-cluster Kubernetes configuration")
    except kubernetes.config.config_exception.ConfigException:
        config.load_kube_config()  # Load local config when running locally
        logger.info("Using local Kubernetes configuration")

    # Initialize the CompassClient singleton
    try:
        CompassClient.get_instance()
        logger.info("CompassClient singleton initialized")
    except ValueError as e:
        error_msg = f"Failed to initialize CompassClient: {e}"
        logger.error(error_msg)
        raise kopf.PermanentError(error_msg)


import service.metrics # noqa
import service.scorecard # noqa
import service.component # noqa


# Periodic reconciliation
@kopf.timer('catalog.onefootball.com', 'v1alpha1', 'metrics', interval=3600)
@kopf.timer('catalog.onefootball.com', 'v1alpha1', 'scorecards', interval=3600)
@kopf.timer('catalog.onefootball.com', 'v1alpha1', 'components', interval=3600)
def periodic_reconciliation(body, meta, **_):
    """Perform periodic reconciliation to ensure state consistency."""
    name = meta.get('name')
    kind = body.get('kind').lower()
    component_ns = meta.get('namespace') if kind == 'component' else None

    logger.info(f"Performing periodic reconciliation for {kind}/{name}")

    # Trigger a refresh by adding an annotation
    try:
        trigger_refresh(kind, name, namespace=component_ns)
    except Exception as e:
        logger.error(f"Error during periodic reconciliation for {kind}/{name}: {e}")


if __name__ == "__main__":
    logger.info("Starting operator in standalone mode")