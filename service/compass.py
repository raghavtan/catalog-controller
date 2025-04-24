import requests
import logging
import os
from typing import Dict, Optional, Any

logger = logging.getLogger('compass-client')


class CompassClient:
    _instance = None

    @classmethod
    def get_instance(cls) -> 'CompassClient':
        """Get the singleton instance of CompassClient."""
        if cls._instance is None:
            # Read configuration from environment variables
            base_url = os.environ.get('COMPASS_API_BASE_URL', 'https://api.atlassian.com/compass')
            cloud_id = os.environ.get('COMPASS_CLOUD_ID')
            api_token = os.environ.get('COMPASS_API_TOKEN')

            if not cloud_id or not api_token:
                raise ValueError(
                    "Missing required environment variables: COMPASS_CLOUD_ID, COMPASS_API_TOKEN")

            cls._instance = cls(base_url, cloud_id, api_token)
            logger.info("CompassClient singleton initialized")
        return cls._instance

    def __init__(self, base_url: str, cloud_id: str, api_token: str):
        """Initialize the CompassClient with configuration."""
        self.base_url = base_url
        self.cloud_id = cloud_id
        self.api_token = api_token
        self.headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make an HTTP request to the Compass API."""
        url = f"{self.base_url}/{self.cloud_id}/{endpoint}"

        try:
            if method == 'GET':
                response = self.session.get(url)
            elif method == 'POST':
                response = self.session.post(url, json=data)
            elif method == 'PUT':
                response = self.session.put(url, json=data)
            elif method == 'DELETE':
                response = self.session.delete(url)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {e}")
            raise

    # Metric Operations
    def create_metric(self, metric_data: Dict) -> Dict[str, Any]:
        return self._make_request('POST', 'metrics', data=metric_data)

    def update_metric(self, metric_id: str, metric_data: Dict) -> Dict[str, Any]:
        return self._make_request('PUT', f'metrics/{metric_id}', data=metric_data)

    def delete_metric(self, metric_id: str) -> Dict[str, Any]:
        return self._make_request('DELETE', f'metrics/{metric_id}')

    def get_metric(self, metric_id: str) -> Dict[str, Any]:
        return self._make_request('GET', f'metrics/{metric_id}')

    # Scorecard Operations
    def create_scorecard(self, scorecard_data: Dict) -> Dict[str, Any]:
        return self._make_request('POST', 'scorecards', data=scorecard_data)

    def update_scorecard(self, scorecard_id: str, scorecard_data: Dict) -> Dict[str, Any]:
        return self._make_request('PUT', f'scorecards/{scorecard_id}', data=scorecard_data)

    def delete_scorecard(self, scorecard_id: str) -> Dict[str, Any]:
        return self._make_request('DELETE', f'scorecards/{scorecard_id}')

    def get_scorecard(self, scorecard_id: str) -> Dict[str, Any]:
        return self._make_request('GET', f'scorecards/{scorecard_id}')

    # Component Operations
    def create_component(self, component_data: Dict) -> Dict[str, Any]:
        return self._make_request('POST', 'components', data=component_data)

    def update_component(self, component_id: str, component_data: Dict) -> Dict[str, Any]:
        return self._make_request('PUT', f'components/{component_id}', data=component_data)

    def delete_component(self, component_id: str) -> Dict[str, Any]:
        return self._make_request('DELETE', f'components/{component_id}')

    def get_component(self, component_id: str) -> Dict[str, Any]:
        return self._make_request('GET', f'components/{component_id}')


def get_compass_client() -> CompassClient:
    """Helper function to get the singleton instance of CompassClient."""
    return CompassClient.get_instance()