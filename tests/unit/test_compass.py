"""Unit tests for CompassAPI utility."""

import pytest
import os
import httpx
from unittest.mock import patch, AsyncMock, MagicMock

from service.utils.compass import CompassAPI

pytestmark = pytest.mark.unit


@pytest.fixture
def compass_api():
    """Return a CompassAPI instance."""
    return CompassAPI()


def test_compass_api_init():
    """Test CompassAPI initialization."""
    # Test with custom environment variables
    with patch.dict(os.environ, {"COMPASS_SERVICE_ENDPOINT": "compass-service.compass-service.svc.cluster.local"}):
        api = CompassAPI()
        assert api.host == "compass-service.compass-service.svc.cluster.local"
        assert api.base_url == "http://compass-service.compass-service.svc.cluster.local/api/v1"

    # Test with custom environment variables
    with patch.dict(os.environ, {"COMPASS_SERVICE_ENDPOINT": "custom-compass-service"}):
        api = CompassAPI()
        assert api.host == "custom-compass-service"
        assert api.base_url == "http://custom-compass-service/api/v1"


@pytest.mark.asyncio
async def test_get_by_id_success(compass_api):
    """Test getting a resource by ID successfully."""
    # Configure mock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "test-id", "spec": {"name": "test-resource"}}

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        # Call function
        result = await compass_api.get_by_id("metric", "test-id")

        # Verify result
        assert result["status_code"] == 200
        assert result["id"] == "test-id"
        assert result["spec"]["name"] == "test-resource"

        # Verify API call
        mock_instance.get.assert_called_once()
        call_args = mock_instance.get.call_args[0][0]
        assert "metrics/test-id" in call_args


@pytest.mark.asyncio
async def test_get_by_id_not_found(compass_api):
    """Test getting a resource by ID that doesn't exist."""
    # Configure mock
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"message": "Resource not found"}

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        # Call function
        result = await compass_api.get_by_id("metric", "nonexistent-id")

        # Verify result
        assert result["status_code"] == 404
        assert result["message"] == "metric not found"


@pytest.mark.asyncio
async def test_get_by_id_error(compass_api):
    """Test getting a resource by ID with an error."""
    # Configure mock to raise an exception
    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock(status_code=500, text="Internal server error")
        )
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        # Call function
        result = await compass_api.get_by_id("metric", "test-id")

        # Verify result
        assert result["status_code"] == 500
        assert "message" in result


@pytest.mark.asyncio
async def test_get_by_name_success(compass_api):
    """Test getting a resource by name successfully."""
    # Configure mock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "test-id", "spec": {"name": "test-resource"}}

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        # Call function
        result = await compass_api.get_by_name("metric", "test-resource")

        # Verify result
        assert result["status_code"] == 200
        assert result["id"] == "test-id"
        assert result["spec"]["name"] == "test-resource"

        # Verify API call
        mock_instance.get.assert_called_once()
        call_args = mock_instance.get.call_args[0][0]
        assert "metrics/by-name/test-resource" in call_args


@pytest.mark.asyncio
async def test_get_by_name_not_found(compass_api):
    """Test getting a resource by name that doesn't exist."""
    # Configure mock
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"message": "Resource not found"}

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        # Call function
        result = await compass_api.get_by_name("metric", "nonexistent-resource")

        # Verify result
        assert result["status_code"] == 404
        assert "message" in result


@pytest.mark.asyncio
async def test_create_success(compass_api):
    """Test creating a resource successfully."""
    # Configure mock
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": "new-resource-id", "spec": {"name": "new-resource"}}

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        # Call function
        resource_data = {
            "metadata": {"name": "new-resource", "namespace": "default"},
            "spec": {
                "name": "new-resource",
                "description": "New test resource",
                "facts": ["test.fact"],
                "evaluateOnDeploy": True,
                "grading-system": "percentage"
            }
        }

        result = await compass_api.create("metric", resource_data)

        # Verify result
        assert result["status_code"] == 201
        assert result["id"] == "new-resource-id"

        # Verify API call
        mock_instance.post.assert_called_once()

        # Verify that certain fields were stripped from the data sent to the API
        post_data = mock_instance.post.call_args[1]["json"]
        assert "facts" not in post_data.get("spec", {})
        assert "evaluateOnDeploy" not in post_data.get("spec", {})
        assert "grading-system" not in post_data.get("spec", {})
        assert post_data["metadata"] == {"name": "new-resource"}


@pytest.mark.asyncio
async def test_create_error(compass_api):
    """Test creating a resource with an error."""
    # Configure mock
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad request"

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=mock_response
        )
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        # Call function
        resource_data = {
            "metadata": {"name": "new-resource"},
            "spec": {"name": "new-resource"}
        }

        result = await compass_api.create("metric", resource_data)

        # Verify result
        assert result["status_code"] == 400
        assert "message" in result


@pytest.mark.asyncio
async def test_create_exception(compass_api):
    """Test creating a resource with an exception."""
    # Configure mock to raise an exception
    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post.side_effect = Exception("Test exception")
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        # Call function
        resource_data = {
            "metadata": {"name": "new-resource"},
            "spec": {"name": "new-resource"}
        }

        result = await compass_api.create("metric", resource_data)

        # Verify result
        assert result["status_code"] == 500
        assert "message" in result


@pytest.mark.asyncio
async def test_update_success(compass_api):
    """Test updating a resource successfully."""
    # Configure mock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "update-resource-id", "spec": {"name": "update-resource"}}

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.put.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        # Call function
        resource_data = {
            "metadata": {"name": "update-resource", "namespace": "default"},
            "spec": {
                "name": "update-resource",
                "description": "Updated test resource",
                "facts": ["test.fact"],
                "evaluateOnDeploy": True,
                "grading-system": "percentage"
            },
            "status": {"id": "update-resource-id"}
        }

        result = await compass_api.update("metric", "update-resource-id", resource_data)

        # Verify result
        assert result["status_code"] == 200
        assert result["id"] == "update-resource-id"

        # Verify API call
        mock_instance.put.assert_called_once()

        # Verify that certain fields were stripped from the data sent to the API
        put_data = mock_instance.put.call_args[1]["json"]
        assert "facts" not in put_data.get("spec", {})
        assert "evaluateOnDeploy" not in put_data.get("spec", {})
        assert "grading-system" not in put_data.get("spec", {})
        assert "status" not in put_data
        assert put_data["metadata"] == {"name": "update-resource"}


@pytest.mark.asyncio
async def test_update_error(compass_api):
    """Test updating a resource with an error."""
    # Configure mock
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad request"

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.put.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=mock_response
        )
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        # Call function
        resource_data = {
            "metadata": {"name": "update-resource"},
            "spec": {"name": "update-resource"}
        }

        result = await compass_api.update("metric", "update-resource-id", resource_data)

        # Verify result
        assert result["status_code"] == 400
        assert "message" in result


@pytest.mark.asyncio
async def test_delete_success(compass_api):
    """Test deleting a resource successfully."""
    # Configure mock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.delete.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        # Call function
        result = await compass_api.delete("metric", "delete-resource-id")

        # Verify result
        assert result["status_code"] == 200

        # Verify API call
        mock_instance.delete.assert_called_once()
        call_args = mock_instance.delete.call_args[0][0]
        assert "metrics/delete-resource-id" in call_args


@pytest.mark.asyncio
async def test_delete_not_found(compass_api):
    """Test deleting a resource that doesn't exist."""
    # Configure mock
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"message": "Resource not found"}

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.delete.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        # Call function
        result = await compass_api.delete("metric", "nonexistent-id")

        # Verify result
        assert result["status_code"] == 404


@pytest.mark.asyncio
async def test_delete_error(compass_api):
    """Test deleting a resource with an error."""
    # Configure mock to raise an exception
    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.delete.side_effect = Exception("Test exception")
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_client.return_value.__aexit__.return_value = None

        # Call function
        result = await compass_api.delete("metric", "delete-resource-id")

        # Verify result
        assert result["status_code"] == 500
        assert "message" in result


def test_has_spec_differences_true():
    """Test detecting spec differences."""
    # Create resources with differences
    k8s_resource = {
        "spec": {
            "name": "test-resource",
            "description": "New description"
        }
    }

    compass_resource = {
        "spec": {
            "name": "test-resource",
            "description": "Old description"
        }
    }

    # Call function
    api = CompassAPI()
    result = api.has_spec_differences(k8s_resource, compass_resource)

    # Verify result
    assert result is True


def test_has_spec_differences_false():
    """Test detecting no spec differences."""
    # Create resources without differences
    k8s_resource = {
        "spec": {
            "name": "test-resource",
            "description": "Same description"
        }
    }

    compass_resource = {
        "spec": {
            "name": "test-resource",
            "description": "Same description"
        }
    }

    # Call function
    api = CompassAPI()
    result = api.has_spec_differences(k8s_resource, compass_resource)

    # Verify result
    assert result is False


def test_has_spec_differences_exception():
    """Test spec differences with an exception."""
    # Call function with data that would cause an exception
    k8s_resource = None
    compass_resource = {"spec": {"name": "test-resource"}}

    # Call function
    api = CompassAPI()
    result = api.has_spec_differences(k8s_resource, compass_resource)

    # Should return True on exception to trigger an update
    assert result is True