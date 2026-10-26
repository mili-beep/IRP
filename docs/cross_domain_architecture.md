# Cross-domain architecture demonstration

The HVAC experiments remain the only evaluated anomaly-detection evidence in
this repository. No approved second Smart Facilities SA data source is
available, so E08 uses a deliberately small synthetic access-control log only
to demonstrate the adapter boundary.

All sources should be converted to the following canonical fields before any
downstream quality, pattern, event, or dashboard component consumes them:

| Field | Meaning |
|---|---|
| `timestamp` | Event or observation time, parsed as a datetime |
| `source_system` | Origin, such as `hvac`, `access_control`, or `power_management` |
| `asset_id` | Stable source-device/asset identifier |
| `event_type` | Observation/event category |
| `measurements` | Source-specific values retained as provenance-preserving JSON text |
| `status` | Source-reported state or severity |
| `provenance` | Input identity and whether it is demonstration or operational data |

The access-control adapter validates these fields and timestamp quality. It
does **not** establish access-control anomaly-detection performance, staff
utility, or cross-domain model generalisation. A future approved dataset must
be audited and evaluated separately before those claims can be made.
