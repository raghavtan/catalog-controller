"""Unit tests for cleanup handler with proper mocking."""

import pytest
from unittest.mock import patch, AsyncMock

from service.handlers.cleanup import finalize_resource

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_finalize_resource_success(test_finalize_request):
    """Test successful resource finalization."""
    with patch('service.handlers.cleanup.CompassAPI') as mock_compass_class:
        # Configure mock
        mock_compass = AsyncMock()
        mock_compass.delete.return_value = {"status_code": 200}
        mock_compass_class.return_value = mock_compass

        # Call function
        response, status_code = await finalize_resource(test_finalize_request)

        # Verify response
        assert status_code == 200
        assert response["finalized"] is True

        # Verify API call
        mock_compass.delete.assert_called_once_with("metric", "test-compass-id")


@pytest.mark.asyncio
async def test_finalize_resource_not_found(test_finalize_request):
    """Test finalization when resource is not found (already deleted)."""
    with patch('service.handlers.cleanup.CompassAPI') as mock_compass_class:
        # Configure mock
        mock_compass = AsyncMock()
        mock_compass.delete.return_value = {"status_code": 404, "message": "Not found"}
        mock_compass_class.return_value = mock_compass

        # Call function
        response, status_code = await finalize_resource(test_finalize_request)

        # Verify response - should still be considered successful
        assert status_code == 200
        assert response["finalized"] is True


@pytest.mark.asyncio
async def test_finalize_resource_no_id(test_request_metric):
    """Test finalization when no Compass ID exists."""
    # Call function
    response, status_code = await finalize_resource(test_request_metric)

    # Verify response
    assert status_code == 200
    assert response["finalized"] is True


@pytest.mark.asyncio
async def test_finalize_resource_api_error(test_finalize_request):
    """Test finalization when API returns an error."""
    with patch('service.handlers.cleanup.CompassAPI') as mock_compass_class:
        # Configure mock
        mock_compass = AsyncMock()
        mock_compass.delete.return_value = {"status_code": 500, "message": "Internal server error"}
        mock_compass_class.return_value = mock_compass

        # Call function
        response, status_code = await finalize_resource(test_finalize_request)

        # Verify response
        assert status_code == 500
        assert response["finalized"] is False


@pytest.mark.asyncio
async def test_finalize_resource_exception(test_finalize_request):
    """Test finalization when an exception occurs."""
    with patch('service.handlers.cleanup.CompassAPI') as mock_compass_class:
        # Configure mock
        mock_compass = AsyncMock()
        mock_compass.delete.side_effect = Exception("Test exception")
        mock_compass_class.return_value = mock_compass

        # Call function
        response, status_code = await finalize_resource(test_finalize_request)

        # Verify response
        assert status_code == 500
        assert response["finalized"] is False
        assert "error" in response["status"]
        assert "Test exception" in response["status"]["error"]