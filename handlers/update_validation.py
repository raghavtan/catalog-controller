import logging
from typing import Dict, Any
from utils import set_condition

logger = logging.getLogger("StateValidationHandler")


def needs_update(resource_kind: str, resource_spec: Dict[str, Any], compass_state: Dict[str, Any]) -> bool:
    """Determine if a resource needs to be updated in Compass based on differences between spec and state."""

    # Common fields to check
    if not compass_state:
        return True

    # Resource-specific comparisons
    if resource_kind.lower() == "metric":
        # Check key metric fields
        key_fields = ["description", "format", "grading-system", "componentType", "name"]
        for field in key_fields:
            spec_value = resource_spec.get(field)
            compass_value = compass_state.get(field)

            # Skip comparison if either value is missing (common for complex fields)
            if spec_value is None or compass_value is None:
                continue

            # Deep comparison for objects
            if isinstance(spec_value, dict) and isinstance(compass_value, dict):
                if spec_value != compass_value:
                    logger.info(f"Field '{field}' differs: {spec_value} vs {compass_value}")
                    return True
            # List comparison
            elif isinstance(spec_value, list) and isinstance(compass_value, list):
                if set(str(x) for x in spec_value) != set(str(x) for x in compass_value):
                    logger.info(f"List field '{field}' differs")
                    return True
            # Simple value comparison
            elif spec_value != compass_value:
                logger.info(f"Field '{field}' differs: {spec_value} vs {compass_value}")
                return True

        # Check facts - this might need specialized comparison logic
        spec_facts = resource_spec.get("facts", [])
        compass_facts = compass_state.get("facts", [])
        if len(spec_facts) != len(compass_facts):
            logger.info(f"Number of facts differs: {len(spec_facts)} vs {len(compass_facts)}")
            return True

        # Simple check - might need more sophisticated comparison for facts
        fact_ids_spec = {f.get("id") for f in spec_facts if "id" in f}
        fact_ids_compass = {f.get("id") for f in compass_facts if "id" in f}
        if fact_ids_spec != fact_ids_compass:
            logger.info(f"Fact IDs differ: {fact_ids_spec} vs {fact_ids_compass}")
            return True

    elif resource_kind.lower() == "scorecard":
        # Check key scorecard fields
        key_fields = ["name", "description", "importance", "state", "ownerId", "scoringStrategyType"]
        for field in key_fields:
            if resource_spec.get(field) != compass_state.get(field):
                logger.info(f"Field '{field}' differs")
                return True

        # Compare component type IDs
        spec_component_types = set(resource_spec.get("componentTypeIds", []))
        compass_component_types = set(compass_state.get("componentTypeIds", []))
        if spec_component_types != compass_component_types:
            logger.info(f"Component type IDs differ: {spec_component_types} vs {compass_component_types}")
            return True

        # Compare criteria
        spec_criteria = resource_spec.get("criteria", [])
        compass_criteria = compass_state.get("criteria", {})

        # Check if criteria count differs
        if len(spec_criteria) != len(compass_criteria):
            logger.info(f"Number of criteria differs: {len(spec_criteria)} vs {len(compass_criteria)}")
            return True

        # Check each criterion
        for criterion in spec_criteria:
            metric_value = criterion.get("hasMetricValue", {})
            metric_name = metric_value.get("metricName")

            if metric_name not in compass_criteria:
                logger.info(f"Criterion '{metric_name}' exists in spec but not in Compass")
                return True

            # Compare criterion properties - could be expanded
            if metric_value.get("comparator") != compass_criteria.get(metric_name, {}).get("comparator") or \
                    metric_value.get("comparatorValue") != compass_criteria.get(metric_name, {}).get(
                "comparatorValue") or \
                    metric_value.get("weight") != compass_criteria.get(metric_name, {}).get("weight"):
                logger.info(f"Criterion '{metric_name}' properties differ")
                return True

    elif resource_kind.lower() == "component":
        # Check key component fields
        key_fields = ["name", "description", "componentType", "typeId", "slug"]
        for field in key_fields:
            if resource_spec.get(field) != compass_state.get(field):
                logger.info(f"Field '{field}' differs")
                return True

        # Could add additional checks for links, labels, etc.
        spec_links = {link.get("url") for link in resource_spec.get("links", []) if "url" in link}
        compass_links = {link.get("url") for link in compass_state.get("links", []) if "url" in link}
        if spec_links != compass_links:
            logger.info(f"Links differ: {spec_links} vs {compass_links}")
            return True

        # Check labels if present
        if "labels" in resource_spec and "labels" in compass_state:
            if set(resource_spec["labels"]) != set(compass_state["labels"]):
                logger.info("Labels differ")
                return True

    # No differences found
    logger.info(f"No differences detected for {resource_kind} in Compass state")
    return False


def handle_no_update_needed(resource_kind: str, compass_id: str, compass_state: Dict[str, Any],
                            resource_spec: Dict[str, Any], desired_status: Dict[str, Any]) -> Dict[str, Any]:
    """Handle the case where no update is needed."""
    logger.info(f"No differences detected for {resource_kind} {compass_id} in Compass state")

    # Resource-specific handling
    if resource_kind.lower() == "scorecard":
        # Copy criteria with metricDefinitionIds
        if compass_state and "criteria" in compass_state:
            desired_status["criteria"] = compass_state["criteria"]

        # Generate metrics summary from criteria in spec
        metric_names = [c.get("hasMetricValue", {}).get("metricName", "unknown")
                        for c in resource_spec.get("criteria", [])]
        desired_status["metricsSummary"] = ", ".join(metric_names)

    elif resource_kind.lower() == "component" and compass_state:
        # Copy metric sources
        if "metricSources" in compass_state:
            desired_status["metricSources"] = compass_state["metricSources"]

        # Copy ownerId if present
        if "ownerId" in compass_state:
            desired_status["ownerId"] = compass_state["ownerId"]

    elif resource_kind.lower() == "metric" and compass_state:
        # Any metric-specific status fields to copy
        pass  # Metric doesn't have special status fields beyond standard ones

    # Common status fields
    desired_status["id"] = compass_id

    # Update conditions
    set_condition(desired_status["conditions"], "Ready", "True", "InSync",
                  f"{resource_kind} in sync with Compass")
    set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                  f"{resource_kind} in sync with Compass.")

    return desired_status