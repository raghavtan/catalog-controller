import hashlib
import yaml
import json
import os
from typing import Dict, Any, Tuple, List

from jinja2 import Environment, FileSystemLoader
from service.utils.log import get_logger

logger = get_logger("CronJobSubHandler")


def build_metric_evaluator_cronjob(parent_resource: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    METRIC_EVAL_URL = os.getenv("METRIC_EVALUATION_SERVICE_URL", "metric-evaluation-service")
    CONTROLLER_PREFIX = os.getenv("CONTROLLER_PREFIX", "metric.catalog.onefootball.com")
    try:

        metric_name = parent_resource["metadata"]["name"]
        resource_spec = parent_resource.get("spec", {})
        cron_schedule = resource_spec.get("cronSchedule")

        if ("componentType" not in resource_spec.keys()) or ("facts" not in resource_spec.keys()) or (
                "grading-system" not in resource_spec.keys()):
            raise ValueError("Missing required keys in resource spec: componentType, facts, grading-system")

        if not cron_schedule:
            logger.debug(f"Metric '{metric_name}' has no cronSchedule. No CronJob will be built.")
            return [], "NoSchedule"

        spec_hash = hashlib.md5(json.dumps(resource_spec, sort_keys=True).encode()).hexdigest()
        cronjob_name = f"{metric_name}-evaluator"

        curl_command = (f"curl -X POST {METRIC_EVAL_URL}/evaluate/{metric_name} "
                        f"-H 'Content-Type: application/json' -d '{{\"spec\": {json.dumps(resource_spec)}}}'"
                        )

        labels = {
            f"{CONTROLLER_PREFIX}/name": metric_name,
            f"{CONTROLLER_PREFIX}/grading-system": resource_spec.get("grading-system"),
            f"{CONTROLLER_PREFIX}/spec-hash": spec_hash
        }

        parent_labels = parent_resource.get("metadata", {}).get("labels", {})
        labels.update({k: v for k, v in parent_labels.items() if k not in labels})

        annotations = {
            f"{CONTROLLER_PREFIX}/name": metric_name,
            f"{CONTROLLER_PREFIX}/spec-hash": spec_hash,
            f"{CONTROLLER_PREFIX}/grading-system": resource_spec.get("grading-system")
        }

        env = Environment(loader=FileSystemLoader("service/scheduler/"))
        env.filters['to_yaml'] = lambda x: yaml.dump(x, default_flow_style=False)
        template = env.get_template("cronjob.yaml")

        context = {
            "name": cronjob_name,
            "schedule": cron_schedule,
            "labels": labels,
            "annotations": annotations,
        }

        cronjob_render = yaml.safe_load(template.render(**context))

        cronjob_render["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["command"] = [
            "/bin/sh", "-c",
            curl_command
        ]

        return [cronjob_render], "Success"
    except Exception as e:
        logger.error(f"Error building CronJob for metric '{parent_resource['metadata']['name']}': {e}")
        return [], "Failed"
