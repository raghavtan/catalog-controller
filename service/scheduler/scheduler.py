import json
import logging
import os
import hashlib
from typing import Dict, Any, Tuple, List
import yaml

logger = logging.getLogger("CronJobSubHandler")

METRIC_EVALUATION_SERVICE_URL = os.getenv("METRIC_EVALUATION_SERVICE_URL", "metric-evaluation-service")


def build_metric_evaluator_cronjob(parent_resource: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    try:
        metric_name = parent_resource["metadata"]["name"]
        resource_spec = parent_resource.get("spec", {})
        cron_schedule = resource_spec.get("cronSchedule")

        controller_prefix = os.getenv("CONTROLLER_PREFIX", "metric.catalog.onefootball.com")

        if not cron_schedule:
            logger.info(f"Metric '{metric_name}' has no cronSchedule. No CronJob will be built.")
            return [], "NoSchedule"

        spec_hash = hashlib.md5(json.dumps(resource_spec, sort_keys=True).encode()).hexdigest()
        cronjob_name = f"{metric_name}-evaluator"

        curl_command = f"curl -X POST {METRIC_EVALUATION_SERVICE_URL}/evaluate/{metric_name} "
        curl_command += f"-H 'Content-Type: application/json' -d '{{\"spec\": {json.dumps(resource_spec)}}}'"

        labels = {
            f"{controller_prefix}/name": metric_name,
            f"{controller_prefix}/grading-system": resource_spec.get("grading-system", "unknown"),
            f"{controller_prefix}/spec-hash": spec_hash
        }

        if "metadata" in parent_resource and "labels" in parent_resource["metadata"]:
            for key, value in parent_resource["metadata"]["labels"].items():
                if key not in labels:
                    labels[key] = value

        annotations = {
            f"{controller_prefix}/name": metric_name,
            f"{controller_prefix}/spec-hash": spec_hash,
            f"{controller_prefix}/grading-system": resource_spec.get("grading-system", "unknown")
        }

        template_path = "templates/cronjob.yaml"
        with open(template_path, 'r') as file:
            cronjob_template = yaml.safe_load(file)

        cronjob_template["metadata"]["name"] = cronjob_name
        cronjob_template["metadata"]["labels"] = labels
        cronjob_template["metadata"]["annotations"] = annotations
        cronjob_template["spec"]["jobTemplate"]["metadata"]["labels"] = labels
        cronjob_template["spec"]["jobTemplate"]["spec"]["template"]["metadata"]["labels"] = labels
        cronjob_template["spec"]["schedule"] = cron_schedule

        for container in cronjob_template["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"]:
            if container["name"] == "compute-caller":
                container["command"] = ["/bin/sh", "-c", curl_command]

        return [cronjob_template], "Created"
    except Exception as e:
        logger.error(f"Error building CronJob for metric '{parent_resource['metadata']['name']}': {e}")
        return [], "Failed"