import pytest

from tools.curl_exec.main import CurlExecService


class DummyProcess:
    def __init__(self, returncode: int, stdout: bytes, stderr: bytes):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


@pytest.mark.asyncio
async def test_execute_curl_preserves_partial_response_on_nonzero_exit(monkeypatch):
    service = CurlExecService()
    raw_response = (
        b"HTTP/1.1 206 Partial Content\r\n"
        b"Content-Type: text/plain\r\n"
        b"Content-Length: 1000\r\n\r\n"
        b"partial-body"
    )

    async def fake_create_subprocess_exec(*args, **kwargs):
        return DummyProcess(returncode=18, stdout=raw_response, stderr=b"curl: (18) end of response with 728 bytes missing")

    monkeypatch.setattr("tools.curl_exec.main.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = await service.execute_curl({"curl_args": ["https://example.com"]})

    assert result["status_code"] == 206
    assert result["raw_response"] == raw_response.decode(errors="ignore")
    assert result["error"] == "curl: (18) end of response with 728 bytes missing"
    assert result["exit_code"] == 18
    assert result["response_complete"] is True


@pytest.mark.asyncio
async def test_execute_curl_returns_empty_response_when_no_stdout(monkeypatch):
    service = CurlExecService()

    async def fake_create_subprocess_exec(*args, **kwargs):
        return DummyProcess(returncode=6, stdout=b"", stderr=b"curl: (6) Could not resolve host")

    monkeypatch.setattr("tools.curl_exec.main.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = await service.execute_curl({"curl_args": ["https://example.com"]})

    assert result["status_code"] is None
    assert result["raw_response"] is None
    assert result["error"] == "curl: (6) Could not resolve host"
    assert result["exit_code"] == 6
    assert result["response_complete"] is False


def test_extract_status_code_prefers_last_http_response():
    service = CurlExecService()
    raw_response = (
        "HTTP/1.1 100 Continue\r\n\r\n"
        "HTTP/1.1 206 Partial Content\r\nContent-Type: text/plain\r\n\r\n"
        "partial-body"
    )

    status_code, response_complete = service._extract_status_code(raw_response)

    assert status_code == 206
    assert response_complete is True


@pytest.mark.asyncio
async def test_execute_curl_preserves_real_world_206_partial_content_case(monkeypatch):
    service = CurlExecService()
    raw_response = (
        b"HTTP/1.1 206\r\n"
        b"Server: openresty\r\n"
        b"Date: Tue, 26 May 2026 10:05:39 GMT\r\n"
        b"Content-Type: multipart/byteranges; boundary=00000000000005764970\r\n"
        b"Content-Length: 1428\r\n"
        b"Connection: close\r\n"
        b"Last-Modified: Tue, 24 Mar 2026 18:33:23 GMT\r\n"
        b"Vary: Accept-Encoding\r\n"
        b"Etag: \"69c2d8f3-267\"\r\n"
        b"Request-Id: 62046a1570737b97286877675211ac1a\r\n\r\n"
        b"--00000000000005764970\r\n"
        b"Content-Type: text/html\r\n"
        b"Content-Range: bytes 0-614/615\r\n\r\n"
        b"<!DOCTYPE html>\n"
        b"<html>\n"
        b"<head>\n"
        b"<title>Welcome to nginx!</title>\n"
        b"<style>\n"
        b"html { color-scheme: light dark; }\n"
        b"body { wi"
    )

    async def fake_create_subprocess_exec(*args, **kwargs):
        return DummyProcess(returncode=18, stdout=raw_response, stderr=b"curl: (18) end of response with 728 bytes missing")

    monkeypatch.setattr("tools.curl_exec.main.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = await service.execute_curl({
        "curl_args": [
            "https://demo-target.example.com/",
            "-X", "GET",
            "-H", "Host: demo-target.example.com",
            "-H", "Accept-Language: zh-CN,zh;q=0.8",
            "-H", "Accept: */*",
            "-H", "User-Agent: Mozilla/5.0 (Windows NT 5.1; rv:5.0) Gecko/20100101 Firefox/5.0 Mozilla/3.1415926",
            "-H", "Accept-Charset: GBK,utf-8;q=0.7,*;q=0.3",
            "-H", "Connection: close",
            "-H", "Referer: https://demo-target.example.com",
            "-H", "Cache-Control: max-age=0",
            "-H", "Range: bytes=-1238,-9223372036854774570",
        ]
    })

    assert result["status_code"] == 206
    assert result["raw_response"] is not None
    assert "HTTP/1.1 206" in result["raw_response"]
    assert "multipart/byteranges" in result["raw_response"]
    assert "Content-Range: bytes 0-614/615" in result["raw_response"]
    assert "<title>Welcome to nginx!</title>" in result["raw_response"]
    assert result["error"] == "curl: (18) end of response with 728 bytes missing"
    assert result["exit_code"] == 18
    assert result["response_complete"] is True
