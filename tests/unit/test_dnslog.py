"""Unit tests for DNSLog providers (internal / callback_red / dnslog_cn).

Tests exercise the provider logic against a mocked httpx.AsyncClient —
no external network is touched.
"""

import asyncio

import pytest

from tools.dnslog.main import (
    CallbackRedProvider,
    DnslogCnProvider,
    DnsLogTool,
    InternalProvider,
)


# ── httpx mock helpers ──────────────────────────────────────────────────────

class FakeResponse:
    def __init__(self, json_data=None, text="", headers=None):
        self._json = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._json is None:
            raise ValueError("no json body")
        return self._json


class FakeAsyncClient:
    """Records requests; returns queued responses or raises if exhausted."""

    def __init__(self, responses=None, method="get", request_error=None):
        # responses: list of (method, url_kwargs, FakeResponse)
        self.responses = list(responses or [])
        self.method = method
        self.request_error = request_error
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def _next(self, method, **kwargs):
        self.calls.append((method, kwargs))
        if self.request_error is not None:
            raise self.request_error
        if not self.responses:
            raise AssertionError("FakeAsyncClient ran out of queued responses")
        m, url_kwargs, resp = self.responses.pop(0)
        assert m == method, f"expected method {m}, got {method}"
        assert url_kwargs.items() <= kwargs.items(), (
            f"expected url_kwargs {url_kwargs} subset of actual {kwargs}"
        )
        return resp

    async def get(self, url, **kwargs):
        return self._next("get", url=url, **kwargs)

    async def post(self, url, **kwargs):
        return self._next("post", url=url, **kwargs)


def _install_fake_client(monkeypatch, client):
    monkeypatch.setattr("tools.dnslog.main.httpx.AsyncClient", lambda *a, **k: client)


# ── internal provider ───────────────────────────────────────────────────────

def test_internal_register_success(monkeypatch):
    client = FakeAsyncClient([
        ("get", {"url": "http://ws:8070/api/verifyToken", "headers": {"token": "tok"}},
         FakeResponse({"code": 200, "msg": "ok"})),
    ])
    _install_fake_client(monkeypatch, client)

    p = InternalProvider(domain="self.dnslog", token="tok", webserver="ws:8070")
    result = asyncio.run(p.register({"length": 4}))

    assert result["status"] == "registered"
    assert result["domain"] == "self.dnslog"
    assert result["subdomain"].endswith(".self.dnslog")
    # length 4 → 4 个字母前缀
    prefix = result["subdomain"].split(".")[0]
    assert len(prefix) == 4


def test_internal_register_unauthorized(monkeypatch):
    client = FakeAsyncClient([
        ("get", {"url": "http://ws:8070/api/verifyToken", "headers": {"token": "tok"}},
         FakeResponse({"code": 401, "msg": "bad token"})),
    ])
    _install_fake_client(monkeypatch, client)
    p = InternalProvider(domain="self.dnslog", token="tok", webserver="ws:8070")
    with pytest.raises(ValueError, match="bad token"):
        asyncio.run(p.register({}))


def test_internal_verifydns_exists(monkeypatch):
    client = FakeAsyncClient([
        ("post", {"url": "http://ws:8070/api/verifyDns",
                  "json": {"query": "abc.self.dnslog"},
                  "headers": {"token": "tok"}},
         FakeResponse({"Msg": "true", "data": "1.2.3.4"})),
    ])
    _install_fake_client(monkeypatch, client)
    p = InternalProvider(domain="self.dnslog", token="tok", webserver="ws:8070")
    result = asyncio.run(p.verifydns({"query": "abc.self.dnslog"}))
    assert result["exists"] is True


def test_internal_verifydns_not_exists(monkeypatch):
    client = FakeAsyncClient([
        ("post", {"url": "http://ws:8070/api/verifyDns",
                  "json": {"query": "abc.self.dnslog"},
                  "headers": {"token": "tok"}},
         FakeResponse({"Msg": "false", "data": ""})),
    ])
    _install_fake_client(monkeypatch, client)
    p = InternalProvider(domain="self.dnslog", token="tok", webserver="ws:8070")
    result = asyncio.run(p.verifydns({"query": "abc.self.dnslog"}))
    assert result["exists"] is False


# ── callback_red provider ───────────────────────────────────────────────────

def test_callback_red_register(monkeypatch):
    client = FakeAsyncClient([
        ("get", {"url": "https://callback.red/get"},
         FakeResponse({"key": "k-123", "subdomain": "abc.callback.red"})),
    ])
    _install_fake_client(monkeypatch, client)
    p = CallbackRedProvider("https://callback.red")
    result = asyncio.run(p.register({}))
    assert result["domain"] == "callback.red"
    assert result["subdomain"] == "abc.callback.red"
    assert result["session_id"] == "k-123"


def test_callback_red_verifydns_exists(monkeypatch):
    client = FakeAsyncClient([
        ("post", {"url": "https://callback.red", "data": {"key": "k-123"},
                  "headers": {"Content-Type": "application/x-www-form-urlencoded"}},
         FakeResponse({"code": 200, "data": [["abc.callback.red", "1.2.3.4"]]})),
    ])
    _install_fake_client(monkeypatch, client)
    p = CallbackRedProvider("https://callback.red")
    result = asyncio.run(p.verifydns({"session_id": "k-123", "query": "abc.callback.red"}))
    assert result["exists"] is True


def test_callback_red_verifydns_session_expired(monkeypatch):
    client = FakeAsyncClient([
        ("post", {"url": "https://callback.red", "data": {"key": "k-123"},
                  "headers": {"Content-Type": "application/x-www-form-urlencoded"}},
         FakeResponse({"code": 403, "data": ["Domain Expired"]})),
    ])
    _install_fake_client(monkeypatch, client)
    p = CallbackRedProvider("https://callback.red")
    result = asyncio.run(p.verifydns({"session_id": "k-123", "query": "abc.callback.red"}))
    assert result["exists"] is False


def test_callback_red_verifydns_unexpected_code(monkeypatch):
    """未知 code（如 500/404）→ 视为不可用，不误报 exists。"""
    client = FakeAsyncClient([
        ("post", {"url": "https://callback.red", "data": {"key": "k-123"},
                  "headers": {"Content-Type": "application/x-www-form-urlencoded"}},
         FakeResponse({"code": 500, "data": ["Server Error"]})),
    ])
    _install_fake_client(monkeypatch, client)
    p = CallbackRedProvider("https://callback.red")
    result = asyncio.run(p.verifydns({"session_id": "k-123", "query": "abc.callback.red"}))
    assert result["exists"] is False


def test_callback_red_verifydns_requires_session(monkeypatch):
    """缺少 session_id 时抛错，而不是发空请求。"""
    p = CallbackRedProvider("https://callback.red")
    with pytest.raises(ValueError):
        asyncio.run(p.verifydns({"query": "abc.callback.red"}))


# ── dnslog_cn provider ──────────────────────────────────────────────────────

def test_dnslog_cn_register_and_verify(monkeypatch):
    client = FakeAsyncClient([
        ("get", {"url": "http://www.dnslog.cn/getdomain.php"},
         FakeResponse(text="abc.dnslog.cn",
                      headers={"set-cookie": "PHPSESSID=phpsess123; path=/; HttpOnly"})),
        ("get", {"url": "http://www.dnslog.cn/getrecords.php",
                 "headers": {"Cookie": "PHPSESSID=phpsess123"}},
         FakeResponse([["abc.dnslog.cn", "1.2.3.4", "2026-08-19 10:00:00"]])),
    ])
    _install_fake_client(monkeypatch, client)

    p = DnslogCnProvider("http://www.dnslog.cn")
    reg = asyncio.run(p.register({}))
    assert reg["subdomain"] == "abc.dnslog.cn"
    assert reg["domain"] == "dnslog.cn"
    assert reg["session_id"] == "phpsess123"

    ver = asyncio.run(p.verifydns({"query": "abc.dnslog.cn"}))
    assert ver["exists"] is True


def test_dnslog_cn_verify_empty(monkeypatch):
    client = FakeAsyncClient([
        ("get", {"url": "http://www.dnslog.cn/getrecords.php",
                 "headers": {"Cookie": "PHPSESSID=phpsess123"}},
         FakeResponse([])),
    ])
    _install_fake_client(monkeypatch, client)
    p = DnslogCnProvider("http://www.dnslog.cn")
    p._session_id = "phpsess123"
    ver = asyncio.run(p.verifydns({"query": "abc.dnslog.cn"}))
    assert ver["exists"] is False


def test_dnslog_cn_register_missing_cookie(monkeypatch):
    client = FakeAsyncClient([
        ("get", {"url": "http://www.dnslog.cn/getdomain.php"},
         FakeResponse(text="abc.dnslog.cn", headers={})),
    ])
    _install_fake_client(monkeypatch, client)
    p = DnslogCnProvider("http://www.dnslog.cn")
    with pytest.raises(ValueError, match="PHPSESSID"):
        asyncio.run(p.register({}))


# ── DnsLogTool provider selection ───────────────────────────────────────────

def test_tool_selects_internal(monkeypatch):
    monkeypatch.setenv("DNSLOG_TYPE", "internal")
    monkeypatch.setenv("DNSLOG_DOMAIN", "self.dnslog")
    monkeypatch.setenv("DNSLOG_TOKEN", "tok")
    monkeypatch.setenv("DNSLOG_WEBSERVER", "ws:8070")
    tool = DnsLogTool()
    assert tool.provider_type == "internal"
    assert isinstance(tool._provider, InternalProvider)


def test_tool_selects_callback_red(monkeypatch):
    monkeypatch.setenv("DNSLOG_TYPE", "callback_red")
    monkeypatch.setenv("CALLBACK_RED_BASE_URL", "https://callback.red")
    tool = DnsLogTool()
    assert tool.provider_type == "callback_red"
    assert isinstance(tool._provider, CallbackRedProvider)


def test_tool_selects_dnslog_cn(monkeypatch):
    monkeypatch.setenv("DNSLOG_TYPE", "dnslog_cn")
    monkeypatch.setenv("DNSLOG_CN_BASE_URL", "http://www.dnslog.cn")
    tool = DnsLogTool()
    assert tool.provider_type == "dnslog_cn"
    assert isinstance(tool._provider, DnslogCnProvider)


def test_tool_rejects_unknown_type(monkeypatch):
    monkeypatch.setenv("DNSLOG_TYPE", "dnslog.cn")  # 旧错标值
    with pytest.raises(ValueError, match="Unknown DNSLOG_TYPE"):
        DnsLogTool()
