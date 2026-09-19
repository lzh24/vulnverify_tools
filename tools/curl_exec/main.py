"""
 Curl Execute Service - Migrated to External Tool Framework

 This tool service provides the same functionality as the original curl_exec.py
 but implemented using the new external tool framework.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin

from core.base_tool_service import BaseToolService, tool_action


# Default User-Agent
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Concurrency control
MAX_CONCURRENCY = 300
semaphore = asyncio.Semaphore(MAX_CONCURRENCY)


class RawHttpToCurl:
    """
    将原始 HTTP 请求包 + 明确的 URL 转换为可执行的 curl 命令
    
    适用场景：
    - 漏洞请求复现
    - 攻防 PoC 生成
    - 抓包请求标准化
    """

    def __init__(
        self,
        url: str,
        raw_http: str,
        *,
        drop_headers: Optional[List[str]] = None,
        mask_headers: Optional[List[str]] = None,
    ):
        """
        :param url: 明确的 URL（含 http/https）
        :param raw_http: 原始 HTTP 请求包文本
        :param drop_headers: 需要丢弃的 header（如 Content-Length）
        :param mask_headers: 需要脱敏的 header（如 Authorization）
        """
        self.url = url.rstrip("/")
        self.raw_http = raw_http
        self.drop_headers = set(h.lower() for h in (drop_headers or []))
        self.mask_headers = set(h.lower() for h in (mask_headers or []))

        self.method: str = ""
        self.path: str = ""
        self.headers: Dict[str, str] = {}
        self.body: str = ""

        self._parse_raw_http()

    def _parse_raw_http(self) -> None:
        lines = self.raw_http.strip("\n").splitlines()
        if not lines:
            raise ValueError("Empty raw HTTP request")

        # 请求行
        try:
            self.method, self.path, _ = lines[0].split(" ", 2)
        except ValueError:
            raise ValueError(f"Invalid request line: {lines[0]}")

        is_body = False
        body_lines = []

        for line in lines[1:]:
            if not is_body:
                if line.strip() == "":
                    is_body = True
                    continue

                if ":" not in line:
                    continue

                k, v = line.split(":", 1)
                header_name = k.strip()
                header_value = v.strip()

                if header_name.lower() in self.drop_headers:
                    continue

                if header_name.lower() in self.mask_headers:
                    header_value = "***MASKED***"

                self.headers[header_name] = header_value
            else:
                body_lines.append(line)

        self.body = "\n".join(body_lines).strip()

    def to_curl_args(self) -> List[str]:
        """
        生成符合 curl_exec.py 入参格式的 curl 参数列表
        
        返回:
            List[str]: curl 参数列表（不含 "curl" 命令本身）
        """
        url = self._build_url()
        
        args = [
            url,
            "-X", self.method,
        ]
        
        for k, v in self.headers.items():
            args.extend(["-H", f"{k}: {v}"])
        
        if self.body:
            args.extend(["--data", self.body])
            
        return args

    def _build_url(self) -> str:
        """
        构造最终请求 URL
        兼容：
        - url 含目录路径
        - raw path 绝对 / 相对
        - raw path 为完整 URL
        """
        path = self.path.strip()

        # 规则 3：raw request 里已经是完整 URL
        if path.startswith("http://") or path.startswith("https://"):
            return path

        base = self.url

        # 确保 base 是目录形式，方便 urljoin
        if not base.endswith("/"):
            base = base + "/"

        # urljoin 自动处理 / 覆盖规则
        return urljoin(base, path)


class CurlExecService(BaseToolService):
    def __init__(self):
        super().__init__("curl-exec", "1.1.0")

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Legacy parameter validation - kept for backward compatibility"""
        return True

    async def _execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy execution method - not used with new action pattern"""
        raise NotImplementedError("Use action-based methods instead")

    @tool_action("curl_args", "Execute curl command with provided arguments")
    async def execute_curl(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute curl command with the same logic as original service"""
        start = time.perf_counter()
        
        curl_args = params.get("curl_args")
        if not curl_args or not isinstance(curl_args, list):
            raise ValueError("curl_args parameter is required and must be a list")
            
        timeout = params.get("timeout", 15)
        
        args = [
            "curl",
            "-i",
            "--raw",
            "--silent",
            "--show-error",
            "--max-time",
            str(timeout),
        ]
        
        if not self._has_ua(curl_args):
            args += ["-H", f"User-Agent: {DEFAULT_UA}"]
            
        args += curl_args
        
        try:
            async with semaphore:
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                
                stdout, stderr = await proc.communicate()
                
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                raw_response = stdout.decode(errors="ignore")
                error_msg = stderr.decode(errors="ignore") or None
                status_code, response_complete = self._extract_status_code(raw_response)

                if proc.returncode != 0:
                    self.logger.warning(
                        "Curl exited with non-zero status %s, preserving partial response",
                        proc.returncode,
                    )

                self.logger.info(
                    "Curl execution completed in %sms with return code %s",
                    elapsed_ms,
                    proc.returncode,
                )
                return {
                    "status_code": status_code,
                    "elapsed_ms": elapsed_ms,
                    "raw_response": raw_response or None,
                    "error": error_msg,
                    "exit_code": proc.returncode,
                    "response_complete": response_complete,
                }
                
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            self.logger.error(f"Curl execution exception: {e}")
            return {
                "status_code": None,
                "elapsed_ms": elapsed_ms,
                "raw_response": None,
                "error": str(e),
            }

    @tool_action("rawhttp", "Execute raw HTTP request by converting it to curl")
    async def send_rawhttp(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        接收原始 HTTP 请求和 URL，转换为 curl 参数并执行
        
        参数:
            url: 目标 URL（必需）
            raw_http: 原始 HTTP 请求文本（必需）
            timeout: 超时时间（可选，默认 15 秒）
            drop_headers: 要丢弃的 header 列表（可选）
            mask_headers: 要脱敏的 header 列表（可选）
        """
        url = params.get("url")
        raw_http = params.get("raw_http")
        
        if not url:
            raise ValueError("url parameter is required")
        if not raw_http:
            raise ValueError("raw_http parameter is required")
        
        timeout = params.get("timeout", 15)
        drop_headers = params.get("drop_headers")
        mask_headers = params.get("mask_headers")
        
        try:
            # 使用 RawHttpToCurl 转换
            converter = RawHttpToCurl(
                url=url,
                raw_http=raw_http,
                drop_headers=drop_headers,
                mask_headers=mask_headers,
            )
            
            # 获取 curl 参数
            curl_args = converter.to_curl_args()
            
            self.logger.info(f"Converted raw HTTP to curl args: {curl_args}")
            
            # 调用 execute_curl 方法执行
            result = await self.execute_curl({
                "curl_args": curl_args,
                "timeout": timeout
            })
            
            # 添加转换信息到结果
            result["converted_from_rawhttp"] = True
            result["original_url"] = url
            
            return result
            
        except ValueError as e:
            self.logger.error(f"Raw HTTP parsing error: {e}")
            raise ValueError(f"Failed to parse raw HTTP request: {str(e)}")
        except Exception as e:
            self.logger.error(f"Raw HTTP execution error: {e}")
            raise

    def _extract_status_code(self, raw_response: str) -> Tuple[Optional[int], bool]:
        """Extract the last HTTP status code and whether the response appears complete."""
        if not raw_response:
            return None, False

        header_separator = "\r\n\r\n" if "\r\n\r\n" in raw_response else "\n\n"
        response_parts = raw_response.split(header_separator)
        status_code: Optional[int] = None

        for part in response_parts:
            if not part.startswith("HTTP/"):
                continue
            try:
                status_code = int(part.split()[1])
            except (IndexError, ValueError):
                continue

        response_complete = raw_response.endswith(header_separator) or len(response_parts) > 1
        return status_code, response_complete

    def _has_ua(self, args: List[str]) -> bool:
        """Check if User-Agent header is already present in curl args"""
        for i, arg in enumerate(args):
            if arg.lower() in {"-h", "--header"} and i + 1 < len(args):
                if args[i + 1].lower().startswith("user-agent"):
                    return True
        return False
