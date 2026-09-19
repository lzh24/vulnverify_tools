#!/usr/bin/env python3
"""批量检测多个 IP 的 8883 端口是否提供 HTTP 服务。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

import httpx

# 示例 IP，使用时替换为你的集群节点地址
DEFAULT_IPS = [
    "192.0.2.10",
    "192.0.2.11",
    "192.0.2.12",
    "192.0.2.13",
    "192.0.2.14",
    "192.0.2.15",
    "192.0.2.16",
    "192.0.2.17",
    "192.0.2.18",
    "192.0.2.19",
]


@dataclass
class ProbeResult:
    ip: str
    url: str
    ok: bool
    status_code: int | None
    elapsed_ms: float
    error: str | None
    response_snippet: str | None
    instance_node_hostname: str | None
    instance_task_name: str | None


async def probe_http_service(
    client: httpx.AsyncClient,
    ip: str,
    port: int,
    path: str,
    expected_statuses: set[int],
) -> ProbeResult:
    url = f"http://{ip}:{port}{path}"
    started_at = time.perf_counter()
    try:
        response = await client.get(url)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        snippet = response.text[:120].replace("\n", " ").replace("\r", " ")
        instance_node_hostname = None
        instance_task_name = None
        try:
            payload = response.json()
            instance = payload.get("instance", {})
            if isinstance(instance, dict):
                instance_node_hostname = instance.get("node_hostname")
                instance_task_name = instance.get("task_name")
        except Exception:
            pass
        return ProbeResult(
            ip=ip,
            url=url,
            ok=response.status_code in expected_statuses,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            error=None,
            response_snippet=snippet,
            instance_node_hostname=instance_node_hostname,
            instance_task_name=instance_task_name,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        return ProbeResult(
            ip=ip,
            url=url,
            ok=False,
            status_code=None,
            elapsed_ms=elapsed_ms,
            error=str(exc) if str(exc).strip() else exc.__class__.__name__,
            response_snippet=None,
            instance_node_hostname=None,
            instance_task_name=None,
        )


async def run_batch(
    ips: list[str],
    port: int,
    path: str,
    timeout_seconds: float,
    concurrency: int,
    expected_statuses: set[int],
) -> list[ProbeResult]:
    semaphore = asyncio.Semaphore(concurrency)
    timeout = httpx.Timeout(timeout_seconds)
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)

    async with httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=True) as client:
        async def run_single(ip: str) -> ProbeResult:
            async with semaphore:
                return await probe_http_service(client, ip, port, path, expected_statuses)

        tasks = [asyncio.create_task(run_single(ip)) for ip in ips]
        return await asyncio.gather(*tasks)


def build_summary(results: list[ProbeResult]) -> dict[str, Any]:
    reachable = [item for item in results if item.ok]
    unreachable = [item for item in results if not item.ok]
    status_counts = Counter(
        str(item.status_code) if item.status_code is not None else "error"
        for item in results
    )
    error_counts = Counter(
        item.error if item.error else "unknown_error"
        for item in unreachable
    )

    return {
        "total_targets": len(results),
        "http_service_up": len(reachable),
        "http_service_down": len(unreachable),
        "success_rate": f"{(len(reachable) / len(results) * 100):.2f}%" if results else "0.00%",
        "status_counts": dict(status_counts),
        "error_type_counts": dict(error_counts),
        "results": [
            {
                "ip": item.ip,
                "url": item.url,
                "ok": item.ok,
                "status_code": item.status_code,
                "elapsed_ms": round(item.elapsed_ms, 2),
                "error": item.error,
                "response_snippet": item.response_snippet,
                "instance_node_hostname": item.instance_node_hostname,
                "instance_task_name": item.instance_task_name,
            }
            for item in sorted(results, key=lambda entry: entry.ip)
        ],
    }


def print_text_summary(summary: dict[str, Any]) -> None:
    print(f"total_targets={summary['total_targets']}")
    print(f"http_service_up={summary['http_service_up']}")
    print(f"http_service_down={summary['http_service_down']}")
    print(f"success_rate={summary['success_rate']}")
    print(f"status_counts={summary['status_counts']}")
    print(f"error_type_counts={summary['error_type_counts']}")
    print()
    print("per_target_results:")
    for item in summary["results"]:
        print(
            " - "
            f"ip={item['ip']} ok={item['ok']} status_code={item['status_code']} "
            f"elapsed_ms={item['elapsed_ms']} error={item['error']} "
            f"node={item['instance_node_hostname']} task={item['instance_task_name']} "
            f"url={item['url']} snippet={item['response_snippet']}"
        )


async def main() -> int:
    parser = argparse.ArgumentParser(description="批量检测多个 IP 的 8883 端口 HTTP 可达性")
    parser.add_argument(
        "ips",
        nargs="*",
        default=DEFAULT_IPS,
        help="待检测 IP 列表，默认使用脚本内置目标",
    )
    parser.add_argument("--port", type=int, default=8883, help="目标端口")
    parser.add_argument("--path", default="/health", help="HTTP 请求路径")
    parser.add_argument("--timeout", type=float, default=10.0, help="单个请求超时秒数")
    parser.add_argument("--concurrency", type=int, default=10, help="并发数")
    parser.add_argument(
        "--expected-status",
        dest="expected_statuses",
        action="append",
        type=int,
        default=[200],
        help="视为 HTTP 服务可用的状态码，可重复指定，例如 --expected-status 200 --expected-status 403",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    args = parser.parse_args()

    if args.port <= 0:
        raise ValueError("--port must be greater than 0")
    if args.timeout <= 0:
        raise ValueError("--timeout must be greater than 0")
    if args.concurrency <= 0:
        raise ValueError("--concurrency must be greater than 0")

    results = await run_batch(
        ips=args.ips,
        port=args.port,
        path=args.path,
        timeout_seconds=args.timeout,
        concurrency=min(args.concurrency, len(args.ips) or 1),
        expected_statuses=set(args.expected_statuses),
    )
    summary = build_summary(results)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text_summary(summary)

    return 0 if all(item.ok for item in results) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
