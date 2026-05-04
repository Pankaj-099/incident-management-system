# 🚨 Incident Management System (IMS)

A **mission-critical, production-grade** full-stack incident management platform built with FastAPI, React + Vite, PostgreSQL, Redis, and SQLite.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          INGESTION LAYER                                │
│   Producers → POST /ingest → Rate Limiter → asyncio.Queue (50K cap)   │
│                                        [BACKPRESSURE BUFFER]            │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │  4 async workers drain continuously
┌────────────────────────────────▼────────────────────────────────────────┐
│                         PROCESSING LAYER                                │
│   Signal Worker → SQLite Sink → Debounce Engine (Redis 10s TTL)        │
│                                 100 signals → 1 Work Item              │
│                              → Workflow Engine (State + Strategy)       │
└──────────┬──────────────────────────────┬──────────────────────────────┘
           │                              │
    ┌──────▼──────┐    ┌──────────────────▼───────────┐    ┌────────────┐
    │ PostgreSQL  │    │         Redis                │    │  SQLite    │
    │ Work Items  │    │ Dashboard cache • Pub/Sub     │    │ Raw signal │
    │ RCA records │    │ Debounce keys  • Metrics      │    │ audit lake │
    └──────┬──────┘    └──────────────────┬───────────┘    └────────────┘
           │                              │ ims:events channel
           │           ┌──────────────────▼───────────────────────────────┐
           │           │              FRONTEND LAYER                      │
           └──────────►│  React + Vite + WebSocket (ping/pong heartbeat)  │
                       │  Dashboard • WorkItemDrawer • Observability       │
                       └──────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 · FastAPI · asyncio |
| Source of Truth | PostgreSQL 16 + SQLAlchemy 2 (async) + Alembic |
| Cache / Debounce / Pub-Sub | Redis 7 |
| Signal Data Lake | SQLite (append-only, aiosqlite) |
| Real-time | WebSockets (FastAPI native + Redis Pub/Sub fanout) |
| Frontend | React 18 · Vite · TypeScript · Recharts |
| Font | Geist Sans + Geist Mono by Vercel |
| Infra | Docker Compose |

---

## Quick Start (Docker)

**Prerequisites:** Docker Desktop ≥ 24, 4 GB RAM, 3 GB disk

```bash
unzip ims-phase8.zip && cd ims
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:5173 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

---

## Local Development

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env .env
uvicorn app.main:app --reload --port 8000

# Radis 
docker compose up redis -d

# Frontend (new terminal)
cd frontend && npm install && npm run dev
```

---

## Running Tests

```bash
cd backend && pytest tests/ -v
```

| Test file | Tests | Coverage |
|---|---|---|
| `test_phase2_ingestion.py` | 8 | Queue backpressure, schema, SQLite retry |
| `test_phase3_debounce.py` | 11 | Debounce logic, priority mapping, cache |
| `test_phase4_workflow.py` | 24 | State machine, alert strategies, RCA guard |
| `test_phase5_rca.py` | 18 | RCA schema, MTTR math, DB retry |
| `test_phase6_websocket.py` | 11 | WS lifecycle, Redis pub/sub, dead-conn pruning |
| **Total** | **72** | |

---

## Simulating Incidents

```bash
# Full cascading failure (RDBMS → API → Cache → Queue → MCP)
python mock_failure.py

# Seed 500 varied signals
python scripts/seed_signals.py

# 10 closed incidents with complete RCAs (fills MTTR charts)
python scripts/seed_closed_incidents.py

# Stress test: 2000 signals/sec for 30 seconds
python scripts/stress_test.py --rate 2000 --duration 30
```

---

## Backpressure Strategy

The IMS uses 4-layer backpressure to handle bursts up to 10,000 signals/sec without crashing:

**Layer 1 — Rate Limiter:** SlowAPI token bucket at the HTTP boundary (2000/min per IP). Returns `429` before hitting the queue.

**Layer 2 — asyncio.Queue (50K cap):** HTTP handler pushes via `put_nowait()` and returns `202` in microseconds. Returns `503 Queue Full` instead of blocking when the queue is saturated.

**Layer 3 — 4 Async Workers:** Concurrently drain the queue. SQLite writes (fast) and PostgreSQL writes (transactional) are independent — a slow PG write never stalls the audit log.

**Layer 4 — Redis Debounce (10s TTL):** 100 signals for `CACHE_CLUSTER_01` within 10 seconds create exactly 1 Work Item. Reduces PG write amplification up to 100×.

---

## Incident Lifecycle

```
Signal arrives → Work Item (OPEN, P0-P3)
    ↓
"Begin Investigation" → INVESTIGATING
    ↓ Alert dispatched (PagerDuty P0, Slack P1, Email P2)
Fix applied → "Mark Resolved" → RESOLVED
    ↓
Fill RCA form → Submit (MTTR auto-calculated)
    ↓
"Close Incident" → CLOSED  [blocked without complete RCA]
```

---

## Design Patterns

| Pattern | File | Purpose |
|---|---|---|
| **State** | `state_machine.py` | Each state owns its allowed transitions. `CLOSED` is terminal. |
| **Strategy** | `alert_strategy.py` | Swappable alert logic per component type. |
| **Producer-Consumer** | `signal_queue.py` + `signal_worker.py` | Decouples HTTP from DB write speed. |
| **Pub/Sub** | `ws_manager.py` | Redis fanout — broadcasts reach all WS clients across workers. |
| **Factory** | `AlertStrategyFactory` | One-line registration to add new alert channels. |
| **Repository** | `work_item_service.py` | DB access isolated with exponential retry. |

---

## API Reference

### Ingestion
| Method | Path | |
|---|---|---|
| `POST` | `/ingest` | Accept single signal (202 async) |
| `POST` | `/ingest/batch` | Accept up to 500 signals |
| `GET` | `/signals/recent` | Last N raw signals from SQLite |
| `WS` | `/ws/signals` | Live signal stream |

### Work Items
| Method | Path | |
|---|---|---|
| `GET` | `/work-items` | List (Redis-cached, sorted by priority) |
| `GET` | `/work-items/stats` | Counts by status and priority |
| `GET` | `/work-items/{id}` | Single work item |
| `GET` | `/work-items/{id}/signals` | Linked raw signals from SQLite |
| `GET` | `/work-items/{id}/transitions` | Allowed transitions |
| `PATCH` | `/work-items/{id}/transition` | Execute state transition |

### RCA
| Method | Path | |
|---|---|---|
| `POST` | `/work-items/{id}/rca` | Submit / re-submit RCA |
| `GET` | `/work-items/{id}/rca` | Fetch existing RCA |
| `GET` | `/rcas` | List all RCAs |

### Observability
| Method | Path | |
|---|---|---|
| `GET` | `/health` | Component health (PG + Redis + SQLite) |
| `GET` | `/metrics/full` | Full snapshot |
| `GET` | `/metrics/throughput` | 30-min per-minute history |
| `GET` | `/metrics/mttr` | MTTR by priority |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `ims_user` | PostgreSQL user |
| `POSTGRES_PASSWORD` | `ims_secret` | PostgreSQL password |
| `REDIS_PASSWORD` | `ims_redis_secret` | Redis password |
| `QUEUE_MAX_SIZE` | `50000` | asyncio.Queue cap |
| `WORKER_COUNT` | `4` | Async worker pool size |
| `DEBOUNCE_WINDOW_SECONDS` | `10` | Signal debounce window |
| `METRICS_INTERVAL_SECONDS` | `5` | Console metrics interval |

---

## Docker Commands

```bash
docker compose up --build      # Start everything
docker compose logs -f backend # Backend logs
docker compose restart backend # Hot reload backend
docker compose down            # Stop
docker compose down -v         # Stop + wipe all data
```
