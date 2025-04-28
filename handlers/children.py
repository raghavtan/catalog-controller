import logging
from typing import Dict, Any, List

from handlers.scheduler import build_metric_evaluator_cronjob
from utils import set_condition

logger = logging.getLogger("ChildrenSubHandler")


def generate_child_resources(resource_kind: str, parent: Dict[str, Any],
                             desired_status: Dict[str, Any]) -> List[Dict[str, Any]]:
    desired_children = []

    if resource_kind == "metrics":
        desired_cronjob = build_metric_evaluator_cronjob(parent)
        if desired_cronjob:
            desired_children.append(desired_cronjob)
            set_condition(desired_status["conditions"], "Ready", "True",
                          "Defined", "Desired CronJob defined.")
        else:
            set_condition(desired_status["conditions"], "Ready", "False",
                          "Absent", "No CronJob desired as cronSchedule is absent.")

    return desired_children
