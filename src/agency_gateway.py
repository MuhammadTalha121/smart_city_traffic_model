"""
Agency Data Sharing Gateway — validation, audit logging, token scoping (PROMPT 131).

Handles AGENCY-role token checks and writes every request to agency_access_log.csv.
No data processing lives here — gateway delegates to existing export functions.
"""

import csv
import hashlib
import os
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from src.auth import validate_key
from src.config import AGENCY_ACCESS_LOG

_api_key_header = APIKeyHeader(name="X-Agency-Token", auto_error=False)


def validate_agency_token(token: Optional[str] = Security(_api_key_header)) -> dict:
    """
    Validate an agency token (AGENCY role required).

    Returns {role, city_scope} on success.
    Raises HTTP 401 if missing, 403 if wrong role or expired.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Agency token required (X-Agency-Token header).")

    credentials = validate_key(token)
    if credentials is None:
        raise HTTPException(status_code=401, detail="Invalid or expired agency token.")
    if credentials["role"] != "AGENCY":
        raise HTTPException(status_code=403, detail="This endpoint requires AGENCY role.")

    return credentials


def log_agency_access(token: str, agency_endpoint: str, city: str) -> None:
    """
    Append one row to agency_access_log.csv.

    Logs only the first 8 chars of the token — never the full key.
    Fields: timestamp, token_prefix, endpoint, city.
    """
    token_prefix = token[:8] if token else "unknown"
    row = {
        "timestamp"   : datetime.utcnow().isoformat(),
        "token_prefix": token_prefix,
        "endpoint"    : agency_endpoint,
        "city"        : city,
    }
    file_exists = os.path.isfile(AGENCY_ACCESS_LOG)
    with open(AGENCY_ACCESS_LOG, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def assert_agency_city_permitted(credentials: dict, city: str) -> None:
    """Raise HTTP 403 if the agency token is not scoped to the requested city."""
    city_scope = credentials.get("city_scope", "all")
    if city_scope != "all" and city not in city_scope.split(","):
        raise HTTPException(
            status_code=403,
            detail=f"Agency token not scoped to city '{city}'.",
        )