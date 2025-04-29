import json
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger("CronJobSubHandler")

METRIC_EVALUATION_SERVICE_URL = os.getenv("METRIC_EVALUATION_SERVICE_URL", "metric-evaluation-service")


def build_metric_evaluator_cronjob(parent_resource: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    metric_name = parent_resource["metadata"]["name"]
    resource_spec = parent_resource.get("spec", {})
    cron_schedule = resource_spec.get("cronSchedule")

    if not cron_schedule:
        logger.info(f"Metric '{metric_name}' has no cronSchedule. No CronJob will be built.")
        return None

    logger.info(f"Building desired CronJob for metric '{metric_name}' with schedule '{cron_schedule}'.")
    cronjob_name = f"{metric_name}-evaluator"
    metric_spec_json = json.dumps(resource_spec)

    desired_cronjob = {
        "apiVersion": "batch/v1",
        "kind": "CronJob",
        "metadata": {
            "name": cronjob_name,
            "namespace": "catalog-controller",
            "labels": {
                "app.kubernetes.io/created-by": "catalog-controller",
                "metric.catalog.onefootball.com/name": metric_name
            },
        },
        "spec": {
            "schedule": cron_schedule,
            "jobTemplate": {
                "spec": {
                    "template": {
                        "spec": {
                            "restartPolicy": "OnFailure",
                            "containers": [
                                {
                                    "name": "compute-caller",
                                    "image": "alpine/curl",
                                    "command": ["/bin/sh", "-c",
                                                f"curl -X POST {METRIC_EVALUATION_SERVICE_URL} "
                                                f"-H 'Content-Type: application/json' "
                                                f"-d '{metric_spec_json}'"]
                                }
                            ],
                        }
                    },
                }
            }
        }
    }

    return desired_cronjob