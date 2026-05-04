#!/usr/bin/env python3
"""
seed_signals.py — Seed 500 varied signals across all component types.

Generates realistic signal data with varied severities and messages,
spread across all 6 component types. Great for testing the dashboard
with a realistic data set.

Usage:
    python scripts/seed_signals.py
    python scripts/seed_signals.py --url http://localhost:8000 --count 500
    python scripts/seed_signals.py --count 1000 --delay 0.002
"""

import asyncio
import argparse
import random
import uuid
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    raise

# ── Signal templates by component type ────────────────────────────────────────

SIGNAL_TEMPLATES = {
    "RDBMS": {
        "component_ids": ["RDBMS_PRIMARY", "RDBMS_REPLICA_01", "RDBMS_REPLICA_02"],
        "messages": [
            "Connection pool exhausted: {n} waiting requests",
            "Slow query detected: {n}ms execution time on table users",
            "Replication lag: {n}s behind primary",
            "Deadlock detected on transaction {tx}",
            "Max connections reached: {n}/{max} active",
            "Checkpoint taking longer than expected: {n}s",
            "Index bloat detected on orders table: {n}MB",
            "WAL accumulation rate exceeded threshold",
        ],
        "severities": ["CRITICAL", "CRITICAL", "HIGH", "HIGH", "MEDIUM"],
    },
    "CACHE": {
        "component_ids": ["CACHE_CLUSTER_01", "CACHE_CLUSTER_02", "CACHE_SHARD_A"],
        "messages": [
            "Cache hit rate dropped to {n}%",
            "Eviction rate spike: {n} keys/sec",
            "Memory utilization at {n}%",
            "Connection timeout to cache node after {n}ms",
            "Cache stampede detected on key 'user_session_{tx}'",
            "Replication failed to replica node-{n}",
        ],
        "severities": ["HIGH", "MEDIUM", "MEDIUM", "LOW", "LOW"],
    },
    "API": {
        "component_ids": ["API_GATEWAY_01", "API_GATEWAY_02", "AUTH_SERVICE", "PAYMENT_API"],
        "messages": [
            "P99 latency exceeded {n}ms on /api/orders",
            "Error rate spike: {n}% of requests returning 5xx",
            "Circuit breaker OPEN on downstream service after {n} failures",
            "Request queue depth: {n} pending",
            "SSL certificate expires in {n} days",
            "Rate limit enforced for client {tx}: {n} req/min",
            "Memory leak detected: heap growing {n}MB/hour",
        ],
        "severities": ["HIGH", "HIGH", "MEDIUM", "MEDIUM", "LOW"],
    },
    "QUEUE": {
        "component_ids": ["ASYNC_QUEUE_01", "EMAIL_QUEUE", "NOTIFICATION_QUEUE", "JOB_QUEUE"],
        "messages": [
            "Queue depth exceeds threshold: {n} messages backlogged",
            "Consumer lag: {n}s behind producer",
            "Dead letter queue growing: {n} failed messages",
            "Message processing rate dropped to {n}/sec",
            "Poison message detected in partition {n}",
        ],
        "severities": ["HIGH", "MEDIUM", "MEDIUM", "LOW", "LOW"],
    },
    "NOSQL": {
        "component_ids": ["NOSQL_CLUSTER_01", "DOCUMENT_STORE", "TIMESERIES_DB"],
        "messages": [
            "Replication lag on secondary nodes: {n}s",
            "Write concern timeout after {n}ms",
            "Disk usage at {n}% on shard-{tx}",
            "Index build consuming {n}% CPU",
            "Compaction falling behind write rate",
        ],
        "severities": ["MEDIUM", "MEDIUM", "LOW", "LOW", "INFO"],
    },
    "MCP_HOST": {
        "component_ids": ["MCP_HOST_01", "MCP_HOST_02", "MCP_ORCHESTRATOR"],
        "messages": [
            "Tool call timeout after {n}ms: database_query",
            "MCP host memory at {n}%: context window pressure",
            "Failed tool invocations: {n} in last 60s",
            "Context serialisation taking {n}ms",
            "MCP host connection pool at capacity: {n} active",
        ],
        "severities": ["CRITICAL", "HIGH", "HIGH", "MEDIUM", "MEDIUM"],
    },
}


def make_signal(component_type: str) -> dict:
    template = SIGNAL_TEMPLATES[component_type]
    component_id = random.choice(template["component_ids"])
    message_tmpl = random.choice(template["messages"])
    severity = random.choice(template["severities"])

    message = message_tmpl.format(
        n=random.randint(1, 9999),
        max=random.randint(100, 1000),
        tx=uuid.uuid4().hex[:6].upper(),
    )

    return {
        "signal_id": str(uuid.uuid4()),
        "component_id": component_id,
        "component_type": component_type,
        "severity": severity,
        "message": message,
        "payload": {
            "source": "seed_script",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


async def seed(base_url: str, count: int, delay: float, batch_size: int):
    component_types = list(SIGNAL_TEMPLATES.keys())
    sent = failed = 0

    print(f"\n🌱 Seeding {count} signals → {base_url}")
    print(f"   Batch size: {batch_size}  |  Delay: {delay}s between batches")
    print("=" * 60)

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        # Verify backend is up
        try:
            r = await client.get("/health")
            health = r.json()
            print(f"✅ Backend status: {health['status']}\n")
        except Exception as e:
            print(f"❌ Cannot reach backend at {base_url}: {e}")
            return

        # Send in batches
        for batch_start in range(0, count, batch_size):
            batch = [
                make_signal(component_types[i % len(component_types)])
                for i in range(batch_start, min(batch_start + batch_size, count))
            ]

            try:
                r = await client.post("/ingest/batch", json=batch)
                r.raise_for_status()
                result = r.json()
                sent += result.get("accepted", 0)
                failed += result.get("rejected", 0)

                progress = min(batch_start + batch_size, count)
                bar_len = 40
                filled = int(bar_len * progress / count)
                bar = "█" * filled + "░" * (bar_len - filled)
                print(f"\r  [{bar}] {progress}/{count}  accepted={sent}  rejected={failed}", end="")

            except Exception as e:
                failed += len(batch)
                print(f"\n  ⚠️  Batch failed: {e}")

            if delay > 0 and batch_start + batch_size < count:
                await asyncio.sleep(delay)

    print(f"\n\n✅ Seeding complete: {sent} accepted, {failed} failed")
    print(f"   Open http://localhost:5173 to see signals in the dashboard.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed IMS with signal data")
    parser.add_argument("--url",        default="http://localhost:8000")
    parser.add_argument("--count",      type=int,   default=500)
    parser.add_argument("--delay",      type=float, default=0.05, help="Seconds between batches")
    parser.add_argument("--batch-size", type=int,   default=50)
    args = parser.parse_args()

    asyncio.run(seed(args.url, args.count, args.delay, args.batch_size))
