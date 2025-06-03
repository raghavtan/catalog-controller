from service.utils.log import get_logger
import os
import json
import httpx
import urllib.parse

logger = get_logger("CompassAPI")


class CompassAPI:
    def __init__(self):
        self.host = os.getenv("COMPASS_SERVICE_ENDPOINT", "compass-service.compass-service.svc.cluster.local")
        self.base_url = f"http://{self.host}/api/v1"

    async def get_by_id(self, resource_kind: str, resource_id: str) -> dict:
        """Get resource by Compass ID"""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        try:
            async with httpx.AsyncClient() as client:
                # request URL example
                # http://compass-service.compass-service.svc.cluster.local/api/v1/metrics/ari:cloud:compass:fca6a80f-888b-4079-82e6-3c2f61c788e2:metric-definition/4d010f50-96c4-48c0-bab5-a3dd5112b464/295e70fa-9359-4a0f-9188-6f7b6a0dbd7e
                encoded_id = urllib.parse.quote(resource_id, safe='')
                request_url = f"{self.base_url}/{resource_kind}s/{encoded_id}"
                response = await client.get(request_url, headers=headers)

                if response.status_code == 200:
                    logger.debug(f"[GetByID]Successfully retrieved {resource_kind} with ID {resource_id} {response.json()}")
                    return {"status_code": 200, **response.json()}
                elif response.status_code == 404:
                    return {"status_code": 404, "message": f"{resource_kind} not found"}
                else:
                    response.raise_for_status()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            return {"status_code": e.response.status_code, "message": e.response.text}
        except Exception as e:
            logger.error(f"Error getting {resource_kind} by ID {resource_id}: {str(e)}")
            return {"status_code": 500, "message": str(e)}

    async def get_by_name(self, resource_kind: str, resource_name: str) -> dict:
        """Get resource by name - for import functionality"""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        request_url = f"{self.base_url}/{resource_kind}s/by-name/{resource_name}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(request_url, headers=headers)

                if response.status_code == 200:
                    logger.debug(f"[GetByName] Successfully retrieved {resource_kind} with name {resource_name} {response.json()}")
                    return {"status_code": 200, **response.json()}
                elif response.status_code == 404:
                    return {"status_code": 404, "message": f"{resource_kind} with name {resource_name} not found"}
                else:
                    response.raise_for_status()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            return {"status_code": e.response.status_code, "message": e.response.text}
        except Exception as e:
            logger.error(f"Error getting {resource_kind} by name {resource_name}: {str(e)}")
            return {"status_code": 500, "message": str(e)}

    async def create(self, resource_kind: str, resource_data: dict) -> dict:
        """Create new resource"""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        request_url = f"{self.base_url}/{resource_kind}s"

        if 'metadata' in resource_data:
            resource_data['metadata'] = {k: v for k, v in resource_data['metadata'].items() if k not in [
                'annotations', 'creationTimestamp', 'finalizers', 'deletionTimestamp',
                'generation', 'resourceVersion', 'uid', 'managedFields', 'namespace'
            ]}

        if isinstance(resource_data, dict):
            try:
                resource_data = json.loads(json.dumps(resource_data, default=str))
            except TypeError as e:
                logger.error(f"Failed to serialize resource data: {str(e)}")
                return {"status_code": 500, "message": "Invalid resource data format"}


        try:
            logger.debug(f"[Create] Attempting to create {resource_kind} with data: {resource_data}")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    request_url,
                    json=resource_data,  # Use json parameter instead of data
                    headers=headers
                )

                if response.status_code == 201:
                    logger.debug(f"[Create] Successfully created {resource_kind} {response.json()}")
                    return {"status_code": 201, **response.json()}
                else:
                    response.raise_for_status()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            return {"status_code": e.response.status_code, "message": e.response.text}
        except Exception as e:
            logger.error(f"Error creating {resource_kind}: {str(e)}")
            return {"status_code": 500, "message": str(e)}

    async def update(self, resource_kind: str, resource_id: str, resource_data: dict) -> dict:
        """Update existing resource"""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        encoded_id = urllib.parse.quote(resource_id, safe='')
        request_url = f"{self.base_url}/{resource_kind}s/{encoded_id}"

        if 'metadata' in resource_data:
            resource_data['metadata'] = {k: v for k, v in resource_data['metadata'].items() if k not in [
                'annotations', 'creationTimestamp', 'finalizers', 'deletionTimestamp',
                'generation', 'resourceVersion', 'uid', 'managedFields', 'namespace'
            ]}

        if isinstance(resource_data, dict):
            try:
                resource_data = json.loads(json.dumps(resource_data, default=str))
            except TypeError as e:
                logger.error(f"Failed to serialize resource data: {str(e)}")
                return {"status_code": 500, "message": "Invalid resource data format"}

        try:
            logger.debug(f"[Update] Attempting to update {resource_kind} {resource_id} with data: {resource_data}")
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    request_url,
                    json=resource_data,  # Use json parameter instead of data
                    headers=headers
                )
                if response.status_code == 200:
                    logger.debug(f"[Update] Successfully updated {resource_kind} {resource_id} {response.json()}")
                    return {"status_code": 200, **response.json()}
                else:
                    response.raise_for_status()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            return {"status_code": e.response.status_code, "message": e.response.text}
        except Exception as e:
            logger.error(f"Error updating {resource_kind} {resource_id}: {str(e)}")
            return {"status_code": 500, "message": str(e)}

    async def delete(self, resource_kind: str, resource_id: str) -> dict:
        """Delete resource"""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        encoded_id = urllib.parse.quote(resource_id, safe='')
        request_url = f"{self.base_url}/{resource_kind}s/{encoded_id}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(request_url, headers=headers)
                logger.debug(f"[Delete] Attempting to delete {resource_kind} {resource_id} response: {response.json()}")
                return {"status_code": response.status_code}

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            return {"status_code": e.response.status_code, "message": e.response.text}
        except Exception as e:
            logger.error(f"Error deleting {resource_kind} {resource_id}: {str(e)}")
            return {"status_code": 500, "message": str(e)}

    def has_spec_differences(self, k8s_resource: dict, compass_resource: dict) -> bool:
        """Compare K8s resource spec with Compass resource to detect differences"""
        try:
            k8s_spec = k8s_resource.get('spec', {})
            compass_spec = compass_resource.get('spec', {})

            return k8s_spec != compass_spec

        except Exception as e:
            logger.error(f"Error comparing specs: {str(e)}")
            return True