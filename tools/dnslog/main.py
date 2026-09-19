"""
DNSLog Service - External Tool Framework Implementation

Supports three providers via DNSLOG_TYPE env:
  - internal (default): existing self-hosted DNSLog (DNSlog-GO) server
  - callback_red: public callback.red DNSLog provider
  - dnslog_cn: public dnslog.cn DNSLog provider
"""

import random
from typing import Dict, Any, Optional

import httpx

from core.base_tool_service import BaseToolService, tool_action
from core.config import get_dnslog_config

VALID_PROVIDER_TYPES = ("internal", "callback_red", "dnslog_cn")


class InternalProvider:
    """Existing self-hosted DNSLog (DNSlog-GO) provider (default)."""

    def __init__(self, domain: str, token: str, webserver: str):
        self.domain = domain
        self.token = token
        self.webserver = webserver

    def random_subdomain(self, domain: str, length: int = 5) -> str:
        if length <= 0 or length > 26:
            raise ValueError("length must be between 1 and 26")
        prefix = ''.join(random.sample('zyxwvutsrqponmlkjihgfedcba', length))
        return f"{prefix}.{domain}"

    async def register(self, params: Dict[str, Any]) -> Dict[str, Any]:
        webserver = params.get("webserver") or self.webserver
        token = params.get("token") or self.token
        length = int(params.get("length", 5))

        if not webserver:
            raise ValueError("webserver parameter is required")
        if not token:
            raise ValueError("token parameter is required")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"http://{webserver}/api/verifyToken",
                    headers={"token": token},
                )
                data = response.json()
        except httpx.HTTPError as e:
            raise ValueError(f"verifyToken request failed: {e}")

        if data.get("code") == 401:
            raise ValueError(data.get("msg", "token verification failed"))

        domain = self.domain
        subdomain = self.random_subdomain(domain, length)

        return {
            "status": "registered",
            "domain": domain,
            "subdomain": subdomain,
        }

    async def verifydns(self, params: Dict[str, Any]) -> Dict[str, Any]:
        webserver = params.get("webserver") or self.webserver
        token = params.get("token") or self.token
        query = params.get("query")

        if not webserver:
            raise ValueError("webserver parameter is required")
        if not token:
            raise ValueError("token parameter is required")
        if not query:
            raise ValueError("query parameter is required")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"http://{webserver}/api/verifyDns",
                    json={"query": query},
                    headers={"token": token},
                )
                data = response.json()
        except httpx.HTTPError as e:
            raise ValueError(f"verifyDns request failed: {e}")

        exists = data.get("Msg", "") == "true"

        return {
            "status": "verified",
            "query": query,
            "exists": exists,
            "data": data.get("data", ""),
        }


class CallbackRedProvider:
    """Public callback.red DNSLog provider (DNSLOG_TYPE=callback_red)."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def register(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/get")
                data = response.json()
        except httpx.HTTPError as e:
            raise ValueError(f"callback.red /get request failed: {e}")

        key = data.get("key")
        subdomain = data.get("subdomain")

        if not key or not subdomain:
            raise ValueError(
                f"callback.red returned unexpected response: {data}"
            )

        # domain 取 subdomain 去掉随机前缀（最后两段）
        parts = subdomain.split(".")
        domain = ".".join(parts[-2:]) if len(parts) >= 2 else subdomain

        return {
            "status": "registered",
            "domain": domain,
            "subdomain": subdomain,
            "session_id": key,
        }

    async def verifydns(self, params: Dict[str, Any]) -> Dict[str, Any]:
        session_id = params.get("session_id")
        if not session_id:
            raise ValueError(
                "session_id is required for callback_red provider. "
                "Please pass the session_id returned by register."
            )

        query = params.get("query", "")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.base_url,
                    data={"key": session_id},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                data = response.json()
        except httpx.HTTPError as e:
            raise ValueError(f"callback.red query request failed: {e}")

        code = data.get("code")
        logs = data.get("data", [])

        if code == 403:
            exists = False
            log_data = logs
        elif code == 200:
            exists = len(logs) > 0
            log_data = logs
        else:
            exists = False
            log_data = data

        return {
            "status": "verified",
            "query": query,
            "exists": exists,
            "data": log_data,
        }


class DnslogCnProvider:
    """Public dnslog.cn DNSLog provider (DNSLOG_TYPE=dnslog_cn)."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        # PHPSESSID 在 register(/getdomain.php) 时由 Set-Cookie 下发，verifydns
        # 时需带上它才能查询到该会话下的记录。
        self._session_id: Optional[str] = None

    @staticmethod
    def _extract_phpsessid(set_cookie: str) -> str:
        for part in set_cookie.split(";"):
            part = part.strip()
            if part.lower().startswith("phpsessid="):
                return part.split("=", 1)[1].strip()
        return ""

    async def register(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/getdomain.php")
        except httpx.HTTPError as e:
            raise ValueError(f"dnslog.cn /getdomain.php request failed: {e}")

        subdomain = (response.text or "").strip()
        phpsessid = self._extract_phpsessid(
            response.headers.get("set-cookie", "")
        )

        if not subdomain or "." not in subdomain:
            raise ValueError(
                f"dnslog.cn returned unexpected subdomain: {subdomain!r}"
            )
        if not phpsessid:
            raise ValueError("dnslog.cn did not return PHPSESSID cookie")

        self._session_id = phpsessid
        parts = subdomain.split(".")
        domain = ".".join(parts[-2:]) if len(parts) >= 2 else subdomain

        return {
            "status": "registered",
            "domain": domain,
            "subdomain": subdomain,
            "session_id": phpsessid,
        }

    async def verifydns(self, params: Dict[str, Any]) -> Dict[str, Any]:
        session_id = params.get("session_id") or self._session_id
        if not session_id:
            raise ValueError(
                "session_id is required for dnslog_cn provider. "
                "Please pass the session_id returned by register."
            )

        query = params.get("query", "")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/getrecords.php",
                    headers={"Cookie": f"PHPSESSID={session_id}"},
                )
                data = response.json()
        except httpx.HTTPError as e:
            raise ValueError(f"dnslog.cn /getrecords.php request failed: {e}")

        logs = data if isinstance(data, list) else []
        exists = len(logs) > 0

        return {
            "status": "verified",
            "query": query,
            "exists": exists,
            "data": logs,
        }


class DnsLogTool(BaseToolService):
    def __init__(self):
        super().__init__("dnslog-service", "1.3.0")
        config = get_dnslog_config()
        provider_type = config["type"]

        if provider_type == "internal":
            self._provider = InternalProvider(
                domain=config["domain"],
                token=config["token"],
                webserver=config["webserver"],
            )
        elif provider_type == "callback_red":
            self._provider = CallbackRedProvider(
                base_url=config["callback_red_base_url"],
            )
        elif provider_type == "dnslog_cn":
            self._provider = DnslogCnProvider(
                base_url=config["dnslog_cn_base_url"],
            )
        else:
            raise ValueError(
                f"Unknown DNSLOG_TYPE={provider_type!r}. "
                f"Expected one of: {', '.join(VALID_PROVIDER_TYPES)}"
            )

        self.provider_type = provider_type

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        return isinstance(params, dict)

    async def _execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(params, dict):
            raise ValueError("params must be a dict")
        raise NotImplementedError("Use action-based methods instead")

    @tool_action("register", "Register and get a random DNS subdomain")
    async def register(self, params: Dict[str, Any]) -> Dict[str, Any]:
        result = await self._provider.register(params)
        self.logger.info(
            f"register ({self.provider_type}): subdomain={result.get('subdomain')}"
        )
        return result

    @tool_action("verifydns", "Verify whether DNS record exists")
    async def verifydns(self, params: Dict[str, Any]) -> Dict[str, Any]:
        result = await self._provider.verifydns(params)
        self.logger.info(
            f"verifydns ({self.provider_type}): query={result.get('query')}, "
            f"exists={result.get('exists')}"
        )
        return result
