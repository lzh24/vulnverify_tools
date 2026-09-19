import asyncio
import time
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

MAX_CONCURRENCY = 300
semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

app = FastAPI(title="Curl Execute Service")

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 认证配置
AUTH_TOKEN = os.getenv("CURL_EXEC_AUTH_TOKEN", "default-token-please-change")
AUTH_HEADER_NAME = os.getenv("CURL_EXEC_AUTH_HEADER", "X-Auth-Token")


# 认证中间件
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # 只跳过健康检查接口
    if request.url.path == "/health":
        response = await call_next(request)
        return response
    
    # 检查认证头
    auth_header = request.headers.get(AUTH_HEADER_NAME)
    if not auth_header or auth_header != AUTH_TOKEN:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid or missing authentication token"}
        )
    
    response = await call_next(request)
    return response


# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {"message": "Curl Service", "version": "1.0.0"}


class CurlRequest(BaseModel):
    curl_args: List[str] = Field(..., description="curl 参数数组（不含 curl）")
    timeout: Optional[int] = Field(15, description="超时时间（秒）")


class CurlResponse(BaseModel):
    status_code: Optional[int]
    elapsed_ms: int
    raw_response: Optional[str]
    error: Optional[str]


def _has_ua(args: List[str]) -> bool:
    for i, arg in enumerate(args):
        if arg.lower() == "-h" and i + 1 < len(args):
            if args[i + 1].lower().startswith("user-agent"):
                return True
    return False


@app.post("/execute-curl", response_model=CurlResponse)
async def execute_curl(req: CurlRequest):
    async with semaphore:
        start = time.perf_counter()

        args = [
            "curl",
            "-i",
            "--raw",
            "--silent",
            "--show-error",
            "--max-time",
            str(req.timeout),
        ]

        if not _has_ua(req.curl_args):
            args += ["-H", f"User-Agent: {DEFAULT_UA}"]

        args += req.curl_args

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()

            elapsed_ms = int((time.perf_counter() - start) * 1000)

            if proc.returncode != 0:
                return CurlResponse(
                    status_code=None,
                    elapsed_ms=elapsed_ms,
                    raw_response=None,
                    error=stderr.decode(errors="ignore"),
                )

            raw_response = stdout.decode(errors="ignore")

            # 提取 HTTP 状态码
            status_code = None
            if raw_response.startswith("HTTP/"):
                try:
                    status_code = int(raw_response.split()[1])
                except Exception:
                    pass

            return CurlResponse(
                status_code=status_code,
                elapsed_ms=elapsed_ms,
                raw_response=raw_response,
                error=None,
            )

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return CurlResponse(
                status_code=None,
                elapsed_ms=elapsed_ms,
                raw_response=None,
                error=str(e),
            )
