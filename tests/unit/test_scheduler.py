"""Unit tests for scheduler."""

import pytest
import os
from unittest.mock import patch, MagicMock

from service.scheduler.scheduler import build_metric_evaluator_cronjob

pytestmark = pytest.mark.unit


def test_build_metric_evaluator_cronjob_success():
    """Test successful CronJob generation."""
    # Create test data
    parent_resource = {
        "metadata": {
            "name": "test-metric",
            "namespace": "default",
            "labels": {"app": "test", "env": "test"}
        },
        "spec": {
            "name": "test-metric",
            "description": "Test metric",
            "componentType": "service",
            "cronSchedule": "0 * * * *",
            "facts": ["test.fact"],
            "grading-system": "percentage"
        }
    }

    # Call function
    with patch.dict(os.environ, {
        "METRIC_EVALUATION_SERVICE_URL": "test-eval-service",
        "CONTROLLER_PREFIX": "test.catalog.example.com"
    }):
        with patch('yaml.safe_load') as mock_yaml_load:
            # Create a mock CronJob with complete metadata structure
            mock_yaml_load.return_value = {
                "apiVersion": "batch/v1",
                "kind": "CronJob",
                "metadata": {
                    "name": "test-metric-evaluator",
                    "namespace": "catalog-controller",
                    "labels": {
                        "test.catalog.example.com/name": "test-metric",
                        "test.catalog.example.com/spec-hash": "hash123",
                        "test.catalog.example.com/grading-system": "percentage"
                    },
                    "annotations": {
                        "test.catalog.example.com/name": "test-metric",
                        "test.catalog.example.com/spec-hash": "hash123",
                        "test.catalog.example.com/grading-system": "percentage"
                    }
                },
                "spec": {
                    "schedule": "0 * * * *",
                    "jobTemplate": {
                        "spec": {
                            "template": {
                                "spec": {
                                    "containers": [
                                        {
                                            "name": "compute-caller",
                                            "image": "alpine/curl",
                                            "command": []
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            }
            children, status = build_metric_evaluator_cronjob(parent_resource)

    # Verify result
    assert status == "Success"
    assert len(children) == 1
    assert children[0]["kind"] == "CronJob"
    assert children[0]["metadata"]["name"] == "test-metric-evaluator"

    # Verify labels and annotations
    assert "test.catalog.example.com/name" in children[0]["metadata"]["labels"]
    assert "test.catalog.example.com/spec-hash" in children[0]["metadata"]["labels"]
    assert "test.catalog.example.com/grading-system" in children[0]["metadata"]["labels"]


def test_build_metric_evaluator_cronjob_no_schedule():
    """Test CronJob generation with no schedule."""
    # Create test data with no cronSchedule
    parent_resource = {
        "metadata": {
            "name": "test-metric",
            "namespace": "default"
        },
        "spec": {
            "name": "test-metric",
            "description": "Test metric",
            "componentType": "service",
            "facts": ["test.fact"],
            "grading-system": "percentage"
            # No cronSchedule
        }
    }

    # Call function
    children, status = build_metric_evaluator_cronjob(parent_resource)

    # Verify result
    assert status == "NoSchedule"
    assert len(children) == 0


def test_build_metric_evaluator_cronjob_missing_required_fields():
    """Test CronJob generation with missing required fields."""
    # Create test data with missing required fields
    parent_resource = {
        "metadata": {
            "name": "test-metric",
            "namespace": "default"
        },
        "spec": {
            "name": "test-metric",
            "description": "Test metric",
            "cronSchedule": "0 * * * *"
            # Missing: componentType, facts, grading-system
        }
    }

    # Call function
    children, status = build_metric_evaluator_cronjob(parent_resource)

    # Verify result
    assert status == "Failed"
    assert len(children) == 0


def test_build_metric_evaluator_cronjob_exception():
    """Test CronJob generation with an exception."""
    # Create test data
    parent_resource = {
        "metadata": {
            "name": "test-metric",
            "namespace": "default"
        },
        "spec": {
            "name": "test-metric",
            "description": "Test metric",
            "componentType": "service",
            "cronSchedule": "0 * * * *",
            "facts": ["test.fact"],
            "grading-system": "percentage"
        }
    }

    # Call function with a side effect that raises an exception
    with patch('json.dumps', side_effect=Exception("Test exception")):
        children, status = build_metric_evaluator_cronjob(parent_resource)

    # Verify result
    assert status == "Failed"
    assert len(children) == 0