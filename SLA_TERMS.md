# Smart City Traffic Intelligence — SLA Terms

---

## Uptime Commitment

| Metric | Target |
|---|---|
| Monthly uptime | ≥ 99.0% |
| Measurement | Successful HTTP responses (2xx, 3xx) / total requests |
| Monitoring | `/sla/current` (public), `/sla/report` (admin) |

---

## Response Time

| Metric | Target |
|---|---|
| Average response time | < 500ms |
| 95th percentile (p95) | < 1000ms |
| Measurement period | Rolling 30 days |

---

## Planned Maintenance

| Window | Activity |
|---|---|
| 03:00–04:00 daily | Model drift check and conditional retraining |
| Monday 06:00 | Weekly report generation |

Planned maintenance windows do not count against uptime calculations.

---

## Alert Response

| Threshold breach | System action |
|---|---|
| Zone congestion ≥ 0.75 | Webhook alert within 15 minutes |
| Accident risk ≥ 0.70 | Webhook alert within 15 minutes |
| Anomaly ratio ≥ 3.0x expected | Webhook alert within 15 minutes |

---

## Exclusions

The following conditions are excluded from SLA calculations:

- Ramadan and Hajj season demand spikes exceeding 3x normal volume
- Sandstorm events causing external API degradation (Open-Meteo, Overpass)
- Deployment platform (Render / Railway) infrastructure outages
- Force majeure events

---

## Reporting

SLA compliance reports are available at any time:
GET /sla/report?days=30

X-API-Key: your_admin_key

The public status endpoint requires no authentication:
GET /sla/current

---

## Version

These terms apply to Smart City Traffic Intelligence System v5.0.0 and above.