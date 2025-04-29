import logging
from typing import Dict, Any, List

from handlers.scheduler import build_metric_evaluator_cronjob
from utils import set_condition
from models import ResourceKind

logger = logging.getLogger("ChildrenSubHandler")


def generate_child_resources(resource_kind: str, parent: Dict[str, Any],
                             desired_status: Dict[str, Any]) -> List[Dict[str, Any]]:
    desired_children = []

    if resource_kind.lower() == ResourceKind.METRIC:
        desired_cronjob = build_metric_evaluator_cronjob(parent)
        if desired_cronjob:
            desired_children.append(desired_cronjob)
            set_condition(desired_status["conditions"], "Ready", "True",
                          "CronJobCreated", "CronJob for metric evaluation created.")
        else:
            set_condition(desired_status["conditions"], "Ready", "True",
                          "NoCronJob", "No CronJob necessary as cronSchedule is not defined.")

    return desired_children
