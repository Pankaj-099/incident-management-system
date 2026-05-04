# Key Design Decisions & Tradeoffs

## 1. SQLite as the Data Lake

**Decision:** Use SQLite for raw signal storage instead of MongoDB or a dedicated time-series DB.

**Rationale:**
- Spec said "NoSQL" for raw signal storage — SQLite satisfies this as a document-capable lightweight store
- No extra container needed (simplifies Docker Compose for reviewers)
- `aiosqlite` is fully async, keeping the single-thread asyncio model clean
- Append-only insert pattern means no contention; queries use indexed `component_id` and `work_item_id`
- Can be trivially swapped for MongoDB by changing the sink service

**Tradeoff:** Not distributed; a production system with multi-node writers would need a real NoSQL store.

---

## 2. asyncio.Queue over Kafka/RabbitMQ

**Decision:** Use Python's built-in `asyncio.Queue` as the ingestion buffer.

**Rationale:**
- A message broker adds 2 more containers and significant operational overhead
- For a single-node deployment, in-process queue gives sub-millisecond enqueue latency
- The 50K cap + `put_nowait()` pattern correctly implements backpressure without blocking
- Easy to replace: change `enqueue_signal()` to push to Kafka instead of the queue

**Tradeoff:** Not durable. If the process crashes, queued-but-unprocessed signals are lost. Mitigated by the rate at which workers drain (typical drain time < 1s).

---

## 3. Redis Pub/Sub for WebSocket Fanout

**Decision:** Route all WebSocket broadcasts through a Redis `PUBLISH`/`SUBSCRIBE` channel.

**Rationale:**
- FastAPI runs multiple workers in production (`--workers 4`)
- Without Pub/Sub, a signal processed by Worker A only reaches WS clients connected to Worker A
- Redis `PUBLISH` is fire-and-forget with microsecond latency
- Each worker maintains its own `SUBSCRIBE` coroutine and fans out to local connections

**Tradeoff:** Adds Redis dependency for WS. Mitigated by falling back to local broadcast if Redis is unavailable.

---

## 4. Distributed Lock for Work Item Creation

**Decision:** Use Redis `SET key value NX EX 30` as a creation lock during debounce.

**Rationale:**
- All 4 workers process signals concurrently
- Without a lock, two workers could both find `GET debounce:RDBMS_PRIMARY = nil` and both create Work Items
- `NX` (only set if not exists) makes the lock atomic at the Redis level
- 30s TTL prevents lock starvation if the winning worker crashes mid-creation

**Alternative considered:** PostgreSQL advisory locks — ruled out because it tightly couples the debounce logic to PG and adds a round-trip.

---

## 5. State Pattern over a Status Enum + Switch

**Decision:** Each state is a class with `allowed_transitions` and `on_enter()`.

**Rationale:**
- Spec explicitly called for the State pattern
- Adding a new state (e.g., `ESCALATED`) requires only a new class + registration — no switch statement changes
- `CLOSED.validate_transition()` unconditionally raises, making the terminal state impossible to circumvent even via direct DB manipulation through the API
- `on_enter()` keeps timestamp logic (resolved_at, closed_at) co-located with the state that cares about it

---

## 6. Strategy Pattern for Alert Dispatch

**Decision:** One concrete `AlertStrategy` class per component type, registered in a factory.

**Rationale:**
- Spec explicitly called for the Strategy pattern
- Adding a new alert channel (e.g., PagerDuty webhook) requires subclassing and one-line registration
- `AlertStrategyFactory.get("RDBMS")` is called at dispatch time — the caller doesn't know which channel is being used
- Strategies currently log to console; replacing with real HTTP calls requires changing only `dispatch()`

---

## 7. RCA Guard in the Workflow Engine, not the State

**Decision:** The RCA completeness check lives in `workflow_engine.py`, not in `ClosedState`.

**Rationale:**
- `ClosedState.validate_transition()` knows only about state logic, not domain entities
- The RCA check requires a DB query — mixing I/O into a synchronous state object would break the pattern
- The engine is the right orchestration layer for cross-cutting domain guards

---

## 8. Frontend Single WebSocket Connection

**Decision:** One WebSocket connection per browser tab, maintained at `DashboardPage` level, with events propagated to children via React props.

**Rationale:**
- Multiple components subscribing independently would create N connections per page
- `useRealtimeEvents` at the page level owns the single connection
- Child components (`WorkItemList`, `SignalFeed`) receive updates via `externalNewItems`/`externalSignals` props
- This also centralises toast dispatch logic in one place
