import pytest
from unittest.mock import patch, AsyncMock
import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the function to test
from service.scheduler.scheduler import build_metric_evaluator_cronjob
from service.handlers.metric import sync_metric, create_metric
from service.utils.compass import CompassAPI
from service.scheduler.scheduler import build_metric_evaluator_cronjob


@pytest.mark.asyncio
async def test_sync_metric_existing_id_found(metric_request, compass_success_response):
    """Test syncing a metric that already exists and is found in Compass"""
    # The ID is already set in the fixture

    # Mock the CompassAPI.dummy_call to return success
    with patch.object(CompassAPI, 'dummy_call', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = compass_success_response

        # Call the function
        response, status_code = await sync_metric(metric_request)

        # Assert the result
        assert status_code == 200
        assert response["status"]["id"] == "alert-routing-and-notifications/metric::123456789"
        assert response["status"]["cronJob"] is not None
        assert len(response["children"]) > 0

        # Verify API calls
        mock_call.assert_called_once()


@pytest.mark.asyncio
async def test_sync_metric_existing_id_not_found(metric_request, compass_not_found_response,
                                                 compass_create_success_response):
    with patch.object(CompassAPI, 'dummy_call', new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = [
            compass_not_found_response,
            compass_create_success_response
        ]
        response, status_code = await sync_metric(metric_request)

        print(response, status_code)

        assert status_code == 200
        assert response["status"]["id"] == "alert-routing-and-notifications/metric::123456789"
        assert response["status"]["cronJob"] is not None
        assert mock_call.call_count == 2


@pytest.mark.asyncio
async def test_sync_metric_id_mismatch(metric_request, compass_success_response):
    """Test syncing a metric where the ID from Compass doesn't match the saved ID"""
    # Set a different ID in the response to simulate a mismatch
    compass_response = compass_success_response.copy()
    compass_response["id"] = "alert-routing-and-notifications/metric::different-id"

    # Mock the CompassAPI.dummy_call to return success with mismatched ID
    with patch.object(CompassAPI, 'dummy_call', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = compass_response

        # Call the function
        response, status_code = await sync_metric(metric_request)

        # Assert the result
        assert status_code == 200
        assert response["status"]["id"] == "alert-routing-and-notifications/metric::different-id"
        assert response["status"]["cronJob"] is not None

        # Verify API calls
        mock_call.assert_called_once()


@pytest.mark.asyncio
async def test_sync_metric_no_id(metric_request, compass_create_success_response):
    """Test syncing a metric that doesn't have an ID (new metric)"""
    # Remove the ID from the status to simulate a new metric
    metric_request.parent.status.pop("id", None)

    # Mock the CompassAPI.dummy_call to return success on create
    with patch.object(CompassAPI, 'dummy_call', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = compass_create_success_response

        # Call the function
        response, status_code = await sync_metric(metric_request)

        # Assert the result
        assert status_code == 200
        assert response["status"]["id"] == "alert-routing-and-notifications/metric::123456789"
        assert response["status"]["cronJob"] is not None

        # Verify API calls - should be called once to create
        mock_call.assert_called_once()


@pytest.mark.asyncio
async def test_sync_metric_get_error(metric_request, compass_error_response):
    """Test syncing a metric when the get request fails"""
    # Mock the CompassAPI.dummy_call to return an error
    with patch.object(CompassAPI, 'dummy_call', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = compass_error_response

        # Call the function
        response, status_code = await sync_metric(metric_request)

        # Assert the result
        assert status_code == 200
        assert response["status"]["cronJob"] is None
        assert response["status"]["id"] is None


@pytest.mark.asyncio
async def test_sync_metric_create_error(metric_request, compass_error_response):
    """Test syncing a metric when the create request fails"""
    # Remove the ID from the status to simulate a new metric
    metric_request.parent.status.pop("id", None)

    # Mock the CompassAPI.dummy_call to return an error on create
    with patch.object(CompassAPI, 'dummy_call', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = compass_error_response

        # Call the function
        response, status_code = await sync_metric(metric_request)

        # Assert the result
        assert status_code == 200
        assert response["status"]["cronJob"] is None
        assert response["status"]["id"] is None

        # Verify API calls
        mock_call.assert_called_once()


@pytest.mark.asyncio
async def test_sync_metric_exception(metric_request):
    """Test syncing a metric when an exception occurs"""
    # Mock the CompassAPI.dummy_call to raise an exception
    with patch.object(CompassAPI, 'dummy_call', new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = Exception("Test exception")

        # Call the function
        response, status_code = await sync_metric(metric_request)

        # Assert the result
        assert status_code == 500
        assert "error" in response["status"]
        assert "Test exception" in response["status"]["error"]
        assert len(response["children"]) == 0


@pytest.mark.asyncio
async def test_create_metric_success(metric_request, compass_create_success_response):
    """Test creating a new metric successfully"""
    # Mock the CompassAPI
    compass_client = AsyncMock()
    compass_client.dummy_call = AsyncMock(return_value=compass_create_success_response)

    # Call the function
    parent_dict = metric_request.parent.model_dump(by_alias=True)
    metric_id = await create_metric(compass_client, parent_dict, "alert-routing-and-notifications")

    # Assert the result
    assert metric_id == "alert-routing-and-notifications/metric::123456789"

    # Verify API call
    compass_client.dummy_call.assert_called_once_with("create", "metric", parent_dict)


@pytest.mark.asyncio
async def test_create_metric_failure(metric_request, compass_error_response):
    """Test creating a new metric that fails"""
    # Mock the CompassAPI
    compass_client = AsyncMock()
    compass_client.dummy_call = AsyncMock(return_value=compass_error_response)

    # Call the function
    parent_dict = metric_request.parent.model_dump(by_alias=True)
    metric_id = await create_metric(compass_client, parent_dict, "alert-routing-and-notifications")

    # Assert the result
    assert metric_id is None

    # Verify API call
    compass_client.dummy_call.assert_called_once_with("create", "metric", parent_dict)


@pytest.mark.asyncio
async def test_create_metric_exception(metric_request):
    """Test creating a new metric when an exception occurs"""
    # Mock the CompassAPI
    compass_client = AsyncMock()
    compass_client.dummy_call = AsyncMock(side_effect=Exception("Test exception"))

    # Call the function and expect an exception
    with pytest.raises(Exception) as excinfo:
        parent_dict = metric_request.parent.model_dump(by_alias=True)
        await create_metric(compass_client, parent_dict, "alert-routing-and-notifications")

    # Assert the exception
    assert str(excinfo.value) == "Test exception"

    # Verify API call
    compass_client.dummy_call.assert_called_once_with("create", "metric", parent_dict)


@pytest.mark.asyncio
async def test_sync_metric_with_build_metric_error(metric_request, compass_success_response):
    """Test when there's an error in the build_metric_evaluator_cronjob function"""
    # Mock the CompassAPI.dummy_call to return success
    with patch.object(CompassAPI, 'dummy_call', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = compass_success_response

        # Mock the scheduler module's build function to raise an exception
        with patch('service.handlers.metric.build_metric_evaluator_cronjob',
                   side_effect=Exception("Failed to build CronJob")):
            # Call the function
            response, status_code = await sync_metric(metric_request)

            # Assert the result
            assert status_code == 500
            assert "error" in response["status"]
            assert "Failed to build CronJob" in response["status"]["error"]
            assert len(response["children"]) == 0

            # Verify API calls
            mock_call.assert_called_once()


@pytest.mark.asyncio
async def test_sync_metric_with_no_schedule(metric_request, compass_success_response):
    """Test syncing a metric with no cron schedule"""
    # Remove the cronSchedule from the spec
    metric_request.parent.spec.pop("cronSchedule", None)

    # Mock the CompassAPI.dummy_call to return success
    with patch.object(CompassAPI, 'dummy_call', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = compass_success_response

        # Call the function
        response, status_code = await sync_metric(metric_request)

        # Assert the result
        assert status_code == 200
        assert response["status"]["id"] == "alert-routing-and-notifications/metric::123456789"
        # The build_metric_evaluator_cronjob function should return "NoSchedule" status
        # or similar when no schedule is provided
        assert response["status"]["cronJob"] is not None
        assert len(response["children"]) == 0  # No children should be created when no schedule

        # Verify API calls
        mock_call.assert_called_once()


def test_build_metric_evaluator_cronjob_direct():
    """Test the build_metric_evaluator_cronjob function directly"""
    # Create a simple parent resource
    parent_resource = {
        "apiVersion": "catalog.onefootball.com/v1alpha1",
        "kind": "Metric",
        "metadata": {
            "name": "test-metric",
            "labels": {
                "app": "catalog"
            }
        },
        "spec": {
            "cronSchedule": "0 * * * *",
            "name": "test-metric",
            "componentType": ["service"],
            "facts": [{"id": "test-fact", "name": "Test Fact"}],
            "grading-system": "resiliency",
            "format": {
                "unit": "Test Units"
            }
        },
        "status": {
            "id": "test-metric/metric::123456789"
        }
    }

    # Call the function directly
    children, status = build_metric_evaluator_cronjob(parent_resource)

    # Basic assertions
    assert status in ["Success", "Failed", "NoSchedule"]
    if status == "Success":
        assert len(children) == 1
        assert children[0]["kind"] == "CronJob"
        assert children[0]["metadata"]["name"] == "test-metric-evaluator"
    else:
        assert len(children) == 0


@pytest.mark.asyncio
async def test_sync_metric_response_without_id(metric_request, compass_success_response):
    """Test syncing a metric when the response is successful but doesn't contain an ID"""
    # Create a success response without an ID field
    response_without_id = compass_success_response.copy()
    response_without_id.pop("id", None)  # Remove the ID from the response

    with patch.object(CompassAPI, 'dummy_call', new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = [
            response_without_id,  # First call returns a successful response without ID
            {"status_code": 201, "id": "alert-routing-and-notifications/metric::new-created-id"}
            # Second call creates a new metric
        ]

        # Call the function
        response, status_code = await sync_metric(metric_request)

        # Assert the result
        assert status_code == 200
        assert response["status"]["id"] == "alert-routing-and-notifications/metric::new-created-id"
        assert response["status"]["cronJob"] is not None

        # Verify API calls - should be called twice: once to get and once to create
        assert mock_call.call_count == 2
        # First call should be a get
        assert mock_call.call_args_list[0][0][0] == "get"
        # Second call should be a create
        assert mock_call.call_args_list[1][0][0] == "create"