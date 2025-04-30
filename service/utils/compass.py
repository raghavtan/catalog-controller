import os
import httpx
import logging
import json
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SyncHandler")


class CompassAPI:
    def __init__(self):
        self.host = os.getenv("COMPASS_SERVICE_ENDPOINT", "compass-service.compass.svc.cluster.local")
        self.base_url = f"http://{self.host}"

    async def call(self, operation: str,  resource_kind: str, resource_data: dict) -> dict:

        logger.info(f"Calling Compass API: {operation} {resource_kind} for {resource_data['metadata']['name']}")

        try:
            async with httpx.AsyncClient() as client:
                if operation == "delete":
                    request_url = f"{self.base_url}/{resource_kind}/{resource_data['status']['id']}"
                    response = await client.delete(request_url)
                elif operation == "create":
                    request_url = f"{self.base_url}/{resource_kind}"
                    request_data = json.dumps(resource_data)
                    headers = {
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                    response = await client.post(request_url, data=request_data, headers=headers)
                elif operation == "update":
                    request_url = f"{self.base_url}/{resource_kind}/{resource_data['status']['id']}"
                    request_data = json.dumps(resource_data)
                    headers = {
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                    response = await client.put(request_url, data=request_data, headers=headers)
                elif operation == "get":
                    request_url = f"{self.base_url}/{resource_kind}/{resource_data['status']['id']}"
                    response = await client.get(request_url)

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")

        finally:
            await client.aclose()
            return response.json()

    async def dummy_call(self, operation: str, resource_kind: str, resource_data: dict) -> dict:
        logger.info(f"Dummy call to {operation} {resource_kind}  for {resource_data['metadata']['name']}")

        if operation == "delete":
            return {"status_code": 200,
                    "message": "Resource deleted successfully",
                    "success": True}
        elif operation == "create":
            return {"status_code": 201,
                    "message": "Resource created successfully",
                    "success": True,
                    "id": f"compass-{resource_kind}-{resource_data['metadata']['name']}-id" }
        elif operation == "update":
            return {"status_code": 200,
                    "message": "Resource updated successfully",
                    "success": True}
        elif operation == "get":
            return {"status_code": 200,
                    "message": "Resource fetched successfully",
                    "success": True,
                    "id": f"compass-{resource_kind}-{resource_data['metadata']['name']}-id"}




