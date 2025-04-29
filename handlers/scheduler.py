import json
import logging
import os
import hashlib
from typing import Dict, Any, Optional

logger = logging.getLogger("CronJobSubHandler")

METRIC_EVALUATION_SERVICE_URL = os.getenv("METRIC_EVALUATION_SERVICE_URL", "metric-evaluation-service")


def build_metric_evaluator_cronjob(parent_resource: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Build a CronJob resource for metric evaluation with consistent hashing.
    Uses a minimal set of fields to ensure stable CronJob specifications.
    IMPORTANT: Does NOT include any changing annotations that would cause reconciliation loops.
    """
    metric_name = parent_resource["metadata"]["name"]
    resource_spec = parent_resource.get("spec", {})
    cron_schedule = resource_spec.get("cronSchedule")

    if not cron_schedule:
        logger.info(f"Metric '{metric_name}' has no cronSchedule. No CronJob will be built.")
        return None

    spec_hash = hashlib.md5(json.dumps(resource_spec, sort_keys=True).encode()).hexdigest()
    cronjob_name = f"{metric_name}-evaluator"

    # Use a simplified command that won't change on every reconciliation
    curl_command = f"curl -X POST {METRIC_EVALUATION_SERVICE_URL}/evaluate/{metric_name}"

    # Create stable labels
    labels = {
        "metric.catalog.onefootball.com/name": metric_name,
        "grading-system": resource_spec.get("grading-system", "unknown"),
        "spec-hash": spec_hash[:8]
    }

    # Add original labels from the parent resource if they exist
    if "metadata" in parent_resource and "labels" in parent_resource["metadata"]:
        for key, value in parent_resource["metadata"]["labels"].items():
            if key not in labels:
                labels[key] = value

    # IMPORTANT: Don't include any annotations that change with each request
    # Only include stable annotations that won't change between reconciliations
    annotations = {
        "metric.catalog.onefootball.com/name": metric_name,
        "metric.catalog.onefootball.com/spec-hash": spec_hash
    }

    logger.info(f"Building CronJob for metric '{metric_name}' with hash '{spec_hash[:8]}'")

    desired_cronjob = {
        "apiVersion": "batch/v1",
        "kind": "CronJob",
        "metadata": {
            "name": cronjob_name,
            "namespace": "catalog-controller",
            "labels": labels,
            "annotations": annotations
        },
        "spec": {
            "schedule": cron_schedule,
            "jobTemplate": {
                "spec": {
                    "template": {
                        "metadata": {
                            "labels": labels
                        },
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