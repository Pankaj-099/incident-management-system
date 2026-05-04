# Phase 2: Signal Ingestion & Backpressure

## Design Decisions

### Backpressure Architecture

```
Producer (HTTP)
     │
     ▼
Rate Limiter (SlowAPI)          ← Layer 1: shed load at the door
     │
     ▼
asyncio.Queue (in-memory)       ← Layer 2: decouple producer from storage
  maxsize=50,000
     │ (non-blocking put_nowait)
     ▼
Signal Workers (×4)             ← Layer 3: async consumers
     │
     ├──▶ SQLite (fast local)   ← always persisted immediately
     └──▶ Redis metrics counter
```

If `asyncio.Queue` is full, `put_nowait()` raises `QueueFull` — we catch it
and return `503 Queue Full` to the producer instead of blocking or crashing.

### Why asyncio.Queue instead of an external queue (Kafka/RabbitMQ)?

For a single-node deployment, `asyncio.Queue` gives us:
- Zero network overhead
- Survives Redis/Postgres slowness (signals buffered in RAM)
- Up to ~50K signals buffered before backpressure kicks in
- Easy to swap for an external queue later (Phase 8 bonus)

### Rate Limiting Strategy

- `POST /ingest`: 2,000 req/min per IP (≈33 req/sec)
- `POST /ingest/batch`: 200 req/min per IP (batch up to 500 signals = 100K signals/min)
- Rate limits are enforced at the HTTP boundary via SlowAPI token bucket

### Worker Pool

4 `asyncio` coroutines concurrently drain the queue. All are I/O-bound so
`asyncio` cooperative multitasking is ideal here (no GIL contention).

### SQLite as the Data Lake

Raw signals are written to SQLite (`signals.db`) as the append-only audit log.
Indexed on `component_id` and `work_item_id` for fast lookup in Phase 3+.

The `_write_with_retry` function implements exponential backoff (base=100ms)
with 3 attempts before a signal is permanently dropped.
