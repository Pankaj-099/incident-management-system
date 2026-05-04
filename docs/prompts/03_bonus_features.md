# Bonus Features (Beyond the Spec)

The following features were added beyond the original assignment requirements:

## 1. Redis Pub/Sub WebSocket Fanout
**Why:** The spec only required WebSocket updates. The Pub/Sub architecture ensures broadcasts work correctly with multiple uvicorn workers — a production requirement the spec didn't explicitly call out but is essential for correctness.

## 2. WebSocket Heartbeat (Ping/Pong)
**Why:** Browser WebSocket connections silently die behind NAT gateways and load balancers without keepalive frames. The 30s ping/pong protocol keeps connections alive and prunes dead ones automatically.

## 3. Exponential Backoff Retry on all DB Writes
**Why:** Every DB write in the system (`sqlite_sink.py`, `rca_service.py`, `work_item_service.py`) uses 3-attempt exponential backoff (100ms → 200ms → 400ms). Transient connection blips won't lose data.

## 4. Toast Notification System
**Why:** The spec asked for a live feed. Toast notifications give engineers an ambient awareness of P0 incidents and status changes without requiring them to watch the feed constantly.

## 5. Connection Status Bar
**Why:** Engineers need to know if their dashboard is actually receiving live events. The ConnectionBar shows `Live`/`Connecting`/`Reconnecting (N)` states and the server-assigned client ID.

## 6. Recharts Timeseries Throughput Chart
**Why:** The spec asked for timeseries aggregations. A visual chart in the Observability page is far more useful than a raw number — you can see traffic patterns, incident spikes, and recovery.

## 7. Stress Test Script
**Why:** Proving the backpressure claim requires an actual load test. `stress_test.py` lets reviewers verify the 10K signals/sec claim and measure real rejection rates.

## 8. Seed Scripts for Demo-Ready State
**Why:** Reviewing a dashboard with zero data is difficult. `seed_signals.py` and `seed_closed_incidents.py` produce a realistic dataset in under 30 seconds, including fully-closed incidents with MTTR data.

## 9. `GET /ws/status` Endpoint
**Why:** Operational visibility into active WebSocket connections — useful for debugging connection issues and confirming pub/sub is working.

## 10. Work Item Re-Investigation Path
**Why:** The spec defined `OPEN → INVESTIGATING → RESOLVED → CLOSED` but real incidents often need to go back to `INVESTIGATING` from `RESOLVED` when a fix doesn't hold. The state machine includes `RESOLVED → INVESTIGATING` as an allowed transition.

## 11. Industrial Terminal UI Design
**Why:** The spec said "simple, responsive Frontend." The design went beyond that to create an opinionated, cohesive visual language — scanline texture, Geist 800-weight numbers, vivid priority colours on black — that makes incident data immediately scannable under pressure.

## 12. Batch Ingestion Endpoint
**Why:** `POST /ingest/batch` accepts up to 500 signals in one request, reducing HTTP overhead for high-volume producers by up to 500×.
