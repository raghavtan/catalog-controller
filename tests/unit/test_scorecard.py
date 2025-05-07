import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from service.handlers.scorecard import sync_scorecard, create_scorecard, validate_metrics
from service.models.models import MetacontrollerRequest
from kubernetes.client.rest import ApiException


@pytest.fixture
def sync_request_scorecard(load_json_fixture):
    """Load the sync.request.scorecard.json fixture"""
    return load_json_fixture('sync.request.scorecard.json')


@pytest.fixture
def scorecard_request(sync_request_scorecard):
    """Create a MetacontrollerRequest from the sync.request.scorecard.json fixture"""
    return MetacontrollerRequest(**sync_request_scorecard)


@pytest.fixture
def mock_compass_api():
    """Mock the CompassAPI class"""
    with patch('service.handlers.scorecard.CompassAPI') as mock_api:
        instance = mock_api.return_value
        instance.dummy_call = AsyncMock()
        yield instance


@pytest.fixture
def mock_k8s_api():
    """Mock the Kubernetes CustomObjectsApi"""
    with patch('service.handlers.scorecard.client.CustomObjectsApi') as mock_api:
        instance = mock_api.return_value
        instance.get_cluster_custom_object = MagicMock()
        yield instance


@pytest.fixture
def mock_load_incluster_config():
    """Mock the Kubernetes config.load_incluster_config function"""
    with patch('service.handlers.scorecard.config.load_incluster_config') as mock_load:
        yield mock_load


class TestScorecardHandler:

    @pytest.mark.asyncio
    async def test_sync_scorecard_existing_id_success(self, scorecard_request, mock_compass_api):
        """Test sync_scorecard when scorecard has existing ID and is found in Compass"""
        # Set up mock
        mock_compass_api.dummy_call.return_value = {
            'status_code': 200,
            'id': 'observability/scorecard::123456789'
        }

        # Mock validate_metrics to return fixture data
        with patch('service.handlers.scorecard.validate_metrics') as mock_validate:
            parent_data = scorecard_request.parent.model_dump(by_alias=True)
            metrics_summary = parent_data['status']['metricsSummary']
            metric_association = parent_data['status']['metricAssociation']
            mock_validate.return_value = (metrics_summary, metric_association)

            # Call function
            response, status_code = await sync_scorecard(scorecard_request)

        # Assertions
        assert status_code == 200
        assert response['status']['id'] == 'observability/scorecard::123456789'
        assert response['status']['metricsSummary'] == metrics_summary
        assert response['status']['metricAssociation'] == metric_association
        mock_compass_api.dummy_call.assert_called_once_with("get", "scorecard",
                                                            scorecard_request.parent.model_dump(by_alias=True))

    @pytest.mark.asyncio
    async def test_sync_scorecard_id_mismatch(self, scorecard_request, mock_compass_api):
        """Test sync_scorecard when Compass returns a different ID than the one in status"""
        # Modify request to have a different ID
        parent = scorecard_request.parent.model_dump(by_alias=True)
        parent['status']['id'] = 'observability/scorecard::old123456'

        # Set up mock
        mock_compass_api.dummy_call.return_value = {
            'status_code': 200,
            'id': 'observability/scorecard::new789012'
        }

        # Mock metric validation
        with patch('service.handlers.scorecard.validate_metrics') as mock_validate:
            mock_validate.return_value = ("metrics_summary", [{"metricName": "test", "metricId": "test-id"}])

            # Call function with modified request
            modified_request = MetacontrollerRequest(**{
                **scorecard_request.model_dump(),
                'parent': parent
            })
            response, status_code = await sync_scorecard(modified_request)

        # Assertions
        assert status_code == 200
        assert response['status']['id'] == 'observability/scorecard::new789012'
        assert response['status']['metricsSummary'] == "metrics_summary"
        assert response['status']['metricAssociation'] == [{"metricName": "test", "metricId": "test-id"}]

    @pytest.mark.asyncio
    async def test_sync_scorecard_not_found_in_compass(self, scorecard_request, mock_compass_api):
        """Test sync_scorecard when scorecard has ID but is not found in Compass"""
        # Set up mock for not found - ID is None
        mock_compass_api.dummy_call.side_effect = [
            {'status_code': 200, 'id': None},  # Response says valid but ID is None
            {'status_code': 201, 'id': 'observability/scorecard::new123456'}  # Created
        ]

        # Mock metric validation
        with patch('service.handlers.scorecard.validate_metrics') as mock_validate:
            mock_validate.return_value = ("metrics_summary", [{"metricName": "test", "metricId": "test-id"}])

            # Call function
            response, status_code = await sync_scorecard(scorecard_request)

        # Assertions
        assert status_code == 200
        assert response['status']['id'] == 'observability/scorecard::new123456'
        assert mock_compass_api.dummy_call.call_count == 2
        assert mock_compass_api.dummy_call.call_args_list[0][0] == (
        "get", "scorecard", scorecard_request.parent.model_dump(by_alias=True))
        assert mock_compass_api.dummy_call.call_args_list[1][0] == (
        "create", "scorecard", scorecard_request.parent.model_dump(by_alias=True))

    @pytest.mark.asyncio
    async def test_sync_scorecard_compass_error(self, scorecard_request, mock_compass_api):
        """Test sync_scorecard when Compass returns an error"""
        # Set up mock for error
        mock_compass_api.dummy_call.return_value = {
            'status_code': 500,
            'message': 'Internal Server Error'
        }

        # Call function
        response, status_code = await sync_scorecard(scorecard_request)

        # Assertions
        assert status_code == 200  # Note: Original code returns 200 even for Compass errors
        assert response['status']['id'] is None  # ID should be None

    @pytest.mark.asyncio
    async def test_sync_scorecard_no_id(self, scorecard_request, mock_compass_api):
        """Test sync_scorecard when scorecard doesn't have an ID yet"""
        # Modify request to remove ID
        parent = scorecard_request.parent.model_dump(by_alias=True)
        parent['status'] = {}  # Remove status with ID

        # Set up mock for successful creation
        mock_compass_api.dummy_call.return_value = {
            'status_code': 201,
            'id': 'observability/scorecard::new123456'
        }

        # Mock metric validation
        with patch('service.handlers.scorecard.validate_metrics') as mock_validate:
            mock_validate.return_value = ("metrics_summary", [{"metricName": "test", "metricId": "test-id"}])

            # Call function with modified request
            modified_request = MetacontrollerRequest(**{
                **scorecard_request.model_dump(),
                'parent': parent
            })
            response, status_code = await sync_scorecard(modified_request)

        # Assertions
        assert status_code == 200
        assert response['status']['id'] == 'observability/scorecard::new123456'
        mock_compass_api.dummy_call.assert_called_once_with("create", "scorecard", parent)

    @pytest.mark.asyncio
    async def test_sync_scorecard_exception(self, scorecard_request, mock_compass_api):
        """Test sync_scorecard when an exception occurs"""
        # Set up mock to raise exception
        mock_compass_api.dummy_call.side_effect = Exception("Test exception")

        # Call function
        response, status_code = await sync_scorecard(scorecard_request)

        # Assertions
        assert status_code == 500
        assert "error" in response['status']
        assert "Test exception" in response['status']['error']

    @pytest.mark.asyncio
    async def test_create_scorecard_success(self, mock_compass_api):
        """Test create_scorecard when creation is successful"""
        # Set up mock
        mock_compass_api.dummy_call.return_value = {
            'status_code': 201,
            'id': 'test-scorecard/scorecard::123456'
        }

        # Call function
        parent = {'metadata': {'name': 'test-scorecard'}}
        result = await create_scorecard(mock_compass_api, parent, 'test-scorecard')

        # Assertions
        assert result == 'test-scorecard/scorecard::123456'
        mock_compass_api.dummy_call.assert_called_once_with("create", "scorecard", parent)

    @pytest.mark.asyncio
    async def test_create_scorecard_failure(self, mock_compass_api):
        """Test create_scorecard when creation fails"""
        # Set up mock
        mock_compass_api.dummy_call.return_value = {
            'status_code': 400,
            'message': 'Bad request'
        }

        # Call function
        parent = {'metadata': {'name': 'test-scorecard'}}
        result = await create_scorecard(mock_compass_api, parent, 'test-scorecard')

        # Assertions
        assert result is None
        mock_compass_api.dummy_call.assert_called_once_with("create", "scorecard", parent)

    @pytest.mark.asyncio
    async def test_create_scorecard_exception(self, mock_compass_api):
        """Test create_scorecard when an exception occurs"""
        # Set up mock to raise exception
        mock_compass_api.dummy_call.side_effect = Exception("Test exception")

        # Call function and assert it raises
        parent = {'metadata': {'name': 'test-scorecard'}}
        with pytest.raises(Exception, match="Test exception"):
            await create_scorecard(mock_compass_api, parent, 'test-scorecard')

    @pytest.mark.asyncio
    async def test_validate_metrics_all_valid(self, mock_k8s_api, mock_load_incluster_config):
        """Test validate_metrics when all metrics are valid"""
        # Set up mock for k8s API responses
        mock_k8s_api.get_cluster_custom_object.side_effect = [
            {'status': {'id': 'metric1/metric::id1'}},
            {'status': {'id': 'metric2/metric::id2'}},
        ]

        # Parent with two metrics
        parent = {
            'spec': {
                'criteria': [
                    {'hasMetricValue': {'metricName': 'metric1'}},
                    {'hasMetricValue': {'metricName': 'metric2'}}
                ]
            }
        }

        # Call function
        summary, associations = await validate_metrics(parent)

        # Assertions
        assert summary == "metric1, metric2"
        assert len(associations) == 2
        assert associations[0]['metricName'] == 'metric1'
        assert associations[0]['metricId'] == 'metric1/metric::id1'
        assert associations[1]['metricName'] == 'metric2'
        assert associations[1]['metricId'] == 'metric2/metric::id2'
        assert mock_k8s_api.get_cluster_custom_object.call_count == 2

    @pytest.mark.asyncio
    async def test_validate_metrics_some_pending(self, mock_k8s_api, mock_load_incluster_config):
        """Test validate_metrics when some metrics are pending (no ID)"""
        # Set up mock for k8s API responses
        mock_k8s_api.get_cluster_custom_object.side_effect = [
            {'status': {'id': 'metric1/metric::id1'}},  # Valid with ID
            {'status': {}}  # Valid but no ID
        ]

        # Parent with two metrics
        parent = {
            'spec': {
                'criteria': [
                    {'hasMetricValue': {'metricName': 'metric1'}},
                    {'hasMetricValue': {'metricName': 'metric2'}}
                ]
            }
        }

        # Call function
        summary, associations = await validate_metrics(parent)

        # Assertions
        assert summary == "metric1, metric2(PENDING)"
        assert len(associations) == 1
        assert associations[0]['metricName'] == 'metric1'
        assert associations[0]['metricId'] == 'metric1/metric::id1'
        assert mock_k8s_api.get_cluster_custom_object.call_count == 2

    @pytest.mark.asyncio
    async def test_validate_metrics_not_found(self, mock_k8s_api, mock_load_incluster_config):
        """Test validate_metrics when metrics are not found"""
        # Set up mock to raise ApiException
        mock_k8s_api.get_cluster_custom_object.side_effect = ApiException(status=404, reason="Not found")

        # Parent with one metric
        parent = {
            'spec': {
                'criteria': [
                    {'hasMetricValue': {'metricName': 'nonexistent-metric'}}
                ]
            }
        }

        # Call function
        summary, associations = await validate_metrics(parent)

        # Assertions
        assert summary == "nonexistent-metric(INVALID)"
        assert len(associations) == 0
        mock_k8s_api.get_cluster_custom_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_metrics_exception(self, mock_k8s_api, mock_load_incluster_config):
        """Test validate_metrics when an exception occurs"""
        # Set up mock to raise a general exception
        mock_load_incluster_config.side_effect = Exception("Test exception")

        # Parent with metrics
        parent = {
            'spec': {
                'criteria': [
                    {'hasMetricValue': {'metricName': 'metric1'}}
                ]
            }
        }

        # Call function
        summary, associations = await validate_metrics(parent)

        # Assertions
        assert "Error validating metrics: Test exception" in summary
        assert len(associations) == 0

    @pytest.mark.asyncio
    async def test_validate_metrics_real_fixture(self, scorecard_request, mock_k8s_api, mock_load_incluster_config):
        """Test validate_metrics with the real fixture data"""
        # Set up mock for k8s API responses - one for each metric in the fixture
        mock_k8s_api.get_cluster_custom_object.side_effect = [
            {'status': {'id': 'instrumentation-check/metric::123456789'}},
            {'status': {'id': 'critical-alerts-slo-check/metric::123456789'}},
            {'status': {'id': 'alert-routing-and-notifications/metric::123456789'}},
            {'status': {'id': 'observability-documentation/metric::123456789'}}
        ]

        # Get parent from the fixture
        parent = scorecard_request.parent.model_dump(by_alias=True)

        # Call function
        summary, associations = await validate_metrics(parent)

        # Assertions
        assert summary == "instrumentation-check, critical-alerts-slo-check, alert-routing-and-notifications, observability-documentation"
        assert len(associations) == 4

        # Check that each metric is properly associated
        for association in associations:
            assert association['metricName'] in [
                "instrumentation-check",
                "critical-alerts-slo-check",
                "alert-routing-and-notifications",
                "observability-documentation"
            ]
            assert association['metricId'].endswith('metric::123456789')

        # Check that k8s API was called for each metric
        assert mock_k8s_api.get_cluster_custom_object.call_count == 4