import os
import sys
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

# Add the service directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Set explicit fixture loop scope
pytest.asyncio_default_fixture_loop_scope = "function"

@pytest.fixture(scope="session")
def event_loop_policy():
    """Create an event loop policy for the test session."""
    return asyncio.DefaultEventLoopPolicy()

@pytest.fixture(autouse=True)
def mock_environment_variables():
    """Mock environment variables for testing"""
    with patch.dict(os.environ, {
        'COMPASS_SERVICE_ENDPOINT': 'test-compass-service',
        'METRIC_EVALUATION_SERVICE_URL': 'test-metric-evaluation-service',
        'CONTROLLER_PREFIX': 'test.catalog.example.com',
        'LOG_LEVEL': 'DEBUG',
        'LOG_FORMAT': '%(asctime)s [%(levelname)s] [%(name)s] - %(message)s'
    }):
        yield

@pytest.fixture(autouse=True)
def mock_kubernetes_config():
    """Mock Kubernetes configuration loading"""
    with patch('kubernetes.config.load_incluster_config'):
        yield

@pytest.fixture(autouse=True)
def mock_httpx_globally():
    """Mock httpx globally to prevent any real HTTP calls"""
    with patch('httpx.AsyncClient') as mock_client:
        # Create a proper async mock
        async_mock = AsyncMock()

        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"id": "test-id"}}
        mock_response.text = "Success"

        # Configure the async mock
        async_mock.get.return_value = mock_response
        async_mock.post.return_value = mock_response
        async_mock.put.return_value = mock_response
        async_mock.delete.return_value = mock_response

        # Setup context manager
        mock_client.return_value.__aenter__.return_value = async_mock
        mock_client.return_value.__aexit__.return_value = AsyncMock(return_value=None)

        yield async_mock

@pytest.fixture
def mock_compass_api():
    """Mock CompassAPI for testing - this will override the global mock when used"""
    mock_instance = AsyncMock()

    # Setup default successful responses
    mock_instance.get_by_name = AsyncMock(return_value={"status_code": 404, "message": "Not found"})
    mock_instance.get_by_id = AsyncMock(return_value={"status_code": 200, "data": {"id": "test-id", "spec": {}}})
    mock_instance.create = AsyncMock(return_value={"status_code": 201, "data": {"id": "test-id"}})
    mock_instance.update = AsyncMock(return_value={"status_code": 200, "data": {"id": "test-id"}})
    mock_instance.delete = AsyncMock(return_value={"status_code": 200})
    mock_instance.has_spec_differences = MagicMock(return_value=False)

    return mock_instance

@pytest.fixture
def mock_k8s_api():
    """Mock Kubernetes CustomObjectsApi for testing"""
    with patch('kubernetes.client.CustomObjectsApi') as mock_api:
        mock_instance = MagicMock()
        mock_api.return_value = mock_instance

        # Default behavior is to return a valid metric
        mock_instance.get_cluster_custom_object.return_value = {
            "metadata": {"name": "test-metric"},
            "status": {"id": "test-metric-id"}
        }
        mock_instance.list_cluster_custom_object.return_value = {"items": []}

        yield mock_instance

@pytest.fixture
def base_metadata():
    """Base Kubernetes metadata for testing"""
    return {
        "name": "test-resource",
        "namespace": "default",
        "uid": "test-uid-12345",
        "resourceVersion": "1",
        "generation": 1,
        "annotations": {"test.com/annotation": "value"},
        "labels": {"app": "test", "env": "test"},
        "finalizers": []
    }

@pytest.fixture
def metric_spec():
    """Test metric specification"""
    return {
        "name": "test-metric",
        "description": "Test metric for unit tests",
        "componentType": "service",
        "cronSchedule": "0 * * * *",
        "facts": ["test.fact"],
        "grading-system": "percentage"
    }

@pytest.fixture
def scorecard_spec():
    """Test scorecard specification"""
    return {
        "name": "test-scorecard",
        "description": "Test scorecard for unit tests",
        "state": "active",
        "componentTypeIds": ["service"],
        "criteria": [
            {
                "hasMetricValue": {
                    "metricName": "test-metric",
                    "operator": "lt",
                    "value": 80,
                    "weight": 1.0
                },
            }
        ]
    }

@pytest.fixture
def component_spec():
    """Test component specification"""
    return {
        "name": "test-component",
        "description": "Test component for unit tests",
        "type": "service",
        "typeId": "SERVICE",
        "labels": {
            "team": "platform",
            "product": "test-product"
        },
        "links": [
            {
                "name": "Documentation",
                "url": "https://example.com/docs"
            }
        ]
    }

@pytest.fixture
def test_request_metric(base_metadata, metric_spec):
    """Create a test MetacontrollerRequest for metrics"""
    from service.models.models import MetacontrollerRequest, ParentResource, KubernetesMetadata

    metadata = KubernetesMetadata(**base_metadata)
    parent = ParentResource(
        apiVersion="catalog.onefootball.com/v1alpha1",
        kind="Metric",
        metadata=metadata,
        spec=metric_spec
    )

    return MetacontrollerRequest(
        controller={"apiVersion": "v1", "kind": "CompositeController"},
        parent=parent,
        children={},
        related={},
        finalizing=False
    )

@pytest.fixture
def test_request_scorecard(base_metadata, scorecard_spec):
    """Create a test MetacontrollerRequest for scorecards"""
    from service.models.models import MetacontrollerRequest, ParentResource, KubernetesMetadata

    metadata = KubernetesMetadata(**base_metadata)
    parent = ParentResource(
        apiVersion="catalog.onefootball.com/v1alpha1",
        kind="Scorecard",
        metadata=metadata,
        spec=scorecard_spec
    )

    return MetacontrollerRequest(
        controller={"apiVersion": "v1", "kind": "CompositeController"},
        parent=parent,
        children={},
        related={},
        finalizing=False
    )

@pytest.fixture
def test_request_component(base_metadata, component_spec):
    """Create a test MetacontrollerRequest for components"""
    from service.models.models import MetacontrollerRequest, ParentResource, KubernetesMetadata

    metadata = KubernetesMetadata(**base_metadata)
    parent = ParentResource(
        apiVersion="catalog.onefootball.com/v1alpha1",
        kind="Component",
        metadata=metadata,
        spec=component_spec
    )

    return MetacontrollerRequest(
        controller={"apiVersion": "v1", "kind": "CompositeController"},
        parent=parent,
        children={},
        related={},
        finalizing=False
    )

@pytest.fixture
def test_finalize_request(base_metadata, metric_spec):
    """Create a test finalize MetacontrollerRequest"""
    from service.models.models import MetacontrollerRequest, ParentResource, KubernetesMetadata

    metadata = KubernetesMetadata(**base_metadata)
    parent = ParentResource(
        apiVersion="catalog.onefootball.com/v1alpha1",
        kind="Metric",
        metadata=metadata,
        spec=metric_spec,
        status={"id": "test-compass-id"}
    )

    return MetacontrollerRequest(
        controller={"apiVersion": "v1", "kind": "CompositeController"},
        parent=parent,
        children={},
        related={},
        finalizing=True
    )