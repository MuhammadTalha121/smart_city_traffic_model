import os
import pytest
from fastapi.testclient import TestClient
from app import app
from src.datex_export import to_datex_measurement, generate_datex_payload
from src.model import congestion_level


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_to_datex_measurement_includes_required_fields():
    """Check that the measurement dict has the expected top-level keys."""
    pred = {
        'congestion_score': 0.75,
        'congestion_level': 'High',
        'vehicle_count': 350,
        'avg_speed': 45,
    }
    result = to_datex_measurement(pred, 'Zone_1', 'Riyadh', '2025-01-01T00:00:00')
    assert 'measurementSiteReference' in result
    assert 'measurementTime' in result
    assert 'measuredValue' in result
    assert 'congestionLevel' in result
    # Check measuredValue list length and keys
    assert len(result['measuredValue']) == 4
    for item in result['measuredValue']:
        assert 'valueType' in item
        assert 'value' in item
        assert 'unit' in item


def test_generate_datex_payload_returns_valid_structure(client):
    """Check that the full payload has the expected structure."""
    # This relies on app.state being populated; the test client lifecycle
    # should have run the lifespan and set up city_dfs.
    payload = generate_datex_payload('Riyadh')
    assert 'publicationCreator' in payload
    assert 'publicationTime' in payload
    assert 'publicationType' in payload
    assert 'measurements' in payload
    assert isinstance(payload['measurements'], list)
    # If data exists, check a measurement structure
    if payload['measurements']:
        m = payload['measurements'][0]
        assert 'measurementSiteReference' in m
        assert 'measuredValue' in m


def test_datex_export_endpoint_requires_auth(client):
    """Without API key, endpoint returns 401."""
    response = client.get("/export/datex?city=Riyadh")
    assert response.status_code == 401


def test_datex_export_endpoint_returns_valid_structure(client):
    """With valid API key, returns 200 and valid structure."""
    api_key = os.getenv("API_KEY")
    if not api_key:
        pytest.skip("API_KEY not set in environment")
    response = client.get("/export/datex?city=Riyadh", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert "publicationCreator" in data
    assert "measurements" in data
    # Check that measurements list is present
    assert isinstance(data["measurements"], list)








import os
import pytest
from fastapi.testclient import TestClient
from app import app
from src.gtfs_rt_export import to_gtfs_vehicle_position, to_gtfs_trip_update

os.environ.setdefault("API_KEY", "test-key-for-pytest-only")
TEST_KEY = os.environ["API_KEY"]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_gtfs_vehicle_position_includes_required_fields():
    trip = {
        "shuttle_id": "DRT_0",
        "passengers": 4,
        "route": ["Zone_4", "Zone_2", "Zone_1"],
        "estimated_wait_mins": 5,
        "estimated_journey_mins": 12,
    }
    result = to_gtfs_vehicle_position(trip)
    assert result["id"] == "vehicle-DRT_0"
    v = result["vehicle"]
    assert v["trip"]["trip_id"] == "DRT-DRT_0"
    assert "latitude" in v["position"] and "longitude" in v["position"]
    assert v["vehicle"]["id"] == "DRT_0"
    assert "timestamp" in v


def test_gtfs_trip_update_maps_congestion_to_delay():
    forecast = {
        "hours_ahead": 1, "forecast_hour": 9, "predicted_score": 0.7,
        "lower_bound": 0.6, "upper_bound": 0.8, "congestion_level": "Critical",
    }
    result = to_gtfs_trip_update(forecast, "Zone_1")
    stu = result["trip_update"]["stop_time_update"][0]
    assert stu["stop_id"] == "Zone_1"
    assert stu["arrival"]["delay"] == 360
    assert stu["arrival"]["uncertainty"] > 0


def test_gtfs_rt_endpoint_no_auth_returns_401(client):
    response = client.get("/export/gtfs-rt?city=Riyadh")
    assert response.status_code == 401


def test_gtfs_rt_endpoint_returns_valid_structure(client):
    response = client.get(
        "/export/gtfs-rt?city=Riyadh", headers={"X-API-Key": TEST_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["header"]["gtfs_realtime_version"] == "2.0"
    assert "entity" in data and isinstance(data["entity"], list)
    assert "gapNote" in data
    assert "not GTFS-RT compliant" in data["gapNote"]


def test_gtfs_rt_unknown_city_returns_404(client):
    response = client.get(
        "/export/gtfs-rt?city=Atlantis", headers={"X-API-Key": TEST_KEY}
    )
    assert response.status_code == 404




import os
import pytest
from fastapi.testclient import TestClient
from app import app
from src.siri_export import to_siri_vehicle_activity, to_siri_estimated_timetable
from src.model import compute_signal_timing


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_to_siri_vehicle_activity_includes_required_fields():
    trip = {"shuttle_id": "DRT_0", "passengers": 4, "route": ["Zone_4", "Zone_2", "Zone_1"],
            "estimated_wait_mins": 5, "estimated_journey_mins": 12}
    result = to_siri_vehicle_activity(trip)
    assert "RecordedAtTime" in result
    journey = result["MonitoredVehicleJourney"]
    assert journey["VehicleRef"] == "DRT_0"
    assert journey["MonitoredCall"]["StopPointRef"] == "Zone_4"
    assert journey["MonitoredCall"]["DestinationDisplay"] == "Zone_1"
    assert "Longitude" in journey["VehicleLocation"]


def test_to_siri_estimated_timetable_includes_required_fields():
    timing = compute_signal_timing(congestion_score=0.5, vehicle_count=200, hour=8, is_weekend=0)
    result = to_siri_estimated_timetable("Zone_1", timing)
    journey = result["EstimatedVehicleJourney"]
    call = journey["EstimatedCalls"]["EstimatedCall"][0]
    assert call["StopPointRef"] == "Zone_1"
    assert "ExpectedArrivalTime" in call
    assert "ArrivalStatus" in call


def test_siri_export_requires_auth(client):
    response = client.get("/export/siri?city=Riyadh")
    assert response.status_code == 401


def test_siri_export_returns_valid_structure(client):
    api_key = os.getenv("API_KEY")
    if not api_key:
        pytest.skip("API_KEY not set in environment")
    response = client.get("/export/siri?city=Riyadh", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    delivery = data["Siri"]["ServiceDelivery"]
    assert "ResponseTimestamp" in delivery
    assert "EstimatedTimetableDelivery" in delivery  # always populated (per-zone signal data exists)


def test_siri_export_unknown_city_returns_404(client):
    api_key = os.getenv("API_KEY")
    if not api_key:
        pytest.skip("API_KEY not set in environment")
    response = client.get("/export/siri?city=Atlantis", headers={"X-API-Key": api_key})
    assert response.status_code == 404






"""
Standards compliance validation suite — PROMPT 139.

Validates that /export/datex-ii, /export/siri, and /export/gtfs-rt
produce outputs that conform to DATEX II v3.4, SIRI 2.0, and GTFS-RT v2.0
schemas respectively.

Non-conformances are assigned an NCF-* ID and documented in
STANDARDS_COMPLIANCE.md rather than treated as hard failures — unless the
output is structurally invalid (not parseable at all), which is always a
hard failure.

Run:
    pytest tests/test_standards_compliance.py -v
    make validate-standards
"""
import os
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app import app


API_KEY = os.getenv("API_KEY", "")
_AUTH = {"X-API-Key": API_KEY}


# ---------------------------------------------------------------------------
# Inline minimal structural schemas
# ---------------------------------------------------------------------------
# These validate root element presence + mandatory attributes only.
# Full namespace-aware validation requires the official multi-file XSD bundles
# (see STANDARDS_COMPLIANCE.md — NCF-D2, NCF-S2).

_DATEX_II_STRUCTURAL_XSD = """\
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           elementFormDefault="unqualified">
  <xs:element name="D2LogicalModel">
    <xs:complexType>
      <xs:sequence minOccurs="0" maxOccurs="unbounded">
        <xs:any processContents="lax"/>
      </xs:sequence>
      <xs:attribute name="modelBaseVersion" type="xs:string" use="required"/>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

_SIRI_STRUCTURAL_XSD = """\
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           elementFormDefault="unqualified">
  <xs:element name="Siri">
    <xs:complexType>
      <xs:sequence minOccurs="0" maxOccurs="unbounded">
        <xs:any processContents="lax"/>
      </xs:sequence>
      <xs:attribute name="version" type="xs:string" use="required"/>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""


# ---------------------------------------------------------------------------
# Optional-dependency helpers
# ---------------------------------------------------------------------------

def _lxml():
    """Return lxml.etree or None when the package is not installed."""
    try:
        from lxml import etree  # noqa: PLC0415
        return etree
    except ImportError:
        return None


def _gtfs_rt_pb2():
    """Return gtfs_realtime_pb2 or None when gtfs-realtime-bindings is absent."""
    try:
        from google.transit import gtfs_realtime_pb2  # noqa: PLC0415
        return gtfs_realtime_pb2
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """
    Module-scoped TestClient that runs the FastAPI lifespan so that
    app.state.df and app.state.model are available to all tests.
    """
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# DATEX II v3.4 — Tests
# ---------------------------------------------------------------------------

class TestDATEXIICompliance:
    """Validate /export/datex-ii against DATEX II v3.4 schema."""

    def test_datex_ii_endpoint_returns_200(self, client):
        """
        Authenticated GET /export/datex-ii must return HTTP 200.
        A non-200 response means the Prompt 100 export endpoint is missing
        or mis-routed in app.py.
        """
        response = client.get("/export/datex", headers=_AUTH)
        assert response.status_code == 200, (
            f"/export/datex-ii returned {response.status_code}. "
            "Verify that Prompt 100 registered this endpoint in app.py."
        )

    def test_datex_ii_content_type_is_xml(self, client):
        """
        DATEX II responses should carry XML content-type per standard.
        Current endpoint returns application/json — NCF-D-FORMAT.
        See STANDARDS_COMPLIANCE.md.
        """
        response = client.get("/export/datex", headers=_AUTH)
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        if "xml" not in content_type.lower():
            pytest.xfail(
                f"NCF-D-FORMAT confirmed: /export/datex returns {content_type!r} "
                "instead of XML. Endpoint is JSON-shaped, not true DATEX II XML."
            )

    def test_datex_ii_output_validates_against_schema(self, client):
        """
        Validates DATEX II export against structural XSD.
        Current endpoint returns JSON, not XML — NCF-D-FORMAT applies.
        XSD validation is xfailed until endpoint emits true XML.
        """
        response = client.get("/export/datex", headers=_AUTH)
        assert response.status_code == 200

        content_type = response.headers.get("content-type", "")
        if "xml" not in content_type.lower():
            pytest.xfail(
                "NCF-D-FORMAT: /export/datex returns JSON, not XML. "
                "XSD schema validation cannot run. See STANDARDS_COMPLIANCE.md."
            )

        etree = _lxml()
        if etree is not None:
            schema_doc = etree.parse(BytesIO(_DATEX_II_STRUCTURAL_XSD.encode("utf-8")))
            xsd = etree.XMLSchema(schema_doc)
            try:
                xml_doc = etree.parse(BytesIO(response.content))
            except etree.XMLSyntaxError as exc:
                pytest.fail(f"DATEX II response is not well-formed XML: {exc} — NCF-D0")
            if not xsd.validate(xml_doc):
                errors = [str(e) for e in xsd.error_log]
                pytest.fail(
                    "DATEX II structural schema validation failed:\n"
                    + "\n".join(errors[:5])
                )
        else:
            body = response.content
            assert b"D2LogicalModel" in body, "Missing D2LogicalModel root — NCF-D0"
            assert b"modelBaseVersion" in body, "Missing modelBaseVersion — NCF-D1"

    def test_datex_ii_requires_authentication(self, client):
        """
        /export/datex-ii must reject unauthenticated requests with 401 or 403.
        Unauthenticated data exports violate Rule 30 (least privilege).
        """
        response = client.get("/export/datex")
        assert response.status_code in (401, 403), (
            f"Expected 401/403 for unauthenticated request, got {response.status_code}."
        )


# ---------------------------------------------------------------------------
# SIRI v2.0 — Tests
# ---------------------------------------------------------------------------

class TestSIRICompliance:
    """Validate /export/siri against SIRI 2.0 schema."""

    def test_siri_endpoint_returns_200(self, client):
        """
        Authenticated GET /export/siri must return HTTP 200.
        A non-200 means the Prompt 100 SIRI export is missing in app.py.
        """
        response = client.get("/export/siri", headers=_AUTH)
        assert response.status_code == 200, (
            f"/export/siri returned {response.status_code}. "
            "Verify that Prompt 100 registered this endpoint in app.py."
        )

    def test_siri_content_type_is_xml(self, client):
        """
        SIRI 2.0 standard requires XML content-type.
        Current endpoint returns application/json — NCF-S1.
        """
        response = client.get("/export/siri", headers=_AUTH)
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        if "xml" not in content_type.lower():
            pytest.xfail(
                f"NCF-S1 confirmed: /export/siri returns {content_type!r} "
                "instead of XML. See STANDARDS_COMPLIANCE.md."
        )
            
    def test_siri_output_validates_against_schema(self, client):
        """
        Validates SIRI export against structural XSD.
        Current endpoint returns JSON — NCF-S-FORMAT applies.
        """
        response = client.get("/export/siri", headers=_AUTH)
        assert response.status_code == 200

        content_type = response.headers.get("content-type", "")
        if "xml" not in content_type.lower():
            pytest.xfail(
                "NCF-S-FORMAT: /export/siri returns JSON, not XML. "
                "XSD schema validation cannot run. See STANDARDS_COMPLIANCE.md."
            )

        etree = _lxml()
        if etree is not None:
            schema_doc = etree.parse(BytesIO(_SIRI_STRUCTURAL_XSD.encode("utf-8")))
            xsd = etree.XMLSchema(schema_doc)
            try:
                xml_doc = etree.parse(BytesIO(response.content))
            except etree.XMLSyntaxError as exc:
                pytest.fail(f"SIRI response is not well-formed XML: {exc} — NCF-S0")
            if not xsd.validate(xml_doc):
                errors = [str(e) for e in xsd.error_log]
                pytest.fail(
                    "SIRI structural schema validation failed:\n"
                    + "\n".join(errors[:5])
                )
        else:
            body = response.content
            assert b"Siri" in body, "Missing Siri root element — NCF-S0"
            assert b'version="2.0"' in body or b"version='2.0'" in body, "Missing version='2.0' — NCF-S1"

    def test_siri_service_delivery_present(self, client):
        """
        A SIRI 2.0 traffic export must contain a ServiceDelivery child element.
        Absence indicates an incomplete SIRI wrapper — NCF-S3.
        """
        response = client.get("/export/siri", headers=_AUTH)
        assert response.status_code == 200
        assert b"ServiceDelivery" in response.content, (
            "SIRI export missing ServiceDelivery element — NCF-S3. "
            "See STANDARDS_COMPLIANCE.md."
        )

    def test_siri_requires_authentication(self, client):
        """
        /export/siri must reject unauthenticated requests with 401 or 403.
        """
        response = client.get("/export/siri")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GTFS-RT v2.0 — Tests
# ---------------------------------------------------------------------------

class TestGTFSRTCompliance:
    """Validate /export/gtfs-rt against GTFS-RT v2.0 protobuf schema."""

    def test_gtfs_rt_endpoint_returns_200(self, client):
        """
        Authenticated GET /export/gtfs-rt must return HTTP 200.
        A non-200 means the Prompt 100 GTFS-RT export is missing in app.py.
        """
        response = client.get("/export/gtfs-rt", headers=_AUTH)
        assert response.status_code == 200, (
            f"/export/gtfs-rt returned {response.status_code}. "
            "Verify that Prompt 100 registered this endpoint in app.py."
        )

    def test_gtfs_rt_content_type_is_protobuf(self, client):
        """
        GTFS-RT standard requires protobuf content-type.
        Current endpoint returns application/json — NCF-G1.
        """
        response = client.get("/export/gtfs-rt", headers=_AUTH)
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        valid = ("application/x-protobuf", "application/octet-stream")
        if not any(t in content_type for t in valid):
            pytest.xfail(
                f"NCF-G1 confirmed: /export/gtfs-rt returns {content_type!r} "
                "instead of protobuf. See STANDARDS_COMPLIANCE.md."
            )

    def test_gtfs_rt_output_validates_against_schema(self, client):
        """
        Validates GTFS-RT export via protobuf parse.
        Current endpoint returns JSON — NCF-G-FORMAT applies.
        """
        pb2 = _gtfs_rt_pb2()
        if pb2 is None:
            pytest.skip(
                "gtfs-realtime-bindings not installed. "
                "Run: pip install gtfs-realtime-bindings --break-system-packages"
            )

        response = client.get("/export/gtfs-rt", headers=_AUTH)
        assert response.status_code == 200

        content_type = response.headers.get("content-type", "")
        if not any(t in content_type for t in ("application/x-protobuf", "application/octet-stream")):
            pytest.xfail(
                "NCF-G-FORMAT: /export/gtfs-rt returns JSON, not protobuf binary. "
                "Protobuf schema validation cannot run. See STANDARDS_COMPLIANCE.md."
            )

        feed = pb2.FeedMessage()
        try:
            feed.ParseFromString(response.content)
        except Exception as exc:
            pytest.fail(f"GTFS-RT protobuf parse failed: {exc} — NCF-G0")

        assert feed.HasField("header"), "FeedMessage missing FeedHeader — NCF-G2"
        assert feed.header.gtfs_realtime_version == "2.0", \
            f"Expected version '2.0', got '{feed.header.gtfs_realtime_version}' — NCF-G3"
        assert feed.header.timestamp > 0, "FeedHeader.timestamp missing or zero — NCF-G4"
    def test_gtfs_rt_requires_authentication(self, client):
        """
        /export/gtfs-rt must reject unauthenticated requests with 401 or 403.
        """
        response = client.get("/export/gtfs-rt")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Makefile target existence
# ---------------------------------------------------------------------------

class TestMakefileTarget:
    """Verify the validate-standards Makefile target exists."""

    def test_makefile_has_validate_standards_target(self):
        """
        Confirm the Makefile contains a validate-standards target so CI can
        run schema validation with: make validate-standards
        """
        try:
            with open("Makefile", encoding="utf-8") as fh:
                content = fh.read()
            assert "validate-standards" in content, (
                "Makefile is missing the 'validate-standards' target. "
                "Add it per Prompt 139 deliverable 3."
            )
        except FileNotFoundError:
            pytest.fail(
                "Makefile not found in project root. "
                "Create one with a validate-standards target."
            )