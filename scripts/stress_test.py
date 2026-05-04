#!/usr/bin/env python3
"""
stress_test.py — High-throughput stress tester for the IMS ingestion pipeline.

Measures actual throughput, tracks accept/reject rates, and prints
a live rate counter while the test runs.

Usage:
    python scripts/stress_test.py
    python scripts/stress_test.py --rate 2000 --duration 30
    python scripts/stress_test.py --rate 5000 --duration 60 --workers 20
"""

import asyncio
import argparse
import time
import uuid
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    raise

COMPONENT_TYPES = ["RDBMS", "CACHE", "API", "QUEUE", "NOSQL", "MCP_HOST"]
SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
COMPONENT_IDS = [
    "RDBMS_PRIMARY", "CACHE_CLUSTER_01", "API_GATEWAY_01",
    "ASYNC_QUEUE_01", "NOSQL_CLUSTER_01", "MCP_HOST_02",
]


@dataclass
class Stats:
    sent: int = 0
    accepted: int = 0
    rejected: int = 0
    errors: int = 0
    start_time: float = field(default_factory=time.time)

    def elapsed(self) -> float:
        return time.time() - self.start_time

    def rate(self) -> float:
        e = self.elapsed()
        return self.accepted / e if e > 0 else 0


def make_signal() -> dict:
    return {
        "signal_id":      str(uuid.uuid4()),
        "component_id":   random.choice(COMPONENT_IDS),
        "component_type": random.choice(COMPONENT_TYPES),
        "severity":       random.choice(SEVERITIES),
        "message":        f"Stress test signal {uuid.uuid4().hex[:8]} at {time.time():.3f}",
        "payload":        {"stress_test": True, "ts": datetime.now(timezone.utc).isoformat()},
    }


async def worker(
    client: httpx.AsyncClient,
    stats: Stats,
    rate_limit: float,       # target signals per second per worker
    stop_event: asyncio.Event,
):
    interval = 1.0 / rate_limit if rate_limit > 0 else 0

    while not stop_event.is_set():
        start = time.monotonic()
        try:
            r = await client.post("/ingest", json=make_signal(), timeout=5)
            if r.status_code == 202:
                stats.accepted += 1
            elif r.status_code == 503:
                stats.rejected += 1
            else:
                stats.errors += 1
            stats.sent += 1
        except Exception:
            stats.errors += 1

        # Pace to hit target rate
        elapsed = time.monotonic() - start
        sleep = interval - elapsed
        if sleep > 0:
            await asyncio.sleep(sleep)


async def run(base_url: str, target_rate: int, duration: int, num_workers: int):
    print(f"\n⚡ IMS Stress Test")
    print(f"   Target: {target_rate:,} signals/sec | Duration: {duration}s | Workers: {num_workers}")
    print(f"   Backend: {base_url}")
    print("=" * 60)

    async with httpx.AsyncClient(base_url=base_url, limits=httpx.Limits(
        max_connections=num_workers + 10,
        max_keepalive_connections=num_workers,
    )) as client:
        # Health check
        try:
            r = await client.get("/health", timeout=5)
            print(f"✅ Backend: {r.json()['status']}\n")
        except Exception as e:
            print(f"❌ Cannot reach backend: {e}")
            return

        stats = Stats()
        stop_event = asyncio.Event()

        # Per-worker rate
        per_worker_rate = target_rate / num_workers

        # Start workers
        tasks = [
            asyncio.create_task(worker(client, stats, per_worker_rate, stop_event))
            for _ in range(num_workers)
        ]

        # Progress reporter
        async def reporter():
            last_accepted = 0
            while not stop_event.is_set():
                await asyncio.sleep(1.0)
                window_rate = stats.accepted - last_accepted
                last_accepted = stats.accepted
                elapsed = stats.elapsed()
                avg_rate = stats.rate()

                # Progress bar
                pct = min(elapsed / duration, 1.0)
                bar_len = 30
                filled = int(bar_len * pct)
                bar = "█" * filled + "░" * (bar_len - filled)

                reject_pct = stats.rejected / max(stats.sent, 1) * 100
                print(
                    f"\r  [{bar}] {elapsed:.0f}/{duration}s  "
                    f"rate={window_rate}/s  avg={avg_rate:.0f}/s  "
                    f"sent={stats.sent:,}  rejected={reject_pct:.1f}%  errors={stats.errors}",
                    end=""
                )

        reporter_task = asyncio.create_task(reporter())

        # Run for duration
        await asyncio.sleep(duration)
        stop_event.set()
        reporter_task.cancel()

        # Cancel workers
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = stats.elapsed()
        avg_rate = stats.rate()
        reject_pct = stats.rejected / max(stats.sent, 1) * 100

        print(f"\n\n{'=' * 60}")
        print(f"📊 STRESS TEST RESULTS")
        print(f"{'=' * 60}")
        print(f"  Duration:       {elapsed:.1f}s")
        print(f"  Total sent:     {stats.sent:,}")
        print(f"  Accepted:       {stats.accepted:,}")
        print(f"  Rejected (503): {stats.rejected:,}  ({reject_pct:.1f}%)")
        print(f"  Errors:         {stats.errors}")
        print(f"  Avg throughput: {avg_rate:,.0f} signals/sec")
        print(f"  Target rate:    {target_rate:,} signals/sec")
        print(f"  Achieved:       {avg_rate/target_rate*100:.1f}% of target")

        if reject_pct > 10:
            print(f"\n  ⚠️  High rejection rate ({reject_pct:.1f}%) — queue is saturating.")
            print(f"      Try reducing --rate or increase QUEUE_MAX_SIZE in .env")
        elif avg_rate >= target_rate * 0.95:
            print(f"\n  ✅ Throughput target met!")
        else:
            print(f"\n  ℹ️  Throughput below target — consider increasing --workers")

        # Check queue stats
        try:
            m = await client.get("/metrics")
            data = m.json()
            print(f"\n  Queue depth after test: {data.get('queue_depth_live', '?')}")
            print(f"  Total signals ingested: {data.get('signals_total', '?')}")
        except Exception:
            pass

        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IMS Stress Tester")
    parser.add_argument("--url",      default="http://localhost:8000")
    parser.add_argument("--rate",     type=int, default=2000, help="Target signals/sec")
    parser.add_argument("--duration", type=int, default=30,   help="Test duration in seconds")
    parser.add_argument("--workers",  type=int, default=10,   help="Concurrent async workers")
    args = parser.parse_args()

    asyncio.run(run(args.url, args.rate, args.duration, args.workers))
