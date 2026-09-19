#!/usr/bin/env python3
"""Load test the screenshot tool endpoints."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class RequestResult:
    ok: bool
    status_code: int | None
    elapsed_ms: float
    error: str | None
    success_field: bool | None
    action: str | None


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


def build_payload(mode: str, target_url: str, include_screenshot_base64: bool) -> dict[str, Any]:
    if mode == "burp":
        return {
            "params": {
                "request_data": "GET /api/test HTTP/1.1\nHost: example.com\nUser-Agent: VulnVerify\n\n",
                "response_data": "HTTP/1.1 200 OK\nContent-Type: application/json\n\n{\"status\":\"ok\",\"message\":\"hello\"}",
                "request_highlights": ["GET", "/api/test"],
                "response_highlights": ["200 OK", "status"],
                "width": 1600,
                "height": 900,
                "elapsed_ms": 123,
                "include_screenshot_base64": include_screenshot_base64,
            }
        }

    return {
        "params": {
            "url": target_url,
            "method": "GET",
            "loading_strategy": "none",
            "sleep_time": 0,
            "window_size": "1600,900",
            "include_screenshot_base64": include_screenshot_base64,
        }
    }


async def send_once(
    client: httpx.AsyncClient,
    api_url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> RequestResult:
    started_at = time.perf_counter()
    try:
        response = await client.post(api_url, headers=headers, json=payload)
        elapsed_ms = (time.perf_counter() - started_at) * 1000

        success_field = None
        action = None
        error = None
        try:
            data = response.json()
            success_field = data.get("success")
            action = data.get("action")
            if response.status_code != 200:
                error = str(data)
            elif success_field is False:
                error = str(data.get("error"))
        except Exception:
            if response.status_code != 200:
                error = response.text[:200]

        ok = response.status_code == 200 and success_field is not False
        if not ok and error is None:
            error = f"unexpected status {response.status_code}"

        return RequestResult(
            ok=ok,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            error=error,
            success_field=success_field,
            action=action,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        return RequestResult(
            ok=False,
            status_code=None,
            elapsed_ms=elapsed_ms,
            error=str(exc),
            success_field=None,
            action=None,
        )


async def worker(
    queue: asyncio.Queue[int],
    client: httpx.AsyncClient,
    api_url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    interval: float,
    results: list[RequestResult],
) -> None:
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return

        result = await send_once(client, api_url, headers, payload)
        results.append(result)
        if interval > 0:
            await asyncio.sleep(interval)
        queue.task_done()


def summarize(results: list[RequestResult]) -> dict[str, Any]:
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

    summary: dict[str, Any] = {
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

    slowest_requests = sorted(results, key=lambda item: item.elapsed_ms, reverse=True)[:5]
    if slowest_requests:
        summary["slowest_requests"] = [
            {
                "elapsed_ms": round(item.elapsed_ms, 2),
                "status_code": item.status_code,
                "ok": item.ok,
                "error": item.error,
                "success_field": item.success_field,
                "action": item.action,
            }
            for item in slowest_requests
        ]

    return summary


def format_summary(summary: dict[str, Any]) -> str:
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
    parser = argparse.ArgumentParser(description="Load test the screenshot tool endpoints")
    parser.add_argument("--base-url", default="http://localhost:8001", help="Base URL of the service")
    parser.add_argument("--token", default="unified-tools-token-12345", help="Bearer token")
    parser.add_argument("--mode", choices=["burp", "web"], default="burp", help="Screenshot mode")
    parser.add_argument("--target-url", default="http://localhost:8001/health", help="Target URL used by web mode")
    parser.add_argument("--requests", type=int, default=50, help="Total number of requests")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent workers")
    parser.add_argument("--timeout", type=float, default=60.0, help="Per-request timeout in seconds")
    parser.add_argument("--interval", type=float, default=0.0, help="Sleep interval between requests per worker")
    parser.add_argument(
        "--include-screenshot-base64",
        action="store_true",
        help="Include base64 screenshot in the response payload validation path",
    )
    parser.add_argument("--json", action="store_true", help="Output summary as JSON")
    args = parser.parse_args()

    if args.requests <= 0:
        raise ValueError("--requests must be greater than 0")
    if args.concurrency <= 0:
        raise ValueError("--concurrency must be greater than 0")

    action = "burp_screenshot" if args.mode == "burp" else "web_screenshot"
    api_url = f"{args.base_url.rstrip('/')}/execute/screenshot/{action}"
    payload = build_payload(args.mode, args.target_url, args.include_screenshot_base64)
    headers = {
        "Authorization": f"Bearer {args.token}",
        "Content-Type": "application/json",
    }

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
                    queue=queue,
                    client=client,
                    api_url=api_url,
                    headers=headers,
                    payload=payload,
                    interval=args.interval,
                    results=results,
                )
            )
            for _ in range(min(args.concurrency, args.requests))
        ]
        await asyncio.gather(*tasks)

    total_elapsed = time.perf_counter() - started_at
    throughput = len(results) / total_elapsed if total_elapsed > 0 else 0.0
    summary = summarize(results)
    summary["base_url"] = args.base_url
    summary["api_url"] = api_url
    summary["mode"] = args.mode
    summary["duration_seconds"] = f"{total_elapsed:.2f}"
    summary["throughput_rps"] = f"{throughput:.2f}"

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"base_url={args.base_url}")
        print(f"api_url={api_url}")
        print(f"mode={args.mode}")
        print(f"duration_seconds={summary['duration_seconds']}")
        print(f"throughput_rps={summary['throughput_rps']}")
        print(format_summary(summary))

    return 0 if all(item.ok for item in results) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
