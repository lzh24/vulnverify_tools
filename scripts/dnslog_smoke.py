"""
DNSLog provider 真实服务冒烟脚本（需要外网/自建服务可达）。

对三种 provider 依次实跑：
  1. internal      → 自建 DNSlog-GO，需 DNSLOG_DOMAIN/TOKEN/WEBSERVER
  2. callback_red  → callback.red，需 CALLBACK_RED_BASE_URL
  3. dnslog_cn     → dnslog.cn，需 DNSLOG_CN_BASE_URL

每种类型独立成节：register → 触发一次 DNS 解析（socket）→ verifydns 断言 exists=true。
单节失败只打印原因，不中断其它类型。

用法：
  python scripts/dnslog_smoke.py
  python scripts/dnslog_smoke.py --type callback_red     # 只跑某类
  # internal 需要真实 env：DNSLOG_DOMAIN/TOKEN/WEBSERVER（本脚本从 os.environ 读取）
"""

import argparse
import asyncio
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.dnslog.main import (  # noqa: E402
    CallbackRedProvider,
    DnslogCnProvider,
    InternalProvider,
)


async def _dns_lookup(subdomain: str, timeout: float = 10.0) -> bool:
    """尝试用系统解析器解析子域名，返回是否解析到 A 记录。"""
    loop = asyncio.get_event_loop()

    def _resolve():
        try:
            socket.setdefaulttimeout(timeout)
            socket.gethostbyname(subdomain)
            return True
        except OSError:
            return False

    return await loop.run_in_executor(None, _resolve)


async def _verify_with_retry(provider, params, attempts: int = 4, delay: float = 2.0):
    """公共 DNSLog 会话极短（尤其 callback.red），verifydns 需轮询若干次。"""
    last = None
    for _ in range(attempts):
        last = await provider.verifydns(params)
        if last["exists"]:
            return last
        await asyncio.sleep(delay)
    return last


async def _smoke_internal() -> bool:
    domain = os.environ.get("DNSLOG_DOMAIN", "")
    token = os.environ.get("DNSLOG_TOKEN", "")
    webserver = os.environ.get("DNSLOG_WEBSERVER", "")
    if not (domain and token and webserver):
        print("[internal] 跳过：缺少 DNSLOG_DOMAIN/TOKEN/WEBSERVER env")
        return False

    p = InternalProvider(domain=domain, token=token, webserver=webserver)
    reg = await p.register({"length": 5})
    sub = reg["subdomain"]
    print(f"[internal] register → {sub}")
    # 自建 DNSLog：系统解析器可能把私有域指向内网，直接用服务端解析最可靠
    # （DNSLOG_WEBSERVER 的主机 IP 即 DNS 服务器，UDP/53）
    dns_ip = webserver.split(":")[0]
    resolved = await _dns_query_to(sub, dns_ip, 53)
    print(f"[internal] DNS 解析(直查 {dns_ip}:53) {'命中' if resolved else '未命中'}")
    ver = await _verify_with_retry(p, {"query": sub})
    ok = resolved and ver["exists"]
    print(f"[internal] verifydns exists={ver['exists']} → {'✅' if ok else '❌'}")
    return ok


async def _dns_query_to(subdomain: str, server_ip: str, server_port: int = 53,
                        timeout: float = 5.0) -> bool:
    """直接向指定 DNS 服务器发 UDP 查询，返回是否命中 A 记录。

    用原始 DNS 报文而非系统解析器，绕开系统 resolver 的缓存/搜索域/私有域判定。
    """
    import struct

    def _query() -> bool:
        header = struct.pack(">HHHHHH", 0xBEEF, 0x0100, 1, 0, 0, 0)
        body = b"".join(
            struct.pack("B", len(label)) + label.encode()
            for label in subdomain.split(".")
        ) + b"\x00"
        body += struct.pack(">HH", 1, 1)  # QTYPE=A, QCLASS=IN
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        try:
            s.sendto(header + body, (server_ip, server_port))
            data, _ = s.recvfrom(4096)
            return struct.unpack(">H", data[6:8])[0] > 0  # ANCOUNT > 0
        except OSError:
            return False
        finally:
            s.close()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _query)


async def _smoke_callback_red() -> bool:
    base = os.environ.get("CALLBACK_RED_BASE_URL", "https://callback.red")
    p = CallbackRedProvider(base_url=base)
    reg = await p.register({})
    sub = reg["subdomain"]
    print(f"[callback_red] register → {sub} (session={reg['session_id']})")
    resolved = await _dns_lookup(sub)
    print(f"[callback_red] DNS 解析 {'命中' if resolved else '未命中'}")
    ver = await _verify_with_retry(
        p, {"session_id": reg["session_id"], "query": sub}
    )
    ok = resolved and ver["exists"]
    print(f"[callback_red] verifydns exists={ver['exists']} → {'✅' if ok else '❌'}")
    return ok


async def _smoke_dnslog_cn() -> bool:
    base = os.environ.get("DNSLOG_CN_BASE_URL", "http://www.dnslog.cn")
    p = DnslogCnProvider(base_url=base)
    reg = await p.register({})
    sub = reg["subdomain"]
    print(f"[dnslog_cn] register → {sub} (session={reg['session_id']})")
    resolved = await _dns_lookup(sub)
    print(f"[dnslog_cn] DNS 解析 {'命中' if resolved else '未命中'}")
    ver = await _verify_with_retry(
        p, {"session_id": reg["session_id"], "query": sub}
    )
    ok = resolved and ver["exists"]
    print(f"[dnslog_cn] verifydns exists={ver['exists']} → {'✅' if ok else '❌'}")
    return ok


async def _main(only: str | None):
    sections = [
        ("internal", _smoke_internal),
        ("callback_red", _smoke_callback_red),
        ("dnslog_cn", _smoke_dnslog_cn),
    ]
    results = {}
    for name, fn in sections:
        if only and name != only:
            continue
        print(f"\n===== {name} =====")
        try:
            results[name] = await fn()
        except Exception as e:  # noqa: BLE001
            print(f"[{name}] ❌ 异常：{type(e).__name__}: {e}")
            results[name] = False

    print("\n===== 汇总 =====")
    for name, ok in results.items():
        print(f"  {name}: {'✅ 通过' if ok else '❌ 未通过/跳过'}")
    failed = [n for n, ok in results.items() if not ok]
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", choices=["internal", "callback_red", "dnslog_cn"],
                    help="只跑某类 provider")
    args = ap.parse_args()
    sys.exit(asyncio.run(_main(args.type)))
