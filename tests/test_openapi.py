import os
os.environ.setdefault("API_KEY", "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780")
TEST_KEY = os.environ["API_KEY"]

import json
import pytest
from fastapi.testclient import TestClient
from app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_openapi_spec_valid_json(client):
    """The /openapi.json endpoint must return valid JSON with required keys."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    spec = response.json()
    assert isinstance(spec, dict)
    assert "openapi" in spec
    assert spec["openapi"].startswith("3.")
    assert "info" in spec
    assert "title" in spec["info"]
    assert "version" in spec["info"]
    assert "paths" in spec
    assert len(spec["paths"]) > 20


def test_all_endpoints_have_descriptions(client):
    """
    Every operation in the OpenAPI spec must include a non-empty description.
    FastAPI derives the description from the endpoint's docstring.
    """
    spec = client.get("/openapi.json").json()
    paths = spec.get("paths", {})
    missing = []

    for path, methods in paths.items():
        for method, operation in methods.items():
            if method.lower() not in ("get", "post", "put", "delete", "patch"):
                continue
            description = (operation.get("description") or "").strip()
            summary = (operation.get("summary") or "").strip()
            if not description and not summary:
                missing.append(f"{method.upper()} {path}")

    assert not missing, (
        f"The following {len(missing)} endpoints have no description or summary:\n  - "
        + "\n  - ".join(missing)
    )


def test_no_undocumented_endpoints(client):
    """
    Every route registered on the app must appear in the OpenAPI spec.
    This guards against endpoints added without a proper decorator tag
    or accidentally hidden from docs.
    """
    spec = client.get("/openapi.json").json()
    documented_paths = set(spec.get("paths", {}).keys())

    undocumented = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        if path in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"):
            continue
        if not path.startswith("/"):
            continue
        if path not in documented_paths:
            undocumented.append(path)

    assert not undocumented, (
        f"The following {len(undocumented)} routes are not in the OpenAPI spec:\n  - "
        + "\n  - ".join(sorted(set(undocumented)))
    )


def test_redoc_ui_available(client):
    """Redoc UI must be served at /redoc."""
    response = client.get("/redoc")
    assert response.status_code == 200
    assert "redoc" in response.text.lower()