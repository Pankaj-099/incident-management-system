# Build Plan: 8-Phase Approach

## Technology Decisions

After analysing the spec, the following stack was chosen:

| Requirement | Choice | Rationale |
|---|---|---|
| Backend | Python 3.11 + FastAPI | asyncio-native, excellent WS support, great DX |
| Source of Truth | PostgreSQL + SQLAlchemy async | ACID transactions for Work Items + RCA |
| NoSQL / Data Lake | SQLite (aiosqlite) | Lightweight audit log, no extra container |
| Cache + Debounce | Redis 7 | TTL keys for debounce, Pub/Sub for WS fanout |
| Real-time | FastAPI WebSockets + Redis Pub/Sub | No extra broker needed |
| Frontend | React 18 + Vite + TypeScript | Fast HMR, strong typing, recharts for charts |
| Font | Geist Sans (Vercel) | Clean, technical, monospace companion included |
| Infra | Docker Compose | Single-command startup |

## Phase Breakdown

### Phase 1 — Project Skeleton & Infra
- Mono-repo structure, Docker Compose
- FastAPI app factory with lifespan
- PostgreSQL + Redis + SQLite connections
- `/health` endpoint checking all 3 databases
- Alembic migrations scaffold
- React + Vite + TypeScript base app with Layout

### Phase 2 — Signal Ingestion & Backpressure
- `POST /ingest` and `POST /ingest/batch` endpoints
- SlowAPI rate limiter (2000/min per IP)
- `asyncio.Queue` in-memory buffer (50K cap, `put_nowait` = no blocking)
- 4 async worker coroutines draining the queue
- SQLite raw signal persistence with exponential backoff retry
- Redis throughput counters + 5s console metrics logger
- `GET /signals/recent`, `GET /metrics`, `WS /ws/signals`
- Frontend: SignalFeed, MetricsBar, SignalTester, WebSocket hook

### Phase 3 — Debounce Engine & Work Item Creation
- Redis `debounce:{component_id}` key with 10s TTL
- Distributed lock (`NX EX 30`) prevents race conditions between workers
- Work Item creation in PostgreSQL (transactional, `flush()` + `commit()`)
- SQLite signal → Work Item link update
- Redis dashboard cache (10s TTL, invalidated on mutations)
- `GET /work-items`, `GET /work-items/{id}`, `GET /work-items/{id}/signals`
- Frontend: WorkItemList, WorkItemDrawer (signals + details tabs)

### Phase 4 — Workflow Engine (State + Strategy Patterns)
- **State Pattern**: `OpenState`, `InvestigatingState`, `ResolvedState`, `ClosedState`
  - Each owns `allowed_transitions` and `on_enter()` side-effects
  - `CLOSED` is terminal — rejects all exits
- **Strategy Pattern**: `RDBMSAlertStrategy` (P0/PagerDuty), `APIAlertStrategy` (P1/Slack), `CacheAlertStrategy` (P2/Email), etc.
  - `AlertStrategyFactory` dispatches by `component_type` at runtime
- `PATCH /work-items/{id}/transition` with full validation
- `GET /work-items/{id}/transitions` returns available moves
- Frontend: WorkflowPanel with visual state flow tracker + transition buttons

### Phase 5 — RCA Module, MTTR & Observability
- `RCACreateRequest` schema with `@model_validator` (end > start enforcement)
- `create_or_update_rca()` with MTTR auto-calculation and retry logic
- `POST /work-items/{id}/rca`, `GET /work-items/{id}/rca`, `GET /rcas`
- `GET /metrics/full`, `/metrics/throughput`, `/metrics/mttr`, `/metrics/signals`
- Frontend: RCAForm with live MTTR preview + CharCount indicators, ObservabilityPage

### Phase 6 — WebSocket Architecture & Real-Time Sync
- Redis Pub/Sub fanout (`ims:events` channel) — broadcasts reach all workers
- `WSConnection` dataclass with `client_id`, `connected_at`
- Heartbeat ping every 30s with dead-connection pruning
- Graceful shutdown draining all connections
- Frontend: `useRealtimeEvents` central event bus, Toast notification system, ConnectionBar

### Phase 7 — UI Polish & Timeseries Chart
- Industrial terminal design system: `#080808` black, Geist 800w numbers, scanline texture
- `ThroughputChart` (recharts AreaChart, 30-min window, gradient fill, custom tooltip)
- `StatsStrip` replaces MetricsBar with a dense 5-tile row
- Full CSS pass on all 14 component stylesheets
- Micro-animations: row slide-in, drawer cubic-bezier, shimmer skeletons, badge pulse

### Phase 8 — Documentation, Scripts & Final Polish
- Comprehensive README with architecture diagram, all API docs, backpressure explanation
- `scripts/seed_signals.py` — 500 varied signals across all component types
- `scripts/seed_closed_incidents.py` — 10 complete closed incidents with RCAs
- `scripts/stress_test.py` — configurable high-throughput load tester
- All design docs and prompts checked in under `docs/`
