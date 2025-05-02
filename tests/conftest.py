import json
import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from service.models.models import MetacontrollerRequest
from service.utils.compass import CompassAPI


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory"""
    return os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture
def load_json_fixture():
    """Function to load a JSON fixture file"""

    def _load(fixture_name):
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', fixture_name)
        with open(fixture_path, 'r') as f:
            return json.load(f)

    return _load


@pytest.fixture
def sync_request_metric(load_json_fixture):
    """Load the sync.request.metric.json fixture"""
    return load_json_fixture('sync.request.metric.json')


@pytest.fixture
def metric_request(sync_request_metric):
    """Create a MetacontrollerRequest from the sync.request.metric.json fixture"""
    return MetacontrollerRequest(**sync_request_metric)


@pytest.fixture
def mock_compass_api():
    """Return a mocked CompassAPI instance"""
    mock_api = AsyncMock(spec=CompassAPI)
    return mock_api


@pytest.fixture
def compass_success_response():
    """Return a successful response from Compass API"""
    return {
        "status_code": 200,
        "message": "Resource fetched successfully",
        "success": True,
        "id": "alert-routing-and-notifications/metric::123456789"
    }


@pytest.fixture
def compass_not_found_response():
    """Return a not found response from Compass API"""
    return {
        "status_code": 404,
        "message": "Resource not found",
        "success": False
    }


@pytest.fixture
def compass_create_success_response():
    """Return a successful create response from Compass API"""
    return {
        "status_code": 201,
        "message": "Resource created successfully",
        "success": True,
        "id": "alert-routing-and-notifications/metric::123456789"
    }


@pytest.fixture
def compass_error_response():
    """Return an error response from Compass API"""
    return {
        "status_code": 500,
        "message": "Internal server error",
        "success": False
    }
