from service.utils.log import get_logger
import os

import httpx

logger = get_logger("CompassAPI")


class CompassAPI:
    def __init__(self):
        self.host = os.getenv("COMPASS_SERVICE_ENDPOINT", "compass-service.compass.svc.cluster.local")
        self.base_url = f"http://{self.host}"

    async def call(self, operation: str, resource_kind: str, resource_data: dict) -> dict:

        logger.debug(f"Calling Compass API: {operation} {resource_kind} for {resource_data['metadata']['name']}")
        headers = {"Content-Type": "application/json","Accept": "application/json"}
        request_url = f"{self.base_url}/{resource_kind}/{resource_data['status']['id']}"

        try:
            async with httpx.AsyncClient() as client:
                if operation == "delete":
                    response = await client.delete(request_url)
                elif operation == "create":
                    response = await client.post(f"{self.base_url}/{resource_kind}", data=resource_data, headers=headers)
                elif operation == "update":
                    response = await client.put(request_url, data=resource_data, headers=headers)
                elif operation == "get":
                    response = await client.get(request_url)

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")

        finally:
            await client.aclose()
            return response.json()

    async def dummy_call(self, operation: str, resource_kind: str, resource_data: dict) -> dict:
        if resource_kind != "component":
            resource_name = resource_data['metadata']['name']
            logger.debug(f"Dummy call to {operation} {resource_kind} for {resource_name}")
        else:
            component_data = resource_data.get('component', {})
            resource_name = component_data.get('metadata', {}).get('name', 'unknown')
            logger.debug(f"Dummy call to {operation} {resource_kind} for {resource_name}")

        if operation == "delete":
            return {
                "status_code": 200,
                "message": "Resource deleted successfully",
                "success": True
            }

        elif operation == "create":
            if resource_kind == "component":
                component_data = resource_data.get('component', {})
                metrics_data = resource_data.get('metrics', [])
                component_name = component_data.get('metadata', {}).get('name', 'unknown')

                metric_sources = []
                for metric in metrics_data:
                    metric_name = metric.get('metricName', 'unknown-metric')
                    metric_id = metric.get('metricId', 'unknown-metric-id')

                    metric_sources.append({
                        "metricName": metric_name,
                        "metricId": metric_id,
                        "metricSourceId": f"{component_name}-{metric_name}/metricSource:::123456789"
                    })

                return {
                    "status_code": 201,
                    "message": "Component with metrics created successfully",
                    "success": True,
                    "id": f"{component_name}/component::123456789",
                    "metricSources": metric_sources
                }
            else:
                return {
                    "status_code": 201,
                    "message": "Resource created successfully",
                    "success": True,
                    "id": f"{resource_data['metadata']['name']}/{resource_kind}::123456789"
                }

        elif operation == "update":
            if resource_kind == "component":
                return {
                    "status_code": 200,
                    "message": "Resource updated successfully",
                    "success": True,
                    "id": f"{resource_name}/component::123456789"
                }
            else:
                return {
                    "status_code": 200,
                    "message": "Resource updated",
                    "success": True
                }

        elif operation == "get":
            if resource_kind == "component":
                metric_associations = resource_data.get('status', {}).get('metricAssociation', [])

                return {
                    "status_code": 200,
                    "message": "Resource fetched successfully",
                    "success": True,
                    "id": f"{resource_name}/component::123456789",
                    "metricAssociation": metric_associations
                }
            else:
                return {
                    "status_code": 200,
                    "message": "Resource fetched successfully",
                    "success": True,
                    "id": f"{resource_data['metadata']['name']}/{resource_kind}::123456789"
                }

        else:
            logger.warning(f"Unsupported operation: {operation}")
            return {
                "status_code": 400,
                "message": f"Unsupported operation: {operation}",
                "success": False
            }
