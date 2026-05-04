#!/usr/bin/env python3
"""
seed_closed_incidents.py — Create 10 fully closed incidents with complete RCAs.

Each incident goes through the full lifecycle:
  Signal → Work Item (OPEN) → INVESTIGATING → RESOLVED → RCA → CLOSED

This populates the MTTR charts in the Observability page with real data.

Usage:
    python scripts/seed_closed_incidents.py
    python scripts/seed_closed_incidents.py --url http://localhost:8000 --count 10
"""

import asyncio
import argparse
import uuid
from datetime import datetime, timezone, timedelta
import random

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    raise

INCIDENTS = [
    {
        "component_id": "RDBMS_PRIMARY",
        "component_type": "RDBMS",
        "severity": "CRITICAL",
        "message": "Primary database connection pool exhausted — 500 waiting requests",
        "rca": {
            "root_cause_category": "CAPACITY_EXHAUSTION",
            "root_cause_description": "A batch job was inadvertently deployed to production that opened 450 long-running connections to the primary database without proper connection pooling. This exhausted the max_connections limit of 500, causing all application requests to queue up indefinitely.",
            "fix_applied": "Immediately terminated the rogue batch job. Increased PgBouncer pool size to 200 connections. Added connection timeout of 30s to all application DB clients. Rolled out emergency patch to batch job with proper connection pooling.",
            "prevention_steps": "Add connection count alerting at 70% utilisation. Enforce PgBouncer for all non-migration DB access. Add automated connection leak detection in CI. Require DB connection review for all batch jobs before production deployment.",
            "submitted_by": "db-oncall",
            "duration_hours": 1.5,
        },
    },
    {
        "component_id": "CACHE_CLUSTER_01",
        "component_type": "CACHE",
        "severity": "HIGH",
        "message": "Redis cache hit rate dropped to 8% — DB fallback overwhelmed",
        "rca": {
            "root_cause_category": "CONFIGURATION_ERROR",
            "root_cause_description": "A misconfigured deployment set the Redis TTL to 1 second instead of 3600 seconds for user session data. This caused near-constant cache misses, forcing every request to hit the database for session validation.",
            "fix_applied": "Rolled back the misconfigured TTL. Flushed and re-warmed the cache. Temporarily increased DB read replicas from 2 to 4 to absorb the fallback load during recovery.",
            "prevention_steps": "Add configuration validation tests that assert TTL values are within expected ranges. Implement canary deployment for cache config changes. Add cache hit rate to deployment smoke tests.",
            "submitted_by": "platform-team",
            "duration_hours": 0.75,
        },
    },
    {
        "component_id": "API_GATEWAY_01",
        "component_type": "API",
        "severity": "HIGH",
        "message": "Circuit breaker OPEN — P99 latency 8500ms on /api/orders",
        "rca": {
            "root_cause_category": "SOFTWARE_BUG",
            "root_cause_description": "A missing database index on the orders table caused full table scans on the most frequently accessed query path. The orders table had grown to 50M rows, making unindexed queries take 6-8 seconds. This was introduced by a schema migration that forgot to create the index.",
            "fix_applied": "Created the missing index using CREATE INDEX CONCURRENTLY to avoid locking. Verified query execution plan dropped from sequential scan to index scan. Circuit breaker recovered automatically once latency normalised.",
            "prevention_steps": "Add EXPLAIN ANALYSE checks to CI for all schema migrations. Add query latency regression tests. Implement slow query logging with automatic alerting at 500ms threshold.",
            "submitted_by": "backend-lead",
            "duration_hours": 2.0,
        },
    },
    {
        "component_id": "MCP_HOST_02",
        "component_type": "MCP_HOST",
        "severity": "CRITICAL",
        "message": "MCP host unresponsive — all tool calls failing with connection refused",
        "rca": {
            "root_cause_category": "HARDWARE_FAILURE",
            "root_cause_description": "The primary MCP host experienced a kernel panic due to memory corruption on one of its DIMM modules. The host became completely unresponsive, causing all tool calls routed to it to fail with connection refused errors.",
            "fix_applied": "Triggered automatic failover to MCP_HOST_01 and MCP_HOST_03. Replaced the faulty DIMM module. Ran full memory diagnostic before returning the host to service. Updated load balancer weights.",
            "prevention_steps": "Implement regular memory stress tests on all MCP hosts. Add ECC memory monitoring. Reduce single-host traffic to 33% max to limit blast radius. Test failover procedure quarterly.",
            "submitted_by": "infra-oncall",
            "duration_hours": 0.5,
        },
    },
    {
        "component_id": "ASYNC_QUEUE_01",
        "component_type": "QUEUE",
        "severity": "HIGH",
        "message": "Queue depth exceeded 80,000 messages — consumer throughput collapsed",
        "rca": {
            "root_cause_category": "DEPENDENCY_FAILURE",
            "root_cause_description": "Queue consumers were writing processed results to a downstream NoSQL store that had an elevated latency spike (30s+ writes). Consumers blocked waiting for write acknowledgement, causing throughput to collapse from 5000/s to 80/s and the queue to backlog.",
            "fix_applied": "Switched queue consumers to async fire-and-forget writes for non-critical results. Added a write timeout of 5s with dead-letter fallback. Scaled consumer instances from 4 to 12 to drain the backlog.",
            "prevention_steps": "Decouple queue consumers from downstream write latency using async patterns. Add consumer throughput monitoring with auto-scaling. Implement backpressure signalling between consumers and producers.",
            "submitted_by": "platform-team",
            "duration_hours": 3.0,
        },
    },
    {
        "component_id": "NOSQL_CLUSTER_01",
        "component_type": "NOSQL",
        "severity": "MEDIUM",
        "message": "Secondary node replication lag: 45 seconds behind primary",
        "rca": {
            "root_cause_category": "CAPACITY_EXHAUSTION",
            "root_cause_description": "A bulk import operation of 20M documents via the primary node saturated the replication oplog, causing secondaries to fall behind. The oplog size was configured at 1GB, which was insufficient for the import volume.",
            "fix_applied": "Throttled the bulk import to 10k documents/batch with 500ms sleep between batches. Increased oplog size to 10GB. Waited for replication to catch up before resuming import.",
            "prevention_steps": "Always route bulk imports through a dedicated import replica that does not feed replication. Set oplog size to at least 10GB. Add replication lag alerting at 10s threshold.",
            "submitted_by": "data-team",
            "duration_hours": 1.25,
        },
    },
    {
        "component_id": "AUTH_SERVICE",
        "component_type": "API",
        "severity": "CRITICAL",
        "message": "Authentication service returning 503 — JWT validation failing for all users",
        "rca": {
            "root_cause_category": "CONFIGURATION_ERROR",
            "root_cause_description": "An automated certificate rotation job rotated the JWT signing key but failed to distribute the new public key to all auth service replicas. Three of six replicas continued using the old public key, causing intermittent 503s that became consistent as load balancer routing changed.",
            "fix_applied": "Manually pushed the new public key to all replicas. Restarted the affected replicas. Added health check that validates JWT key consistency across replicas.",
            "prevention_steps": "Implement blue-green key rotation with validation step before cutover. Add JWT validation health check endpoint. Monitor for auth error rate spikes during any certificate rotation.",
            "submitted_by": "security-team",
            "duration_hours": 0.33,
        },
    },
    {
        "component_id": "PAYMENT_API",
        "component_type": "API",
        "severity": "HIGH",
        "message": "Payment API timeout rate 42% — Stripe webhook processing backlogged",
        "rca": {
            "root_cause_category": "SOFTWARE_BUG",
            "root_cause_description": "A webhook handler for Stripe events was implemented synchronously in the main request thread. Under high transaction volume, the handler blocked the event loop while making outbound HTTP calls to our internal inventory service, causing timeouts to cascade.",
            "fix_applied": "Moved webhook processing to an async background task queue. Added idempotency keys to prevent double-processing during replay. Deployed fix to production with immediate relief.",
            "prevention_steps": "Mandate async processing for all third-party webhook handlers. Add webhook processing time to performance tests. Implement webhook replay testing in staging.",
            "submitted_by": "payments-team",
            "duration_hours": 4.0,
        },
    },
    {
        "component_id": "RDBMS_REPLICA_01",
        "component_type": "RDBMS",
        "severity": "MEDIUM",
        "message": "Read replica falling behind primary: 120s replication lag",
        "rca": {
            "root_cause_category": "HUMAN_ERROR",
            "root_cause_description": "An engineer accidentally ran VACUUM FULL on the replica instead of the primary. VACUUM FULL acquires an exclusive lock on tables and takes significantly longer than a standard VACUUM. This blocked replication from applying new WAL records for 35 minutes.",
            "fix_applied": "Killed the VACUUM FULL process. Monitored replication lag as it recovered to <1s. Added runbook note that VACUUM FULL should never be run on replicas.",
            "prevention_steps": "Add IAM policies to prevent VACUUM FULL on replicas. Require peer review for any manual DB maintenance commands. Add VACUUM FULL detection to database monitoring.",
            "submitted_by": "db-oncall",
            "duration_hours": 0.6,
        },
    },
    {
        "component_id": "EMAIL_QUEUE",
        "component_type": "QUEUE",
        "severity": "MEDIUM",
        "message": "Email delivery queue backlog: 15,000 undelivered messages",
        "rca": {
            "root_cause_category": "DEPENDENCY_FAILURE",
            "root_cause_description": "The third-party email provider (SendGrid) experienced a regional outage affecting EU endpoints. Our retry logic used exponential backoff but did not implement a maximum retry count, causing workers to retry indefinitely and block new messages from being processed.",
            "fix_applied": "Added maximum retry count of 5 with dead-letter queue for failed messages. Implemented secondary email provider fallback (AWS SES) for critical transactional emails. Drained backlog over 2 hours once SendGrid recovered.",
            "prevention_steps": "Always implement maximum retry counts. Add dead-letter queue monitoring. Configure multi-provider email routing for critical paths. Add SendGrid status page to incident monitoring.",
            "submitted_by": "platform-team",
            "duration_hours": 2.5,
        },
    },
]


async def create_closed_incident(client: httpx.AsyncClient, incident: dict, index: int) -> bool:
    rca_data = incident["rca"]
    duration = rca_data["duration_hours"]

    # Use a past time so MTTR is realistic
    hours_ago = random.randint(1, 72)
    incident_start = datetime.now(timezone.utc) - timedelta(hours=hours_ago + duration)
    incident_end   = incident_start + timedelta(hours=duration)

    print(f"\n  [{index+1}/10] Creating: {incident['component_id']} ({incident['component_type']})")

    try:
        # 1. Send signal
        sig_r = await client.post("/ingest", json={
            "signal_id": str(uuid.uuid4()),
            "component_id": incident["component_id"],
            "component_type": incident["component_type"],
            "severity": incident["severity"],
            "message": incident["message"],
        })
        sig_r.raise_for_status()
        print(f"     ✓ Signal ingested")

        # Wait for debounce to create Work Item
        await asyncio.sleep(1.0)

        # 2. Find the Work Item
        wi_r = await client.get(f"/work-items?status=OPEN&limit=200")
        wi_r.raise_for_status()
        items = wi_r.json().get("items", [])
        wi = next(
            (w for w in items if w["component_id"] == incident["component_id"]),
            None
        )
        if not wi:
            print(f"     ⚠️  Work Item not found for {incident['component_id']} — skipping")
            return False

        wi_id = wi["id"]
        print(f"     ✓ Work Item: {wi_id[:8]}… [{wi['priority']}]")

        # 3. Transition → INVESTIGATING
        t1 = await client.patch(f"/work-items/{wi_id}/transition",
                                json={"status": "INVESTIGATING", "actor": "seed-script"})
        t1.raise_for_status()
        print(f"     ✓ OPEN → INVESTIGATING")

        # 4. Transition → RESOLVED
        t2 = await client.patch(f"/work-items/{wi_id}/transition",
                                json={"status": "RESOLVED", "actor": "seed-script"})
        t2.raise_for_status()
        print(f"     ✓ INVESTIGATING → RESOLVED")

        # 5. Submit RCA
        rca_payload = {
            "incident_start": incident_start.isoformat(),
            "incident_end":   incident_end.isoformat(),
            "root_cause_category":    rca_data["root_cause_category"],
            "root_cause_description": rca_data["root_cause_description"],
            "fix_applied":            rca_data["fix_applied"],
            "prevention_steps":       rca_data["prevention_steps"],
            "submitted_by":           rca_data.get("submitted_by", "seed-script"),
        }
        rca_r = await client.post(f"/work-items/{wi_id}/rca", json=rca_payload)
        rca_r.raise_for_status()
        rca_result = rca_r.json()
        mttr_min = rca_result.get("mttr_minutes", 0)
        print(f"     ✓ RCA submitted — MTTR: {mttr_min} minutes")

        # 6. Transition → CLOSED
        t3 = await client.patch(f"/work-items/{wi_id}/transition",
                                json={"status": "CLOSED", "actor": "seed-script"})
        t3.raise_for_status()
        print(f"     ✓ RESOLVED → CLOSED ✅")

        return True

    except Exception as e:
        print(f"     ❌ Failed: {e}")
        return False


async def run(base_url: str, count: int):
    print(f"\n🌱 Seeding {count} closed incidents with RCAs → {base_url}")
    print("=" * 60)

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        try:
            r = await client.get("/health")
            print(f"✅ Backend status: {r.json()['status']}\n")
        except Exception as e:
            print(f"❌ Cannot reach backend: {e}")
            return

        success = 0
        for i, incident in enumerate(INCIDENTS[:count]):
            if await create_closed_incident(client, incident, i):
                success += 1
            await asyncio.sleep(0.5)

    print(f"\n\n✅ Done: {success}/{count} incidents created and closed.")
    print(f"   Open http://localhost:5173/observability to see MTTR charts.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",   default="http://localhost:8000")
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(run(args.url, min(args.count, len(INCIDENTS))))
