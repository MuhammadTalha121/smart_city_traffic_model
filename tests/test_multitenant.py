import os
import secrets
import pytest

os.environ.setdefault('API_KEY', 'test-key-for-pytest-only')

from src.pipeline import parse_key_registry


def test_operator_key_blocked_from_admin_endpoint():
    operator_key = secrets.token_hex(16)
    admin_key    = secrets.token_hex(16)
    os.environ['API_KEYS'] = f'{operator_key}:Riyadh:operator,{admin_key}:*:admin'

    from fastapi.testclient import TestClient
    from app import app

    with TestClient(app) as client:
        r = client.get('/pipeline/status', headers={'X-API-Key': operator_key})
    assert r.status_code == 403
    del os.environ['API_KEYS']


def test_wrong_city_key_blocked_from_other_city():
    neom_key = secrets.token_hex(16)
    os.environ['API_KEYS'] = f'{neom_key}:NEOM:operator'

    from fastapi.testclient import TestClient
    from app import app

    with TestClient(app) as client:
        r = client.get('/anomalies?city=Riyadh', headers={'X-API-Key': neom_key})
    assert r.status_code == 403
    del os.environ['API_KEYS']


def test_admin_key_accesses_all_cities():
    admin_key = secrets.token_hex(16)
    os.environ['API_KEYS'] = f'{admin_key}:*:admin'

    from fastapi.testclient import TestClient
    from app import app

    with TestClient(app) as client:
        r1 = client.get('/anomalies?city=Riyadh', headers={'X-API-Key': admin_key})
        r2 = client.get('/pipeline/status',       headers={'X-API-Key': admin_key})
    assert r1.status_code == 200
    assert r2.status_code == 200
    del os.environ['API_KEYS']