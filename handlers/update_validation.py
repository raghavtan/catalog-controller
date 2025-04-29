import logging
from typing import Dict, Any
from utils import set_condition
from models import ResourceKind

logger = logging.getLogger("StateValidationHandler")


def needs_update(resource_kind: str, parent: Dict[str, Any], compass_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determines if a resource needs to be updated in Compass.
    Returns a dictionary with needs_update flag and update_fields list.
    """
    resource_spec = parent.get("spec", {})
    resource_name = parent["metadata"]["name"]

    # Default result
    result = {
        "needs_update": False,
        "update_fields": []
    }

    # Check if compass_state is empty or None
    if not compass_state:
        result["needs_update"] = True
        result["update_fields"].append("all")
        return result

    # Resource-specific comparisons
    if resource_kind.lower() == ResourceKind.METRIC:
        # Key fields to check for metrics
        fields_to_check = [
            "name", "description", "format", "grading-system",
            "componentType", "cronSchedule"
        ]

        # Compare each field
        for field in fields_to_check:
            spec_value = resource_spec.get(field)
            compass_value = compass_state.get(field)

            # Skip if both values are None
            if spec_value is None and compass_value is None:
                continue

            # Skip empty comparison
            if not spec_value or not compass_value:
                continue

            # Compare based on type
            if isinstance(spec_value, dict) and isinstance(compass_value, dict):
                # Deep comparison for dictionaries
                if spec_value != compass_value:
                    result["needs_update"] = True
                    result["update_fields"].append(field)
            elif isinstance(spec_value, list) and isinstance(compass_value, list):
                # Compare sets for lists - order doesn't matter
                if set(str(x) for x in spec_value) != set(str(x) for x in compass_value):
                    result["needs_update"] = True
                    result["update_fields"].append(field)
            else:
                # Simple equality for other types
                if spec_value != compass_value:
                    result["needs_update"] = True
                    result["update_fields"].append(field)

        # Facts comparison - more complex
        spec_facts = resource_spec.get("facts", [])
        compass_facts = compass_state.get("facts", [])

        if len(spec_facts) != len(compass_facts):
            result["needs_update"] = True
            result["update_fields"].append("facts")
        else:
            # Check for different fact IDs
            spec_fact_ids = {f.get("id") for f in spec_facts if "id" in f}
            compass_fact_ids = {f.get("id") for f in compass_facts if "id" in f}

            if spec_fact_ids != compass_fact_ids:
                result["needs_update"] = True
                result["update_fields"].append("facts")

    elif resource_kind.lower() == ResourceKind.SCORECARD:
        # Check key scorecard fields
        fields_to_check = [
            "name", "description", "importance", "state",
            "ownerId", "scoringStrategyType"
        ]

        for field in fields_to_check:
            if resource_spec.get(field) != compass_state.get(field):
                result["needs_update"] = True
                result["update_fields"].append(field)

        # Check component type IDs
        spec_component_types = set(resource_spec.get("componentTypeIds", []))
        compass_component_types = set(compass_state.get("componentTypeIds", []))

        if spec_component_types != compass_component_types:
            result["needs_update"] = True
            result["update_fields"].append("componentTypeIds")

        # Check criteria
        spec_criteria = resource_spec.get("criteria", [])
        compass_criteria = compass_state.get("criteria", {})

        # Count different criteria
        if len(spec_criteria) != len(compass_criteria):
            result["needs_update"] = True
            result["update_fields"].append("criteria")
        else:
            # Check each criterion
            for criterion in spec_criteria:
                if "hasMetricValue" in criterion:
                    metric_value = criterion["hasMetricValue"]
                    metric_name = metric_value.get("metricName")

                    if metric_name not in compass_criteria:
                        result["needs_update"] = True
                        result["update_fields"].append(f"criterion.{metric_name}")
                    else:
                        # Check criterion properties
                        compass_criterion = compass_criteria.get(metric_name, {})

                        for prop in ["comparator", "comparatorValue", "weight"]:
                            if metric_value.get(prop) != compass_criterion.get(prop):
                                result["needs_update"] = True
                                result["update_fields"].append(f"criterion.{metric_name}.{prop}")

    elif resource_kind.lower() == ResourceKind.COMPONENT:
        # Check key component fields
        fields_to_check = [
            "name", "description", "componentType", "typeId", "slug"
        ]

        for field in fields_to_check:
            if resource_spec.get(field) != compass_state.get(field):
                result["needs_update"] = True
                result["update_fields"].append(field)

        # Check links
        spec_links = resource_spec.get("links", [])
        compass_links = compass_state.get("links", [])

        if len(spec_links) != len(compass_links):
            result["needs_update"] = True
            result["update_fields"].append("links")
        else:
            # Create sets of URLs for comparison
            spec_urls = {link.get("url") for link in spec_links if "url" in link}
            compass_urls = {link.get("url") for link in compass_links if "url" in link}

            if spec_urls != compass_urls:
                result["needs_update"] = True
                result["update_fields"].append("links")

        # Check labels
        if "labels" in resource_spec and "labels" in compass_state:
            if set(resource_spec["labels"]) != set(compass_state["labels"]):
                result["needs_update"] = True
                result["update_fields"].append("labels")

    logger.info(
        f"Update check for {resource_kind}/{resource_name}: {result['needs_update']} - {result['update_fields']}")
    return result


def handle_no_update_needed(resource_kind: str, compass_id: str, compass_state: Dict[str, Any],
                            parent: Dict[str, Any], desired_status: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handles the case where no update is needed for a resource.
    Returns the desired status with appropriate values from compass state.
    """
    resource_name = parent["metadata"]["name"]
    resource_spec = parent.get("spec", {})

    logger.info(f"No differences detected for {resource_kind}/{resource_name} with ID {compass_id}")

    # Ensure ID is set
    desired_status["id"] = compass_id

    # Resource-specific handling
    if resource_kind.lower() == ResourceKind.SCORECARD:
        # Copy criteria with metricDefinitionIds
        if compass_state and "criteria" in compass_state:
            desired_status["criteria"] = compass_state["criteria"]

        # Generate metrics summary
        metric_names = [
            c.get("hasMetricValue", {}).get("metricName", "unknown")
            for c in resource_spec.get("criteria", [])
            if "hasMetricValue" in c
        ]
        desired_status["metricsSummary"] = ", ".join(metric_names)

    elif resource_kind.lower() == ResourceKind.COMPONENT:
        # Copy metric sources
        if compass_state and "metricSources" in compass_state:
            desired_status["metricSources"] = compass_state["metricSources"]

        # Copy owner ID
        if compass_state and "ownerId" in compass_state:
            desired_status["ownerId"] = compass_state["ownerId"]

    # Update conditions
    set_condition(desired_status["conditions"], "Ready", "True", "InSync",
                  f"{resource_kind} in sync with Compass")
    set_condition(desired_status["conditions"], "Synced", "True", "SyncSuccess",
                  f"{resource_kind} in sync with Compass")

    return desired_status