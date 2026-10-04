"""
Export the FastAPI OpenAPI 3.1 spec to API_SPEC_v2.json at the repo root.

Usage:
    py scripts/export_openapi.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app


def export_spec(output_path: str = "API_SPEC_v2.json") -> str:
    """Write the app's OpenAPI spec to a JSON file."""
    spec = app.openapi()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)
    return output_path


if __name__ == "__main__":
    path = export_spec()
    size = os.path.getsize(path)
    print(f"Exported OpenAPI spec: {path} ({size:,} bytes)")