import sys

import yaml
from fastapi.openapi.utils import get_openapi

try:
    from main import app
except ImportError as e:
    print(f"❌ Error: Could not import FastAPI app - {e}")
    sys.exit(1)


def generate_openapi_yaml():
    openapi_schema = get_openapi(
        title="Simple FastAPI app",
        version="1.0.0",
        description="Automatically generated OpenAPI schema.",
        routes=app.routes
    )
    with open("docs/openapi.yaml", "w") as f:
        yaml.dump(openapi_schema, f, default_flow_style=False)
    print("✅ OpenAPI YAML generated successfully.")


if __name__ == "__main__":
    try:
        generate_openapi_yaml()
        sys.exit(0)  # Success
    except Exception as e:
        print(f"❌ Error generating OpenAPI YAML: {e}")
        sys.exit(1)  # Failure
