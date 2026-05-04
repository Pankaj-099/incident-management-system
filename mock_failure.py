#!/usr/bin/env python3
"""
mock_failure.py — Simulate a cascading failure scenario.

Scenario:
  1. RDBMS Primary goes down (P0)
  2. Connection pool exhausted causes API timeouts (P1)
  3. Cache miss spike as hot data expires (P2)
  4. Async queue backlog builds up (P1)
  5. MCP Host loses DB connectivity (P0)

Also demonstrates debounce: floods CACHE_CLUSTER_01 with 20 signals.

Usage:
    python mock_failure.py                      # default: http://localhost:8000
    python mock_failure.py --url http://host:8000
    python mock_failure.py --burst 50           # burst N signals to test debounce
"""

import asyncio
import argparse
import json
import uuid
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    raise

BASE_URL = "http://localhost:8000"

FAILURE_SEQUENCE = [
    # (delay_seconds, payload)
    (0.0, {
        "component_id": "RDBMS_PRIMARY",
        "component_type": "RDBMS",
        "severity": "CRITICAL",
        "message": "Connection refused: max_connections exceeded",
        "payload": {"error_code": "PGERR_TOO_MANY_CONNECTIONS", "active_connections": 500},
    }),
    (0.5, {
        "component_id": "RDBMS_PRIMARY",
        "component_type": "RDBMS",
        "severity": "CRITICAL",
        "message": "Primary health check failed: no response in 5s",
        "payload": {"timeout_ms": 5000},
    }),
    (1.0, {
        "component_id": "API_GATEWAY_01",
        "component_type": "API",
        "severity": "HIGH",
        "message": "Upstream DB timeout: query pool exhausted",
        "payload": {"pool_size": 20, "waiting_requests": 150},
    }),
    (1.5, {
        "component_id": "API_GATEWAY_02",
        "component_type": "API",
        "severity": "HIGH",
        "message": "Circuit breaker OPEN for /api/users route",
        "payload": {"error_rate_pct": 94.2},
    }),
    (2.0, {
        "component_id": "CACHE_CLUSTER_01",
        "component_type": "CACHE",
        "severity": "HIGH",
        "message": "Cache hit rate dropped below 10%: DB fallback overwhelmed",
        "payload": {"hit_rate_pct": 8.1, "eviction_rate": 12000},
    }),
    (2.5, {
        "component_id": "ASYNC_QUEUE_01",
        "component_type": "QUEUE",
        "severity": "MEDIUM",
        "message": "Queue backlog growing: consumers blocked on DB writes",
        "payload": {"queue_depth": 48200, "consumers_blocked": 8},
    }),
    (3.0, {
        "component_id": "MCP_HOST_02",
        "component_type": "MCP_HOST",
        "severity": "CRITICAL",
        "message": "MCP Host lost database connectivity — tool calls failing",
        "payload": {"failed_tool_calls": 320, "last_seen": datetime.now(timezone.utc).isoformat()},
    }),
    (3.5, {
        "component_id": "NOSQL_CLUSTER_01",
        "component_type": "NOSQL",
        "severity": "MEDIUM",
        "message": "Replication lag exceeding 30s on secondary nodes",
        "payload": {"lag_seconds": 34, "affected_nodes": ["node-2", "node-3"]},
    }),
]


async def send_signal(client: httpx.AsyncClient, payload: dict) -> dict:
    payload["signal_id"] = str(uuid.uuid4())
    resp = await client.post("/ingest", json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


async def run_scenario(base_url: str, burst: int = 0):
    print(f"\n🔥 Starting cascading failure simulation → {base_url}")
    print("=" * 60)

    async with httpx.AsyncClient(base_url=base_url) as client:

        # 1. Health check first
        try:
            r = await client.get("/health", timeout=5)
            health = r.json()
            print(f"✅ Backend status: {health['status']}")
        except Exception as e:
            print(f"❌ Cannot reach backend: {e}")
            return

        # 2. Fire the cascading failure sequence
        print("\n📡 Firing failure sequence...\n")
        for delay, payload in FAILURE_SEQUENCE:
            await asyncio.sleep(delay)
            try:
                result = await send_signal(client, payload.copy())
                print(
                    f"  [{payload['severity']:8s}] {payload['component_id']:22s} → "
                    f"signal={result['signal_id'][:8]}… queue={result['queue_depth']}"
                )
            except Exception as e:
                print(f"  [ERROR] {payload['component_id']}: {e}")

        # 3. Debounce burst test
        if burst > 0:
            print(f"\n🌊 Debounce test: sending {burst} signals for CACHE_CLUSTER_01...")
            tasks = [
                send_signal(client, {
                    "component_id": "CACHE_CLUSTER_01",
                    "component_type": "CACHE",
                    "severity": "HIGH",
                    "message": f"Cache timeout #{i+1}",
                })
                for i in range(burst)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            ok = sum(1 for r in results if isinstance(r, dict) and r.get("accepted"))
            print(f"  ✓ {ok}/{burst} signals accepted — debounce should collapse to 1 Work Item")

        print("\n✅ Simulation complete. Check the dashboard at http://localhost:5173")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IMS Failure Simulation")
    parser.add_argument("--url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--burst", type=int, default=20, help="Debounce burst count")
    args = parser.parse_args()

    asyncio.run(run_scenario(args.url, args.burst))
