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

    import hashlib
    spec_hash = hashlib.md5(json.dumps(resource_spec, sort_keys=True).encode()).hexdigest()

    logger.debug(f"Building desired CronJob for metric '{metric_name}' with schedule '{cron_schedule}'.")
    cronjob_name = f"{metric_name}-evaluator"
    metric_spec_json = json.dumps(resource_spec)
    curl_command = f"curl -X POST {METRIC_EVALUATION_SERVICE_URL} -H 'Content-Type: application/json' -d '{metric_spec_json}'"

    annotations = {
        "metric.catalog.onefootball.com/description": resource_spec.get("description", ""),
        "metric.catalog.onefootball.com/component-type": ",".join(resource_spec.get("componentType", [])),
        "metric.catalog.onefootball.com/spec-hash": spec_hash
    }

    labels = parent_resource["metadata"].get("labels", {}).copy()
    default_labels = {
        "metric.catalog.onefootball.com/name": metric_name,
        "grading-system": resource_spec.get("grading-system", "unknown"),
        "spec-hash": spec_hash[:8]
    }
    labels.update(default_labels)

    desired_cronjob = {
        "apiVersion": "batch/v1",
        "kind": "CronJob",
        "metadata": {
            "name": cronjob_name,
            "namespace": "catalog-controller",
            "labels": labels,
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
                                    "command": ["/bin/sh", "-c", curl_command]
                                }
                            ],
                        }
                    },
                }
            }
        }
    }

    return desired_cronjob