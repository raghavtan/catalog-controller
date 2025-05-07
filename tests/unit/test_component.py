import pytest
import sys
import os
import yaml
from unittest.mock import patch, AsyncMock, MagicMock
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from service.handlers.component import sync_component, metrics_match, create_component_with_metrics, \
    get_applicable_metrics
from service.models.models import MetacontrollerRequest, SyncResponse
from service.utils.compass import CompassAPI
from kubernetes.client.rest import ApiException


@pytest.fixture
def component_yaml():
    with open('tests/fixtures/component.yaml', 'r') as f:
        return yaml.safe_load(f.read())

@pytest.fixture
def sync_request_component(component_yaml):
    """Create a sync request with the component resource"""
    return {
        "controller": {"group": "metacontroller.k8s.io", "version": "v1alpha1", "kind": "CompositeController"},
        "parent": component_yaml,
        "children": {},
        "related": {},
        "finalizing": False
    }


@pytest.fixture
def component_request(sync_request_component):
    """Create a MetacontrollerRequest from the sync request"""
    return MetacontrollerRequest(**sync_request_component)


@pytest.fixture
def component_with_id(component_yaml):
    """Create a component with an existing ID in status"""
    component = component_yaml.copy()
    component['status'] = {
        'id': 'simple-service/component::123456789',
        'metricAssociation': [
            {
                'metricName': 'instrumentation-check',
                'metricId': 'instrumentation-check/metric::123456789',
                'metricSourceId': 'simple-service-instrumentation-check/metricSource:::123456789'
            }
        ]
    }
    return component


@pytest.fixture
def component_request_with_id(sync_request_component, component_with_id):
    """Create a request with a component that has an ID"""
    request = sync_request_component.copy()
    request['parent'] = component_with_id
    return MetacontrollerRequest(**request)


@pytest.fixture
def mock_compass_api():
    """Mock the CompassAPI class"""
    with patch('service.handlers.component.CompassAPI') as mock_api:
        instance = mock_api.return_value
        instance.dummy_call = AsyncMock()
        yield instance


@pytest.fixture
def mock_k8s_api():
    """Mock the Kubernetes CustomObjectsApi"""
    with patch('service.handlers.component.client.CustomObjectsApi') as mock_api:
        instance = mock_api.return_value
        instance.list_cluster_custom_object = MagicMock()
        instance.get_cluster_custom_object = MagicMock()
        yield instance


@pytest.fixture
def mock_load_incluster_config():
    """Mock the Kubernetes config.load_incluster_config function"""
    with patch('service.handlers.component.config.load_incluster_config') as mock_load:
        yield mock_load


@pytest.fixture
def applicable_metrics():
    """Return a list of applicable metrics for testing"""
    return [
        {'metricName': 'instrumentation-check', 'metricId': 'instrumentation-check/metric::123456789'},
        {'metricName': 'alert-routing-and-notifications',
         'metricId': 'alert-routing-and-notifications/metric::123456789'}
    ]


@pytest.fixture
def mock_get_applicable_metrics(applicable_metrics):
    """Mock the get_applicable_metrics function"""
    with patch('service.handlers.component.get_applicable_metrics',
               AsyncMock(return_value=applicable_metrics)) as mock_fn:
        yield mock_fn


class TestComponentHandler:

    @pytest.mark.asyncio
    async def test_sync_component_existing_with_matching_metrics(self, component_request_with_id, mock_compass_api,
                                                                 applicable_metrics, mock_get_applicable_metrics):
        """Test syncing a component that exists in Compass with matching metrics"""
        # Configure mocks
        mock_compass_api.dummy_call.return_value = {
            'status_code': 200,
            'id': 'simple-service/component::123456789',
            'metricAssociation': [
                {'metricName': 'instrumentation-check', 'metricId': 'instrumentation-check/metric::123456789'},
                {'metricName': 'alert-routing-and-notifications',
                 'metricId': 'alert-routing-and-notifications/metric::123456789'}
            ]
        }

        # Override the metricAssociation in the request
        component_request_with_id.parent.status['metricAssociation'] = [
            {'metricName': 'instrumentation-check', 'metricId': 'instrumentation-check/metric::123456789'},
            {'metricName': 'alert-routing-and-notifications',
             'metricId': 'alert-routing-and-notifications/metric::123456789'}
        ]

        # Call the function
        response, status_code = await sync_component(component_request_with_id)

        # Assertions
        assert status_code == 200
        assert response['status']['id'] == 'simple-service/component::123456789'
        assert len(response['status']['metricAssociation']) == 2
        assert response['children'] == []

        # Verify the API was called with get operation
        mock_compass_api.dummy_call.assert_called_once_with(
            "get", "component", component_request_with_id.parent.model_dump(by_alias=True)
        )

        # Verify get_applicable_metrics was called with the type ID
        mock_get_applicable_metrics.assert_called_once_with("SERVICE")

    @pytest.mark.asyncio
    async def test_sync_component_existing_with_mismatched_metrics(self, component_request_with_id, mock_compass_api,
                                                                   applicable_metrics, mock_get_applicable_metrics):
        """Test syncing a component that exists in Compass but has mismatched metrics (requiring recreation)"""
        # Configure mocks
        mock_compass_api.dummy_call.side_effect = [
            # First call - get component
            {
                'status_code': 200,
                'id': 'simple-service/component::123456789',
                'metricAssociation': [
                    {'metricName': 'instrumentation-check', 'metricId': 'instrumentation-check/metric::123456789'}
                    # Missing the second metric
                ]
            },
            # Second call - recreate component with metrics
            {
                'status_code': 201,
                'id': 'simple-service/component::new987654',
                'metricSources': [
                    {
                        'metricName': 'instrumentation-check',
                        'metricId': 'instrumentation-check/metric::123456789',
                        'metricSourceId': 'simple-service-instrumentation-check/metricSource:::123456789'
                    },
                    {
                        'metricName': 'alert-routing-and-notifications',
                        'metricId': 'alert-routing-and-notifications/metric::123456789',
                        'metricSourceId': 'simple-service-alert-routing-and-notifications/metricSource:::123456789'
                    }
                ]
            }
        ]

        # Call the function
        response, status_code = await sync_component(component_request_with_id)

        # Assertions
        assert status_code == 200
        assert response['status']['id'] == 'simple-service/component::new987654'
        assert len(response['status']['metricAssociation']) == 2
        assert response['children'] == []

        # Verify the API was called twice
        assert mock_compass_api.dummy_call.call_count == 2

        # First call should be get
        assert mock_compass_api.dummy_call.call_args_list[0][0][0] == "get"
        assert mock_compass_api.dummy_call.call_args_list[0][0][1] == "component"

        # Second call should be create
        assert mock_compass_api.dummy_call.call_args_list[1][0][0] == "create"
        assert mock_compass_api.dummy_call.call_args_list[1][0][1] == "component"

        # Verify request data for second call has component and metrics
        second_call_data = mock_compass_api.dummy_call.call_args_list[1][0][2]
        assert 'component' in second_call_data
        assert 'metrics' in second_call_data
        assert len(second_call_data['metrics']) == 2

    @pytest.mark.asyncio
    async def test_sync_component_existing_not_found(self, component_request_with_id, mock_compass_api,
                                                     applicable_metrics, mock_get_applicable_metrics):
        """Test syncing a component that has an ID but is not found in Compass"""
        # Configure mocks
        mock_compass_api.dummy_call.side_effect = [
            # First call - get component (not found)
            {
                'status_code': 404,
                'message': 'Component not found'
            },
            # Second call - create component
            {
                'status_code': 201,
                'id': 'simple-service/component::new987654',
                'metricSources': [
                    {
                        'metricName': 'instrumentation-check',
                        'metricId': 'instrumentation-check/metric::123456789',
                        'metricSourceId': 'simple-service-instrumentation-check/metricSource:::123456789'
                    },
                    {
                        'metricName': 'alert-routing-and-notifications',
                        'metricId': 'alert-routing-and-notifications/metric::123456789',
                        'metricSourceId': 'simple-service-alert-routing-and-notifications/metricSource:::123456789'
                    }
                ]
            }
        ]

        # Call the function
        response, status_code = await sync_component(component_request_with_id)

        # Assertions
        assert status_code == 200
        assert response['status']['id'] == 'simple-service/component::new987654'
        assert len(response['status']['metricAssociation']) == 2
        assert response['children'] == []

        # Verify the API was called twice
        assert mock_compass_api.dummy_call.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_component_id_mismatch(self, component_request_with_id, mock_compass_api, applicable_metrics,
                                              mock_get_applicable_metrics):
        """Test syncing a component where the ID from Compass doesn't match the saved ID"""
        # Configure mocks
        mock_compass_api.dummy_call.side_effect = [
            # First call - get component with different ID
            {
                'status_code': 200,
                'id': 'simple-service/component::different-id',
                'metricAssociation': [
                    {'metricName': 'instrumentation-check', 'metricId': 'instrumentation-check/metric::123456789'},
                    {'metricName': 'alert-routing-and-notifications',
                     'metricId': 'alert-routing-and-notifications/metric::123456789'}
                ]
            },
            # Second call - create component
            {
                'status_code': 201,
                'id': 'simple-service/component::new987654',
                'metricSources': [
                    {
                        'metricName': 'instrumentation-check',
                        'metricId': 'instrumentation-check/metric::123456789',
                        'metricSourceId': 'simple-service-instrumentation-check/metricSource:::123456789'
                    },
                    {
                        'metricName': 'alert-routing-and-notifications',
                        'metricId': 'alert-routing-and-notifications/metric::123456789',
                        'metricSourceId': 'simple-service-alert-routing-and-notifications/metricSource:::123456789'
                    }
                ]
            }
        ]

        # Call the function
        response, status_code = await sync_component(component_request_with_id)

        # Assertions
        assert status_code == 200
        assert response['status']['id'] == 'simple-service/component::new987654'
        assert len(response['status']['metricAssociation']) == 2
        assert response['children'] == []

        # Verify the API was called twice
        assert mock_compass_api.dummy_call.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_component_new(self, component_request, mock_compass_api, applicable_metrics,
                                      mock_get_applicable_metrics):
        """Test syncing a component that doesn't have an ID (new component)"""
        # Configure mocks
        mock_compass_api.dummy_call.return_value = {
            'status_code': 201,
            'id': 'simple-service/component::new987654',
            'metricSources': [
                {
                    'metricName': 'instrumentation-check',
                    'metricId': 'instrumentation-check/metric::123456789',
                    'metricSourceId': 'simple-service-instrumentation-check/metricSource:::123456789'
                },
                {
                    'metricName': 'alert-routing-and-notifications',
                    'metricId': 'alert-routing-and-notifications/metric::123456789',
                    'metricSourceId': 'simple-service-alert-routing-and-notifications/metricSource:::123456789'
                }
            ]
        }

        # Call the function
        response, status_code = await sync_component(component_request)

        # Assertions
        assert status_code == 200
        assert response['status']['id'] == 'simple-service/component::new987654'
        assert len(response['status']['metricAssociation']) == 2
        assert response['children'] == []

        # Verify the API was called once with create operation
        assert mock_compass_api.dummy_call.call_count == 1
        assert mock_compass_api.dummy_call.call_args[0][0] == "create"

    @pytest.mark.asyncio
    async def test_sync_component_api_error(self, component_request_with_id, mock_compass_api,
                                            mock_get_applicable_metrics):
        """Test syncing a component when the Compass API returns an error"""
        # Configure mocks
        mock_compass_api.dummy_call.return_value = {
            'status_code': 500,
            'message': 'Internal server error'
        }

        # Call the function
        response, status_code = await sync_component(component_request_with_id)

        # Assertions
        assert status_code == 200  # Note: Original code still returns 200 for API errors
        assert response['status']['id'] is None
        assert response['status']['metricAssociation'] == []
        assert response['children'] == []

        assert mock_compass_api.dummy_call.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_component_exception(self, component_request_with_id, mock_compass_api):
        """Test syncing a component when an exception occurs"""
        # Configure mocks
        mock_compass_api.dummy_call.side_effect = Exception("Test exception")

        # Call the function
        response, status_code = await sync_component(component_request_with_id)

        # Assertions
        assert status_code == 500
        assert "error" in response['status']
        assert "Test exception" in response['status']['error']
        assert response['children'] == []

        # Verify the API was called once
        mock_compass_api.dummy_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_component_with_metrics_success(self, component_request, mock_compass_api, applicable_metrics,
                                                         mock_get_applicable_metrics):
        """Test creating a component with metrics successfully"""
        # Configure mocks
        mock_compass_api.dummy_call.return_value = {
            'status_code': 201,
            'id': 'simple-service/component::new987654',
            'metricSources': [
                {
                    'metricName': 'instrumentation-check',
                    'metricId': 'instrumentation-check/metric::123456789',
                    'metricSourceId': 'simple-service-instrumentation-check/metricSource:::123456789'
                },
                {
                    'metricName': 'alert-routing-and-notifications',
                    'metricId': 'alert-routing-and-notifications/metric::123456789',
                    'metricSourceId': 'simple-service-alert-routing-and-notifications/metricSource:::123456789'
                }
            ]
        }

        # Call the function directly
        parent_dict = component_request.parent.model_dump(by_alias=True)
        result = await create_component_with_metrics(mock_compass_api, parent_dict, "simple-service")

        # Assertions
        assert result['id'] == 'simple-service/component::new987654'
        assert len(result['metricAssociation']) == 2

        # Verify the API was called once
        assert mock_compass_api.dummy_call.call_count == 1
        assert mock_compass_api.dummy_call.call_args[0][0] == "create"
        assert mock_compass_api.dummy_call.call_args[0][1] == "component"

        # Verify request data
        request_data = mock_compass_api.dummy_call.call_args[0][2]
        assert 'component' in request_data
        assert 'metrics' in request_data
        assert len(request_data['metrics']) == 2

    @pytest.mark.asyncio
    async def test_create_component_with_metrics_failure(self, component_request, mock_compass_api, applicable_metrics,
                                                         mock_get_applicable_metrics):
        """Test creating a component with metrics that fails"""
        # Configure mocks
        mock_compass_api.dummy_call.return_value = {
            'status_code': 400,
            'message': 'Bad request'
        }

        # Call the function directly
        parent_dict = component_request.parent.model_dump(by_alias=True)
        result = await create_component_with_metrics(mock_compass_api, parent_dict, "simple-service")

        # Assertions
        assert result['id'] is None
        assert result['metricAssociation'] == []

        # Verify the API was called once
        mock_compass_api.dummy_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_component_with_metrics_exception(self, component_request, mock_compass_api,
                                                           applicable_metrics, mock_get_applicable_metrics):
        """Test creating a component with metrics when an exception occurs"""
        # Configure mocks
        mock_compass_api.dummy_call.side_effect = Exception("Test exception")

        # Call the function directly
        parent_dict = component_request.parent.model_dump(by_alias=True)

        # Expect an exception
        with pytest.raises(Exception) as excinfo:
            await create_component_with_metrics(mock_compass_api, parent_dict, "simple-service")

        # Assert the exception
        assert str(excinfo.value) == "Test exception"

    @pytest.mark.asyncio
    async def test_create_component_with_metrics_missing_type_id(self, component_request, mock_compass_api,
                                                                 mock_get_applicable_metrics):
        """Test creating a component with metrics when typeId is missing"""
        # Remove typeId from the spec
        parent_dict = component_request.parent.model_dump(by_alias=True)
        parent_dict['spec'].pop('typeId', None)

        # Call the function directly
        result = await create_component_with_metrics(mock_compass_api, parent_dict, "simple-service")

        # Assertions
        assert result['id'] is None
        assert result['metricAssociation'] == []

        # Verify the API was not called
        mock_compass_api.dummy_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_applicable_metrics(self, mock_k8s_api, mock_load_incluster_config):
        """Test getting applicable metrics for a component type"""
        # Mock the Kubernetes API responses
        mock_k8s_api.list_cluster_custom_object.return_value = {
            'items': [
                {
                    'metadata': {'name': 'scorecard1'},
                    'spec': {
                        'componentTypeIds': ['SERVICE', 'DATABASE'],
                        'criteria': [
                            {'hasMetricValue': {'metricName': 'instrumentation-check'}},
                            {'hasMetricValue': {'metricName': 'alert-routing-and-notifications'}}
                        ]
                    }
                },
                {
                    'metadata': {'name': 'scorecard2'},
                    'spec': {
                        'componentTypeIds': ['DATABASE'],
                        'criteria': [
                            {'hasMetricValue': {'metricName': 'database-backup-check'}}
                        ]
                    }
                }
            ]
        }

        mock_k8s_api.get_cluster_custom_object.side_effect = [
            {'status': {'id': 'instrumentation-check/metric::123456789'}},
            {'status': {'id': 'alert-routing-and-notifications/metric::123456789'}}
        ]

        # Call the function
        result = await get_applicable_metrics('SERVICE')

        # Assertions
        assert len(result) == 2
        assert {'metricName': 'instrumentation-check', 'metricId': 'instrumentation-check/metric::123456789'} in result
        assert {'metricName': 'alert-routing-and-notifications',
                'metricId': 'alert-routing-and-notifications/metric::123456789'} in result

        # Verify the Kubernetes API was called
        mock_k8s_api.list_cluster_custom_object.assert_called_once()
        assert mock_k8s_api.get_cluster_custom_object.call_count == 2

    @pytest.mark.asyncio
    async def test_get_applicable_metrics_metric_not_found(self, mock_k8s_api, mock_load_incluster_config):
        """Test getting applicable metrics when a metric is not found"""
        # Mock the Kubernetes API responses
        mock_k8s_api.list_cluster_custom_object.return_value = {
            'items': [
                {
                    'metadata': {'name': 'scorecard1'},
                    'spec': {
                        'componentTypeIds': ['SERVICE'],
                        'criteria': [
                            {'hasMetricValue': {'metricName': 'instrumentation-check'}},
                            {'hasMetricValue': {'metricName': 'nonexistent-metric'}}
                        ]
                    }
                }
            ]
        }

        mock_k8s_api.get_cluster_custom_object.side_effect = [
            {'status': {'id': 'instrumentation-check/metric::123456789'}},
            ApiException(status=404, reason="Not found")
        ]

        # Call the function
        result = await get_applicable_metrics('SERVICE')

        # Assertions
        assert len(result) == 1
        assert {'metricName': 'instrumentation-check', 'metricId': 'instrumentation-check/metric::123456789'} in result

        # Verify the Kubernetes API was called
        mock_k8s_api.list_cluster_custom_object.assert_called_once()
        assert mock_k8s_api.get_cluster_custom_object.call_count == 2

    @pytest.mark.asyncio
    async def test_get_applicable_metrics_exception(self, mock_k8s_api, mock_load_incluster_config):
        """Test getting applicable metrics when an exception occurs"""
        # Mock the Kubernetes API to raise an exception
        mock_load_incluster_config.side_effect = Exception("Test exception")

        # Call the function
        result = await get_applicable_metrics('SERVICE')

        # Assertions
        assert result == []

    def test_metrics_match_identical(self):
        """Test metrics_match with identical metric sets"""
        current_metrics = [
            {'metricName': 'metric1', 'metricId': 'id1'},
            {'metricName': 'metric2', 'metricId': 'id2'}
        ]
        applicable_metrics = [
            {'metricName': 'metric1', 'metricId': 'id1'},
            {'metricName': 'metric2', 'metricId': 'id2'}
        ]

        # Call the function
        result = metrics_match(current_metrics, applicable_metrics)

        # Assertions
        assert result is True

    def test_metrics_match_different_order(self):
        """Test metrics_match with identical metric sets in different order"""
        current_metrics = [
            {'metricName': 'metric1', 'metricId': 'id1'},
            {'metricName': 'metric2', 'metricId': 'id2'}
        ]
        applicable_metrics = [
            {'metricName': 'metric2', 'metricId': 'id2'},
            {'metricName': 'metric1', 'metricId': 'id1'}
        ]

        # Call the function
        result = metrics_match(current_metrics, applicable_metrics)

        # Assertions
        assert result is True

    def test_metrics_match_different_count(self):
        """Test metrics_match with different count of metrics"""
        current_metrics = [
            {'metricName': 'metric1', 'metricId': 'id1'}
        ]
        applicable_metrics = [
            {'metricName': 'metric1', 'metricId': 'id1'},
            {'metricName': 'metric2', 'metricId': 'id2'}
        ]

        # Call the function
        result = metrics_match(current_metrics, applicable_metrics)

        # Assertions
        assert result is False

    def test_metrics_match_different_ids(self):
        """Test metrics_match with same metric names but different IDs"""
        current_metrics = [
            {'metricName': 'metric1', 'metricId': 'old-id1'},
            {'metricName': 'metric2', 'metricId': 'id2'}
        ]
        applicable_metrics = [
            {'metricName': 'metric1', 'metricId': 'new-id1'},
            {'metricName': 'metric2', 'metricId': 'id2'}
        ]

        # Call the function
        result = metrics_match(current_metrics, applicable_metrics)

        # Assertions
        assert result is False

    def test_metrics_match_different_names(self):
        """Test metrics_match with different metric names"""
        current_metrics = [
            {'metricName': 'metric1', 'metricId': 'id1'},
            {'metricName': 'old-metric2', 'metricId': 'id2'}
        ]
        applicable_metrics = [
            {'metricName': 'metric1', 'metricId': 'id1'},
            {'metricName': 'new-metric2', 'metricId': 'id2'}
        ]

        # Call the function
        result = metrics_match(current_metrics, applicable_metrics)

        # Assertions
        assert result is False

    def test_metrics_match_empty_lists(self):
        """Test metrics_match with empty lists"""
        # Call the function
        result = metrics_match([], [])

        # Assertions
        assert result is True

    def test_metrics_match_missing_keys(self):
        """Test metrics_match with metrics missing required keys"""
        current_metrics = [
            {'metricName': 'metric1'},  # Missing metricId
            {'metricId': 'id2'}  # Missing metricName
        ]
        applicable_metrics = [
            {'metricName': 'metric1', 'metricId': 'id1'},
            {'metricName': 'metric2', 'metricId': 'id2'}
        ]

        # Call the function
        result = metrics_match(current_metrics, applicable_metrics)

        # Assertions
        assert result is False