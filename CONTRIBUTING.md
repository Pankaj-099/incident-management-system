# Contributing & Extending the IMS

## Adding a new Alert Strategy

1. Subclass `AlertStrategy` in `backend/app/services/alert_strategy.py`:

```python
class MyWebhookStrategy(AlertStrategy):
    component_type = "MY_COMPONENT"
    priority = "P1"
    channel = "webhook"
    severity_label = "HIGH"

    def _compose_message(self, work_item: "WorkItem") -> str:
        return f"Incident: {work_item.title}"

    async def dispatch(self, alert: Alert) -> None:
        async with httpx.AsyncClient() as client:
            await client.post("https://hooks.example.com/incident", json=alert.__dict__)
```

2. Register it in the factory (same file):

```python
AlertStrategyFactory._registry["MY_COMPONENT"] = MyWebhookStrategy()
```

That's it. The factory picks it up at runtime.

---

## Adding a new Work Item State

1. Subclass `WorkItemStateBase` in `backend/app/services/state_machine.py`:

```python
class EscalatedState(WorkItemStateBase):
    name = "ESCALATED"
    allowed_transitions = {"INVESTIGATING", "CLOSED"}

    def on_enter(self, work_item):
        super().on_enter(work_item)
        work_item.escalated_at = datetime.now(timezone.utc)
```

2. Register it in `_STATE_REGISTRY`:

```python
_STATE_REGISTRY["ESCALATED"] = EscalatedState()
```

3. Add it to the `WorkItemStatus` enum in `models/work_item.py`
4. Add a new Alembic migration to update the enum in PostgreSQL

---

## Adding a new API endpoint

```python
# backend/app/api/my_endpoint.py
from fastapi import APIRouter
router = APIRouter(tags=["my-feature"])

@router.get("/my-endpoint")
async def my_endpoint():
    return {"hello": "world"}
```

Register in `backend/app/api/__init__.py`:

```python
from app.api.my_endpoint import router as my_router
api_router.include_router(my_router)
```

---

## Running a single test file

```bash
cd backend
pytest tests/test_phase4_workflow.py -v
```

## Running with coverage

```bash
pip install pytest-cov
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html
```

---

## Swapping SQLite for MongoDB

1. Replace `backend/app/db/sqlite.py` with a MongoDB connection using `motor`
2. Update `backend/app/services/sqlite_sink.py` to use Motor async operations
3. Keep the same function signatures — callers don't change

---

## Swapping asyncio.Queue for Kafka

1. Update `backend/app/services/signal_queue.py`:
   - Replace `asyncio.Queue` with an `aiokafka.AIOKafkaProducer`
   - `enqueue_signal()` calls `await producer.send(topic, signal_bytes)`
2. Update `backend/app/workers/signal_worker.py`:
   - Replace the `queue.get()` loop with an `AIOKafkaConsumer` group
3. Docker Compose: add Kafka + Zookeeper services

The rest of the system is unchanged — the debounce engine, workflow engine, and API layer don't know how signals arrived.
