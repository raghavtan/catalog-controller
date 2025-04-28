import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("CronJobManager")

def build_metric_evaluator_cronjob(parent_resource: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Builds the desired CronJob object for a Metric resource if a cronSchedule is provided.

    Args:
        parent_resource: The dictionary representation of the Metric parent resource.

    Returns:
        A dictionary representing the desired CronJob object, or None if no cronSchedule is found.
    """
    metric_name = parent_resource["metadata"]["name"]
    namespace = parent_resource["metadata"].get("namespace", "default")
    resource_spec = parent_resource.get("spec", {})
    cron_schedule = resource_spec.get("cronSchedule")

    if not cron_schedule:
        logger.info(f"Metric '{metric_name}' has no cronSchedule. No CronJob will be built.")
        return None

    logger.info(f"Building desired CronJob for metric '{metric_name}' with schedule '{cron_schedule}'.")

    # Define the desired CronJob object structure
    cronjob_name = f"{metric_name}-evaluator"

    # Serialize the metric spec to pass to the compute-caller container
    # Consider alternative methods (ConfigMap, reading via K8s API) for larger specs
    metric_spec_json = json.dumps(resource_spec)

    desired_cronjob = {
        "apiVersion": "batch/v1",
        "kind": "CronJob",
        "metadata": {
            "name": cronjob_name,
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/created-by": "metric-controller",
                "metric.catalog.onefootball.com/name": metric_name # Add a label for easier identification
            },
            # Metacontroller will automatically add/manage ownerReferences
            # when this object is returned in the SyncResponse children list
        },
        "spec": {
            "schedule": cron_schedule,
            # Optional: Add startingDeadlineSeconds, concurrencyPolicy, suspend, etc.
            "jobTemplate": {
                "spec": {
                    "template": {
                        "spec": {
                            "restartPolicy": "OnFailure", # Ensure the Job fails if computation fails
                            "containers": [
                                {
                                    "name": "compute-caller",
                                    "image": "<your-compute-caller-image>", # !!! REPLACE with your actual image !!!
                                    # Command to call the compute service
                                    "command": ["/bin/sh", "-c",
                                                f"curl -X POST http://compute-service.your-namespace.svc.cluster.local/compute " # !!! REPLACE with your actual service URL !!!
                                                f"-H 'Content-Type: application/json' "
                                                f"-d '{metric_spec_json}'"] # Pass the spec as JSON payload
                                    # Add resource requests/limits
                                    # Add securityContext if needed
                                }
                            ],
                            # Add serviceAccountName if needed for Kubernetes API access
                        }
                    },
                    # Optional: Add backoffLimit, activeDeadlineSeconds
                }
            }
        }
    }

    return desired_cronjob