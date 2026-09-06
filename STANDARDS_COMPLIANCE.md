# STANDARDS_COMPLIANCE.md

## Smart City Traffic Intelligence System
### Standards Compliance Report — DATEX II v3.4 · SIRI v2.0 · GTFS-RT v2.0

**Prompt:** 139 — Standards Compliance Validation  
**Validation command:** `make validate-standards`  
**Test file:** `tests/test_standards_compliance.py`

---

## Summary Table

| Standard | Format | Validation Level | Status | Open NCFs |
|---|---|---|---|---|
| DATEX II v3.4 | XML | Structural XSD | PARTIAL | NCF-D2, NCF-D3, NCF-D4 |
| SIRI v2.0 | XML | Structural XSD | PARTIAL | NCF-S2, NCF-S3, NCF-S4, NCF-S5 |
| GTFS-RT v2.0 | Protobuf | Full protobuf parse | CONFORMANT | NCF-G5 (low) |

**Status legend**

| Status | Meaning |
|---|---|
| CONFORMANT | All tested fields match the standard |
| PARTIAL | Root structure and required fields match; full namespace / content validation not yet applied |
| NON-CONFORMANT | Structural parse failure or mandatory field absent |

No standard is currently NON-CONFORMANT. Gaps are documented below.

---

## DATEX II v3.4

### What is validated

The automated test fetches `GET /export/datex-ii` and validates the response
using `lxml.etree.XMLSchema` against an embedded structural XSD that checks:

- Response is well-formed XML (not a parse error)
- Root element is `D2LogicalModel`
- Attribute `modelBaseVersion` is present

### Full-schema validation gap

The complete DATEX II v3.4 XSD bundle consists of approximately 30 interdependent
schema files covering every message type (SituationPublication, TrafficFlowData,
MeasuredDataPublication, etc.). Full validation requires:

1. Downloading the official bundle from `https://datex2.eu/schema/3/3.4/`
2. Storing it locally under `schemas/datex-ii/` (offline CI requirement)
3. Resolving namespace `http://datex2.eu/schema/3/common` on all elements

This is a known gap and is planned for remediation (see NCF-D2 below).

### Non-conformance register

| ID | Element / Field | Standard Requirement | Current State | Severity | Remediation |
|---|---|---|---|---|---|
| NCF-D0 | XML well-formedness | Output must be valid XML | ✅ PASS | — | — |
| NCF-D1 | `modelBaseVersion` attribute | Required on root | ✅ PASS | — | — |
| NCF-D2 | Namespace qualification | Elements must use namespace `http://datex2.eu/schema/3/common` | Not validated | LOW | Bundle XSD locally; extend test |
| NCF-D3 | `exchange.supplierIdentification` | Required in full schema | Not tested | MEDIUM | Add targeted element check once XSD is bundled |
| NCF-D4 | `payloadPublication.lang` | `xml:lang` attribute required | Not tested | LOW | Add targeted element check |

---

## SIRI v2.0

### What is validated

The automated test fetches `GET /export/siri` and validates using
`lxml.etree.XMLSchema` against an embedded structural XSD that checks:

- Response is well-formed XML
- Root element is `Siri`
- Attribute `version` is present
- `ServiceDelivery` child element is present

### Full-schema validation gap

The complete SIRI 2.0 XSD bundle covers ServiceDelivery, StopMonitoring,
VehicleMonitoring, EstimatedTimetable, ConnectionTimetable, and nine other
service interfaces. Full validation requires:

1. Downloading the bundle from `http://www.siri.org.uk/schema/2.0/xsd/`
2. Storing it locally under `schemas/siri/`
3. Resolving namespace `http://www.siri.org.uk/siri` on all elements

### Note on SIRI-TM

SIRI for traffic monitoring uses the SIRI-TM extension profile, which adds
TrafficMonitoringServiceDelivery and RoadEvent types. The current export uses
the generic SIRI ServiceDelivery wrapper only. This is a material gap (NCF-S5)
for full ITS interoperability.

### Non-conformance register

| ID | Element / Field | Standard Requirement | Current State | Severity | Remediation |
|---|---|---|---|---|---|
| NCF-S0 | XML well-formedness | Output must be valid XML | ✅ PASS | — | — |
| NCF-S1 | `version="2.0"` attribute | Required on Siri root | ✅ PASS | — | — |
| NCF-S2 | Namespace qualification | Elements must use `http://www.siri.org.uk/siri` | Not validated | LOW | Bundle XSD locally; extend test |
| NCF-S3 | `ServiceDelivery.ResponseTimestamp` | ISO 8601 timestamp required | Not validated | MEDIUM | Add targeted element check |
| NCF-S4 | `ServiceDelivery.ProducerRef` | Operator reference required | Not validated | LOW | Add to export endpoint output |
| NCF-S5 | SIRI-TM extension | TrafficMonitoringServiceDelivery type | Not implemented | HIGH | Implement SIRI-TM adapter in a future prompt |

---

## GTFS-RT v2.0

### What is validated

The automated test fetches `GET /export/gtfs-rt` and runs full protobuf schema
validation using `google.transit.gtfs_realtime_pb2.FeedMessage.ParseFromString()`.
This is complete structural validation — not structural approximation.

The following fields are validated:

| Field | Requirement | Status |
|---|---|---|
| Binary parseability | Must deserialise as FeedMessage | ✅ PASS |
| Content-Type header | `application/x-protobuf` or `application/octet-stream` | ✅ PASS |
| `FeedHeader` presence | Required by v2.0 spec | ✅ PASS |
| `FeedHeader.gtfs_realtime_version` | Must equal `"2.0"` | ✅ PASS |
| `FeedHeader.timestamp` | Required POSIX timestamp, non-zero | ✅ PASS |

### Non-conformance register

| ID | Element / Field | Standard Requirement | Current State | Severity | Remediation |
|---|---|---|---|---|---|
| NCF-G0 | Protobuf parseability | Binary must parse as FeedMessage | ✅ PASS | — | — |
| NCF-G1 | Content-Type | `application/x-protobuf` | ✅ PASS | — | — |
| NCF-G2 | `FeedHeader` | Required field | ✅ PASS | — | — |
| NCF-G3 | `gtfs_realtime_version` | Must be `"2.0"` | ✅ PASS | — | — |
| NCF-G4 | `FeedHeader.timestamp` | Non-zero POSIX timestamp | ✅ PASS | — | — |
| NCF-G5 | Per-entity field validation | VehiclePosition, TripUpdate, Alert sub-schemas | Not validated | LOW | Add per-entity field presence tests in a follow-up prompt |

GTFS-RT has the strongest compliance posture because protobuf provides binary schema
enforcement at parse time — invalid fields cannot be silently ignored.

---

## Dependencies required

Add to `requirements.txt` if not already present:

```
lxml>=4.9.0
gtfs-realtime-bindings>=1.0.0
protobuf>=3.20.0
```

---

## Vision 2030 relevance

| Authority / Platform | Standard Expected | Current State |
|---|---|---|
| Muroor (Saudi Traffic Police) | DATEX II incident reports | PARTIAL — NCF-D2 to D4 open |
| Saudi Public Transport Authority (PTA) | GTFS-RT real-time feeds | CONFORMANT |
| NEOM Smart City Platform | SIRI multi-modal exchange | PARTIAL — NCF-S5 is a HIGH gap |
| ITS Arabia tender requirements | DATEX II compliance declared | PARTIAL — namespace gap to close |

Full DATEX II and SIRI-TM compliance would remove the need for a custom data
translation layer when integrating with Vision 2030 smart infrastructure programs.
Closing NCF-S5 (SIRI-TM) is the highest-priority remediation item.

---

## How to run

```bash
# All three standards
make validate-standards

# Verbose per-standard
pytest tests/test_standards_compliance.py::TestDATEXIICompliance -v
pytest tests/test_standards_compliance.py::TestSIRICompliance -v
pytest tests/test_standards_compliance.py::TestGTFSRTCompliance -v
```
