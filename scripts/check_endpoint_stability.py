#!/usr/bin/env python3
"""Check endpoint reachability and basic stability metrics."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class RequestResult:
    ok: bool
    status_code: Optional[int]
    elapsed_ms: float
    error: Optional[str]


async def fetch_once(
    client: httpx.AsyncClient,
    url: str,
    expected_status: int,
) -> RequestResult:
    start = time.perf_counter()
    try:
        response = await client.get(url)
        elapsed_ms = (time.perf_counter() - start) * 1000
        ok = response.status_code == expected_status
        error = None if ok else f"unexpected status {response.status_code}"
        return RequestResult(
            ok=ok,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            error=error,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return RequestResult(
            ok=False,
            status_code=None,
            elapsed_ms=elapsed_ms,
            error=str(exc),
        )


async def worker(
    name: str,
    queue: asyncio.Queue[int],
    client: httpx.AsyncClient,
    url: str,
    expected_status: int,
    interval: float,
    results: list[RequestResult],
) -> None:
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return

        result = await fetch_once(client, url, expected_status)
        results.append(result)
        if interval > 0:
            await asyncio.sleep(interval)
        queue.task_done()


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize(results: list[RequestResult]) -> dict[str, object]:
    latencies = [item.elapsed_ms for item in results]
    successes = sum(1 for item in results if item.ok)
    failures = len(results) - successes
    success_rate = (successes / len(results) * 100) if results else 0.0
    status_counts = Counter(
        str(item.status_code) if item.status_code is not None else "error"
        for item in results
    )
    error_counts = Counter(
        item.error.strip() if item.error and item.error.strip() else "unknown_error"
        for item in results
        if item.error is not None
    )

    summary: dict[str, object] = {
        "total_requests": len(results),
        "successes": successes,
        "failures": failures,
        "success_rate": f"{success_rate:.2f}%",
        "latency_min_ms": f"{min(latencies):.2f}" if latencies else "0.00",
        "latency_avg_ms": f"{statistics.mean(latencies):.2f}" if latencies else "0.00",
        "latency_p95_ms": f"{percentile(latencies, 0.95):.2f}" if latencies else "0.00",
        "latency_max_ms": f"{max(latencies):.2f}" if latencies else "0.00",
        "status_counts": dict(status_counts),
        "error_type_counts": dict(error_counts),
    }

    if error_counts:
        summary["top_errors"] = [
            {"error": error, "count": count}
            for error, count in error_counts.most_common(5)
        ]

    slowest_results = sorted(results, key=lambda item: item.elapsed_ms, reverse=True)[:5]
    if slowest_results:
        summary["slowest_requests"] = [
            {
                "elapsed_ms": round(item.elapsed_ms, 2),
                "status_code": item.status_code,
                "ok": item.ok,
                "error": item.error,
            }
            for item in slowest_results
        ]

    return summary


def format_summary(summary: dict[str, object]) -> str:
    lines = [
        f"total_requests={summary['total_requests']}",
        f"successes={summary['successes']}",
        f"failures={summary['failures']}",
        f"success_rate={summary['success_rate']}",
        f"latency_min_ms={summary['latency_min_ms']}",
        f"latency_avg_ms={summary['latency_avg_ms']}",
        f"latency_p95_ms={summary['latency_p95_ms']}",
        f"latency_max_ms={summary['latency_max_ms']}",
        f"status_counts={summary['status_counts']}",
    ]

    error_type_counts = summary.get("error_type_counts")
    if error_type_counts:
        lines.append(f"error_type_counts={error_type_counts}")

    top_errors = summary.get("top_errors")
    if top_errors:
        lines.append(f"top_errors={top_errors}")

    slowest_requests = summary.get("slowest_requests")
    if slowest_requests:
        lines.append(f"slowest_requests={slowest_requests}")

    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description="HTTP endpoint stability checker")
    parser.add_argument(
        "--url",
        default="http://203.0.113.10:8883/",
        help="Target URL to test",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        help="Total number of requests",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Concurrent workers",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.0,
        help="Sleep interval between requests per worker",
    )
    parser.add_argument(
        "--expected-status",
        type=int,
        default=200,
        help="Expected HTTP status code",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the summary as JSON",
    )
    args = parser.parse_args()

    if args.requests <= 0:
        raise ValueError("--requests must be greater than 0")
    if args.concurrency <= 0:
        raise ValueError("--concurrency must be greater than 0")

    queue: asyncio.Queue[int] = asyncio.Queue()
    for index in range(args.requests):
        queue.put_nowait(index)

    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    timeout = httpx.Timeout(args.timeout)
    results: list[RequestResult] = []

    started_at = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=True) as client:
        tasks = [
            asyncio.create_task(
                worker(
                    name=f"worker-{index}",
                    queue=queue,
                    client=client,
                    url=args.url,
                    expected_status=args.expected_status,
                    interval=args.interval,
                    results=results,
                )
            )
            for index in range(min(args.concurrency, args.requests))
        ]
        await asyncio.gather(*tasks)

    total_elapsed = time.perf_counter() - started_at
    throughput = len(results) / total_elapsed if total_elapsed > 0 else 0.0

    summary = summarize(results)
    output: dict[str, object] = {
        "url": args.url,
        "duration_seconds": round(total_elapsed, 2),
        "throughput_rps": round(throughput, 2),
        **summary,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"url={args.url}")
        print(f"duration_seconds={total_elapsed:.2f}")
        print(f"throughput_rps={throughput:.2f}")
        print(format_summary(summary))

    return 0 if all(item.ok for item in results) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
