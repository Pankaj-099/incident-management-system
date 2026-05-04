# Phase 3: Debounce Engine & Work Item Creation

## Debounce Algorithm

```
Signal arrives for COMPONENT_ID
         │
         ▼
GET redis key "debounce:{COMPONENT_ID}"
         │
    ┌────┴────┐
  EXISTS    MISSING
    │           │
    │           ▼
    │    SET lock "debounce:lock:{COMPONENT_ID}" NX EX 30
    │           │
    │    ┌──────┴──────┐
    │  LOCK OK      LOCK FAIL
    │    │              │
    │    │           WAIT 50ms × 20 retries
    │    │           (poll for debounce key)
    │    │
    │    ▼
    │  CREATE WorkItem in PostgreSQL (transactional)
    │  SET "debounce:{COMPONENT_ID}" = work_item_id EX 10
    │  DELETE lock key
    │
    ▼
UPDATE raw_signals SET work_item_id = ? (SQLite)
INCREMENT work_item.signal_count (PostgreSQL)
BROADCAST ws event
```

## Race Condition Prevention

Multiple workers processing signals for the same component simultaneously
is handled by a Redis distributed lock (`NX` flag = only set if not exists).

Only one worker will win the lock → create the Work Item → release.
All other workers spin-wait on the debounce key (max 1 second), then
fold their signal into the now-existing Work Item.

## Transactional Guarantee

Work Item creation in PostgreSQL uses SQLAlchemy's async session with
`flush()` + `commit()` to ensure atomicity. If the commit fails, no
partial state is left — the debounce key is only set in Redis **after**
a successful commit, so the next signal will retry creation.

## Redis Hot-Path Cache

```
GET /work-items → Redis GET "cache:dashboard:work_items"
                         │
                    ┌────┴────┐
                  HIT       MISS
                    │           │
                  return    PostgreSQL query
                  cached    → SET cache (TTL 10s)
                            → return result
```

Cache is invalidated immediately on any Work Item creation or mutation.
