# Phase 5: RCA Module, MTTR & Observability

## RCA Lifecycle

```
Work Item reaches RESOLVED
         │
         ▼
User opens RCA tab in drawer
User fills: incident_start/end, category, description, fix, prevention
         │
         ▼
POST /work-items/{id}/rca
  → schema validates (min lengths, end > start)
  → MTTR calculated: (incident_end - incident_start) in seconds
  → RCA persisted to PostgreSQL (transactional, with retry)
  → mttr_seconds written back to WorkItem
  → Redis cache invalidated
  → WebSocket broadcasts work_item_updated
         │
         ▼
User clicks "Close Incident" in Workflow tab
  → State machine validates RESOLVED → CLOSED
  → workflow_engine._validate_rca() checks RCA exists + complete
  → Work Item moves to CLOSED
```

## MTTR Calculation

```python
mttr_seconds = max(0, int((incident_end - incident_start).total_seconds()))
```

Stored on the WorkItem record for fast retrieval.
The Observability page aggregates `avg(mttr_seconds)` grouped by priority.

## Retry Logic (exponential backoff)

```python
for attempt in range(3):
    try:
        return await db_operation()
    except SQLAlchemyError:
        await asyncio.sleep(0.1 * 2**attempt)  # 100ms, 200ms, 400ms
raise  # re-raise after 3 failures
```

Applied to all RCA DB writes and Work Item MTTR updates.

## Observability Endpoints

| Endpoint              | Data source         | Refresh         |
|-----------------------|---------------------|-----------------|
| GET /metrics/full     | Redis + PG + SQLite | Per-request     |
| GET /metrics/throughput | Redis buckets     | Per-minute keys |
| GET /metrics/mttr     | PostgreSQL          | Per-request     |
| GET /metrics/signals  | SQLite              | Per-request     |

Throughput history uses Redis keys `obs:throughput:{epoch_minute}` with 1h TTL.
Each signal processed increments the current minute's bucket.

## Frontend RCA Form Validations

| Field                    | Rule                     |
|--------------------------|--------------------------|
| incident_start           | Required datetime         |
| incident_end             | Required, must be > start |
| root_cause_category      | Required dropdown         |
| root_cause_description   | min 20 chars              |
| fix_applied              | min 10 chars              |
| prevention_steps         | min 10 chars              |

Live MTTR preview updates as user adjusts dates.
CharCount indicator turns green when minimum is met.
