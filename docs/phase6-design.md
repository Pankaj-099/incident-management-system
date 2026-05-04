# Phase 6: WebSocket Architecture & Real-Time Sync

## Redis Pub/Sub Fanout

### Problem with Phase 2
In Phase 2, the `ConnectionManager` held WebSocket connections in an in-process `set`.
Broadcasting from Worker A would NOT reach clients connected to Worker B.

### Phase 6 Solution

```
Service calls ws_manager.broadcast("signal", {...})
              │
              ▼
      Redis PUBLISH "ims:events"
              │
    ┌─────────┼──────────┐
    ▼         ▼          ▼
 Worker A   Worker B   Worker C
(pubsub     (pubsub     (pubsub
 listener)   listener)   listener)
    │         │          │
    ▼         ▼          ▼
  Local    Local       Local
  WS Conns  WS Conns   WS Conns
```

Every worker process subscribes to `ims:events` via a persistent asyncio
coroutine (`_pubsub_listener`). When Redis delivers a message, each worker
fans it out to its local WebSocket connections.

**Redis unavailable fallback**: if `redis.publish()` raises, broadcast falls
back to local-only delivery so the system degrades gracefully.

## Heartbeat Protocol

```
Server → Client: { "type": "ping", "data": { "ts": "..." } }
Client → Server: { "type": "pong", "ts": "..." }
```

- Server pings every 30 seconds
- Dead connections (send raises) are pruned automatically
- Client hook auto-reconnects with exponential backoff (1s → 30s cap, max 15 attempts)

## Frontend Event Bus Architecture

```
useRealtimeEvents (root hook, one WebSocket connection per page)
    │
    ├─── onSignal         → SignalFeed (via props)
    ├─── onWorkItemCreated → WorkItemList (via props) + Toast
    └─── onWorkItemUpdated → WorkItemList (via props) + Toast (on CLOSED/RESOLVED)

Only ONE WebSocket connection is maintained per browser tab (at DashboardPage level).
All child components receive updates via React props — no duplicate connections.
```

## Client Reconnection Strategy

| Attempt | Delay      |
|---------|-----------|
| 1       | ~1s        |
| 2       | ~1.5s      |
| 3       | ~2.25s     |
| 5       | ~5s        |
| 10      | ~17s       |
| 15      | 30s (cap)  |

After 15 failed attempts, reconnection stops. User must refresh.

## Event Types

| Event               | Trigger                        | Toast?                |
|---------------------|--------------------------------|-----------------------|
| `connected`         | WS accept                      | No (sets client_id)   |
| `ping`              | Every 30s from server          | No (auto-pong)        |
| `signal`            | Every ingested signal          | Only on CRITICAL      |
| `work_item_created` | New WI from debounce engine    | Yes (priority-coded)  |
| `work_item_updated` | State transition               | Yes (RESOLVED/CLOSED) |
