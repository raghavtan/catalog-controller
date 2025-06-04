"""End-to-end tests for the catalog controller - Fixed version."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from typing import Dict, Any

import httpx
from fastapi.testclient import TestClient
from kubernetes import client

# Import your application
from main import app
from service.models.models import MetacontrollerRequest, ParentResource, KubernetesMetadata
from service.utils.compass import CompassAPI

pytestmark = pytest.mark.e2e


class TestE2EMetricsAndScorecards:
    """Comprehensive end-to-end tests for metrics and scorecard sync/finalize operations"""

    @pytest.fixture
    def test_client(self):
        return TestClient(app)

    @pytest.fixture
    def base_metadata(self):
        return {
            "name": "test-metric",
            "namespace": "default",
            "uid": "12345-67890",
            "resourceVersion": "1",
            "generation": 1,
            "creationTimestamp": "2023-01-01T00:00:00Z",  # Use string instead of datetime object
            "annotations": {"example.com/annotation": "value"},
            "labels": {"app": "test", "version": "v1"},
            "finalizers": []
        }

    @pytest.fixture
    def metric_spec(self):
        return {
            "name": "cpu-usage-metric",
            "description": "CPU usage percentage metric",
            "componentType": "service",
            "cronSchedule": "0 */6 * * *",
            "facts": ["cpu.usage"],
            "grading-system": "percentage"
        }

    @pytest.fixture
    def scorecard_spec(self):
        return {
            "name": "service-quality-scorecard",
            "description": "Service quality assessment scorecard",
            "state": "active",
            "componentTypeIds": ["service", "deployment"],
            "criteria": [
                {
                    "hasMetricValue": {
                        "metricName": "cpu-usage-metric",
                        "operator": "lt",
                        "value": 80
                    },
                    "weight": 0.5
                },
                {
                    "hasMetricValue": {
                        "metricName": "memory-usage-metric",
                        "operator": "lt",
                        "value": 90
                    },
                    "weight": 0.5
                }
            ]
        }

    def create_metacontroller_request(self, resource_type: str, metadata: Dict, spec: Dict,
                                      status: Dict = None) -> Dict:
        """Helper to create metacontroller request payload"""
        return {
            "controller": {"apiVersion": "v1", "kind": "CompositeController"},
            "parent": {
                "apiVersion": "catalog.onefootball.com/v1alpha1",
                "kind": resource_type.capitalize(),
                "metadata": metadata,
                "spec": spec,
                "status": status or {}
            },
            "children": {},
            "related": {},
            "finalizing": False
        }


class TestMetricSync(TestE2EMetricsAndScorecards):
    """Test cases for metric sync operations"""

    @pytest.mark.asyncio
    async def test_metric_sync_new_metric_creation(self, test_client, base_metadata, metric_spec):
        """Test creating a new metric when it doesn't exist in Compass"""
        # Setup mocks
        with patch('service.handlers.metric.CompassAPI') as mock_compass_api:
            mock_compass_instance = AsyncMock()
            mock_compass_api.return_value = mock_compass_instance

            # Mock responses: not found by name, successful creation
            mock_compass_instance.get_by_name.return_value = {"status_code": 404, "message": "Not found"}
            mock_compass_instance.create.return_value = {
                "status_code": 201,
                "data": {"id": "new-metric-id-123"}
            }
            mock_compass_instance.get_by_id.return_value = {
                "status_code": 200,
                "data": {"id": "new-metric-id-123", "spec": metric_spec}
            }

            request_payload = self.create_metacontroller_request("metric", base_metadata, metric_spec)

            response = test_client.post("/sync/metric", json=request_payload)

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["status"]["id"] == "new-metric-id-123"
            assert response_data["status"]["cronJob"] == "Success"
            assert len(response_data["children"]) == 1  # CronJob should be created

            # Verify compass API calls
            mock_compass_instance.get_by_name.assert_called_once_with("metric", "test-metric")
            mock_compass_instance.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_metric_sync_existing_metric_import(self, test_client, base_metadata, metric_spec):
        """Test importing existing metric by name"""
        with patch('service.handlers.metric.CompassAPI') as mock_compass_api:
            mock_compass_instance = AsyncMock()
            mock_compass_api.return_value = mock_compass_instance

            # Mock responses: found by name
            mock_compass_instance.get_by_name.return_value = {
                "status_code": 200,
                "data": {"id": "existing-metric-id-456"}
            }
            mock_compass_instance.get_by_id.return_value = {
                "status_code": 200,
                "data": {"id": "existing-metric-id-456", "spec": metric_spec}
            }

            request_payload = self.create_metacontroller_request("metric", base_metadata, metric_spec)

            response = test_client.post("/sync/metric", json=request_payload)

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["status"]["id"] == "existing-metric-id-456"

            mock_compass_instance.get_by_name.assert_called_once_with("metric", "test-metric")
            mock_compass_instance.get_by_id.assert_called_with("metric", "existing-metric-id-456")

    @pytest.mark.asyncio
    async def test_metric_sync_with_status_id_validation(self, test_client, base_metadata, metric_spec):
        """Test metric sync when status already contains an ID"""
        with patch('service.handlers.metric.CompassAPI') as mock_compass_api:
            mock_compass_instance = AsyncMock()
            mock_compass_api.return_value = mock_compass_instance

            status = {"id": "status-metric-id-789"}

            # Mock responses: existing ID is valid
            mock_compass_instance.get_by_id.return_value = {
                "status_code": 200,
                "data": {"id": "status-metric-id-789", "spec": metric_spec}
            }

            request_payload = self.create_metacontroller_request("metric", base_metadata, metric_spec, status)

            response = test_client.post("/sync/metric", json=request_payload)

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["status"]["id"] == "status-metric-id-789"

            # Should use existing ID, not try to import by name
            mock_compass_instance.get_by_id.assert_called_with("metric", "status-metric-id-789")
            mock_compass_instance.get_by_name.assert_not_called()

    @pytest.mark.asyncio
    async def test_metric_sync_spec_update_required(self, test_client, base_metadata, metric_spec):
        """Test metric sync when spec differences require an update"""
        with patch('service.handlers.metric.CompassAPI') as mock_compass_api:
            mock_compass_instance = AsyncMock()
            mock_compass_api.return_value = mock_compass_instance

            # Different spec in Compass
            compass_spec = metric_spec.copy()
            compass_spec["description"] = "Old description"

            mock_compass_instance.get_by_name.return_value = {
                "status_code": 200,
                "data": {"id": "update-metric-id-999"}
            }
            mock_compass_instance.get_by_id.return_value = {
                "status_code": 200,
                "data": {"id": "update-metric-id-999", "spec": compass_spec}
            }
            mock_compass_instance.update.return_value = {
                "status_code": 200,
                "data": {"id": "update-metric-id-999"}
            }

            request_payload = self.create_metacontroller_request("metric", base_metadata, metric_spec)

            response = test_client.post("/sync/metric", json=request_payload)

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["status"]["id"] == "update-metric-id-999"

            # Verify update was called
            mock_compass_instance.update.assert_called_once()


class TestScorecardSync(TestE2EMetricsAndScorecards):
    """Test cases for scorecard sync operations"""

    @pytest.mark.asyncio
    async def test_scorecard_sync_new_creation(self, test_client, base_metadata, scorecard_spec):
        """Test creating a new scorecard with valid metrics"""
        # Setup mocks
        with patch('service.handlers.scorecard.CompassAPI') as mock_compass_api, \
             patch('service.handlers.scorecard.config.load_incluster_config'), \
             patch('service.handlers.scorecard.client.CustomObjectsApi') as mock_k8s_api:

            mock_compass_instance = AsyncMock()
            mock_compass_api.return_value = mock_compass_instance
            mock_k8s_instance = MagicMock()
            mock_k8s_api.return_value = mock_k8s_instance

            # Mock metric validation responses
            mock_k8s_instance.get_cluster_custom_object.side_effect = [
                {"metadata": {"name": "cpu-usage-metric"}, "status": {"id": "cpu-metric-id-123"}},
                {"metadata": {"name": "memory-usage-metric"}, "status": {"id": "memory-metric-id-456"}}
            ]

            # Mock Compass API responses
            mock_compass_instance.get_by_name.return_value = {"status_code": 404, "message": "Not found"}
            mock_compass_instance.create.return_value = {
                "status_code": 201,
                "data": {"id": "new-scorecard-id-789"}
            }
            mock_compass_instance.get_by_id.return_value = {
                "status_code": 200,
                "data": {"id": "new-scorecard-id-789", "spec": {}}
            }
            mock_compass_instance.update.return_value = {
                "status_code": 200,
                "data": {"id": "new-scorecard-id-789"}
            }

            request_payload = self.create_metacontroller_request("scorecard", base_metadata, scorecard_spec)

            response = test_client.post("/sync/scorecard", json=request_payload)

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["status"]["id"] == "new-scorecard-id-789"
            assert "cpu-usage-metric" in response_data["status"]["metricsSummary"]
            assert "memory-usage-metric" in response_data["status"]["metricsSummary"]
            assert len(response_data["status"]["metricAssociation"]) == 2

    @pytest.mark.asyncio
    async def test_scorecard_sync_with_invalid_metrics(self, test_client, base_metadata, scorecard_spec):
        """Test scorecard sync when some metrics are invalid/missing"""
        with patch('service.handlers.scorecard.CompassAPI') as mock_compass_api, \
                patch('service.handlers.scorecard.config.load_incluster_config'), \
                patch('service.handlers.scorecard.client.CustomObjectsApi') as mock_k8s_api:

            mock_compass_instance = AsyncMock()
            mock_compass_api.return_value = mock_compass_instance
            mock_k8s_instance = MagicMock()
            mock_k8s_api.return_value = mock_k8s_instance

            # Mock responses: first metric exists, second doesn't
            def mock_get_metric(group, version, plural, name):
                if name == "cpu-usage-metric":
                    return {"metadata": {"name": "cpu-usage-metric"}, "status": {"id": "cpu-metric-id-123"}}
                elif name == "memory-usage-metric":
                    raise client.ApiException(status=404, reason="Not Found")

            mock_k8s_instance.get_cluster_custom_object.side_effect = mock_get_metric

            mock_compass_instance.get_by_name.return_value = {"status_code": 404, "message": "Not found"}
            # Fix: Return proper dictionary instead of MagicMock
            mock_compass_instance.create.return_value = {
                "status_code": 201,
                "data": {"id": "scorecard-with-invalid-metrics"}
            }
            mock_compass_instance.get_by_id.return_value = {
                "status_code": 200,
                "data": {"id": "scorecard-with-invalid-metrics", "spec": {}}
            }
            # Add proper update mock to avoid any potential issues
            mock_compass_instance.update.return_value = {
                "status_code": 200,
                "data": {"id": "scorecard-with-invalid-metrics"}
            }

            request_payload = self.create_metacontroller_request("scorecard", base_metadata, scorecard_spec)

            response = test_client.post("/sync/scorecard", json=request_payload)

            assert response.status_code == 200
            response_data = response.json()
            assert "cpu-usage-metric" in response_data["status"]["metricsSummary"]
            assert "INVALID" in response_data["status"]["metricsSummary"]
            assert len(response_data["status"]["metricAssociation"]) == 1  # Only valid metric


class TestFinalize(TestE2EMetricsAndScorecards):
    """Test cases for resource finalization"""

    @pytest.mark.asyncio
    async def test_finalize_metric_success(self, test_client, base_metadata, metric_spec):
        """Test successful metric finalization"""
        with patch('service.handlers.cleanup.CompassAPI') as mock_compass_api:
            mock_compass_instance = AsyncMock()
            mock_compass_api.return_value = mock_compass_instance

            status = {"id": "metric-to-delete-123"}
            mock_compass_instance.delete.return_value = {"status_code": 200}

            request_payload = self.create_metacontroller_request("metric", base_metadata, metric_spec, status)
            request_payload["finalizing"] = True

            response = test_client.post("/finalize", json=request_payload)

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["finalized"] is True

            mock_compass_instance.delete.assert_called_once_with("metric", "metric-to-delete-123")

    @pytest.mark.asyncio
    async def test_finalize_scorecard_success(self, test_client, base_metadata, scorecard_spec):
        """Test successful scorecard finalization"""
        with patch('service.handlers.cleanup.CompassAPI') as mock_compass_api:
            mock_compass_instance = AsyncMock()
            mock_compass_api.return_value = mock_compass_instance

            status = {"id": "scorecard-to-delete-456"}
            mock_compass_instance.delete.return_value = {"status_code": 204}  # No content

            request_payload = self.create_metacontroller_request("scorecard", base_metadata, scorecard_spec, status)
            request_payload["finalizing"] = True

            response = test_client.post("/finalize", json=request_payload)

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["finalized"] is True

            mock_compass_instance.delete.assert_called_once_with("scorecard", "scorecard-to-delete-456")

    @pytest.mark.asyncio
    async def test_finalize_no_compass_id(self, test_client, base_metadata, metric_spec):
        """Test finalization when no Compass ID exists"""
        with patch('service.handlers.cleanup.CompassAPI') as mock_compass_api:
            mock_compass_instance = AsyncMock()
            mock_compass_api.return_value = mock_compass_instance

            # No status or no ID in status
            request_payload = self.create_metacontroller_request("metric", base_metadata, metric_spec)
            request_payload["finalizing"] = True

            response = test_client.post("/finalize", json=request_payload)

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["finalized"] is True

            # Should not attempt to delete
            mock_compass_instance.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_finalize_resource_not_found(self, test_client, base_metadata, metric_spec):
        """Test finalization when resource is not found in Compass (already deleted)"""
        with patch('service.handlers.cleanup.CompassAPI') as mock_compass_api:
            mock_compass_instance = AsyncMock()
            mock_compass_api.return_value = mock_compass_instance

            status = {"id": "non-existent-resource-789"}
            mock_compass_instance.delete.return_value = {"status_code": 404, "message": "Resource not found"}

            request_payload = self.create_metacontroller_request("metric", base_metadata, metric_spec, status)
            request_payload["finalizing"] = True

            response = test_client.post("/finalize", json=request_payload)

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["finalized"] is True  # Should still mark as finalized


class TestEdgeCases(TestE2EMetricsAndScorecards):
    """Test edge cases and error scenarios"""

    @pytest.mark.asyncio
    async def test_unsupported_resource_type(self, test_client, base_metadata, metric_spec):
        """Test sync with unsupported resource type"""
        request_payload = self.create_metacontroller_request("metric", base_metadata, metric_spec)

        response = test_client.post("/sync/unsupported", json=request_payload)

        assert response.status_code == 400
        response_data = response.json()
        assert "Unsupported resource type" in response_data["error"]

    @pytest.mark.asyncio
    async def test_malformed_request_payload(self, test_client):
        """Test sync with malformed request payload"""
        malformed_payload = {
            "controller": {"apiVersion": "v1"},
            # Missing required fields
        }

        response = test_client.post("/sync/metric", json=malformed_payload)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, test_client):
        """Test health check endpoint"""
        response = test_client.get("/healthz")

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "ok"