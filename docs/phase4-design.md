# Phase 4: Workflow Engine — State & Strategy Patterns

## State Machine

```
              ┌─────────────────────────────┐
              │                             │
    ┌──────►OPEN──────────────────────────► INVESTIGATING
    │         ▲                  │               │
    │         │                  │               │
    │         │              (reopen)        (resolved)
    │         │                  │               │
    │         └──────────────────┘               ▼
    │                                        RESOLVED
    │                                            │
    │                                    (RCA required)
    │                                            │
    │                                            ▼
    └───────────────────────────────────────► CLOSED ⛔ (terminal)
```

### Rules enforced by State Machine
| From → To               | Allowed | Guard                           |
|-------------------------|---------|-------------------------------|
| OPEN → INVESTIGATING    | ✅      | none                           |
| INVESTIGATING → RESOLVED| ✅      | none                           |
| INVESTIGATING → OPEN    | ✅      | none (re-open)                 |
| RESOLVED → CLOSED       | ✅      | RCA must exist and be complete |
| RESOLVED → INVESTIGATING| ✅      | none (re-investigate)          |
| CLOSED → anything       | ❌      | Terminal state                 |
| OPEN → CLOSED           | ❌      | Not in allowed set             |
| OPEN → RESOLVED         | ❌      | Not in allowed set             |

## Strategy Pattern — Alert Routing

| Component Type | Priority | Channel    | Behavior                              |
|---------------|----------|-----------|---------------------------------------|
| RDBMS         | P0       | PagerDuty | Auto-page on-call, escalation policy  |
| MCP_HOST      | P0       | PagerDuty | Auto-page platform team               |
| API           | P1       | Slack     | Post to #incidents, @mention oncall   |
| QUEUE         | P1       | Slack     | Post to #incidents, @mention backend  |
| CACHE         | P2       | Email     | Email oncall list, 2hr SLA            |
| NOSQL         | P2       | Email     | Email oncall list                     |
| UNKNOWN       | P3       | Log       | Console log only                      |

Alert is dispatched when a Work Item transitions to **INVESTIGATING**.

### Adding a new alert strategy (Open/Closed principle)
```python
class MyNewStrategy(AlertStrategy):
    component_type = "MY_COMPONENT"
    priority = "P1"
    channel = "webhook"
    severity_label = "HIGH"

    def _compose_message(self, work_item): ...

# Register in factory:
AlertStrategyFactory._registry["MY_COMPONENT"] = MyNewStrategy()
```

## RCA Guard

The `RESOLVED → CLOSED` transition is rejected with HTTP 422 if:
- No RCA record exists for the Work Item
- `root_cause_description` is blank
- `fix_applied` is blank  
- `prevention_steps` is blank
- `incident_end` ≤ `incident_start`
