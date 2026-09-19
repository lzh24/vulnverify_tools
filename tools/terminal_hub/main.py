import asyncio
import base64
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from core.base_tool_service import BaseToolService, tool_action
from core.config import ToolConfig
from core.image_hosting import upload_and_get_url


@dataclass
class TerminalSession:
    session_id: str
    command: List[str]
    created_at: float
    status: str = "running"
    return_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    screenshot_base64: Optional[str] = None
    screenshot_path: Optional[str] = None
    image_url: Optional[str] = None
    finished_at: Optional[float] = None


class TerminalHubToolService(BaseToolService):
    def __init__(self) -> None:
        super().__init__("terminal_hub", "0.2.0")
        self.runtime_config = ToolConfig()
        self.sessions: Dict[str, TerminalSession] = {}
        self.max_sessions: int = int(os.environ.get("TERMINAL_HUB_MAX_SESSIONS", "50"))

        # 允许的工具白名单，默认允许所有（空字符串或空列表表示不限制）
        allowed_raw = os.environ.get("TERMINAL_HUB_ALLOWED_TOOLS", "")
        if allowed_raw.strip():
            self.allowed_tools: Optional[List[str]] = [t.strip() for t in allowed_raw.split(",") if t.strip()]
        else:
            self.allowed_tools = None  # None 表示不限制

        self.logger.info(f"terminal_hub allowed_tools: {self.allowed_tools}")

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        return True

    async def _execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Use action-based methods")

    def _check_tool_allowed(self, tool: str) -> None:
        """检查工具是否在白名单中，不在则抛出异常"""
        if self.allowed_tools is not None and tool not in self.allowed_tools:
            raise ValueError(
                f"tool '{tool}' is not allowed. "
                f"Allowed tools: {', '.join(self.allowed_tools)}"
            )

    @tool_action("run_cli", "Execute CLI tool and return output + screenshot + image_url")
    async def run_cli(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        一站式执行 CLI 工具并返回完整结果。

        参数:
            tool (str): CLI 工具名称，如 "nmap"、"curl"（必需）
            args (list): CLI 参数列表（可选，默认 []）
            timeout (int): 超时秒数（可选，默认 60）
            inputs (list): 交互式输入序列（可选）。对于需要交互的命令，可以在连接后按顺序发送这些字符串，每个字符串会自动加上换行符。如果输入为 "quit"，则会发送 Ctrl+C 信号。

        返回:
            command (str): 完整命令字符串
            stdout (str): 标准输出
            stderr (str): 标准错误
            return_code (int): 退出码
            status (str): finished / failed
            screenshot_base64 (str): 截图 base64
            image_url (str): 图床 URL
        """
        tool = params.get("tool")
        args = params.get("args", [])
        timeout = int(params.get("timeout", 60))
        inputs = params.get("inputs", [])
        include_screenshot_base64 = params.get(
            "include_screenshot_base64",
            self.runtime_config.terminal_hub_return_base64_by_default,
        )

        if not tool or not isinstance(tool, str):
            raise ValueError("tool is required and must be string")
        if not isinstance(args, list) or not all(isinstance(i, str) for i in args):
            raise ValueError("args must be string array")
        if not isinstance(inputs, list) or not all(isinstance(i, str) for i in inputs):
            raise ValueError("inputs must be string array")
        if not isinstance(include_screenshot_base64, bool):
            raise ValueError("include_screenshot_base64 must be boolean")

        self._check_tool_allowed(tool)

        session_id = str(uuid.uuid4())
        command = [tool, *args]
        use_input_pipe = bool(inputs)

        session = TerminalSession(
            session_id=session_id,
            command=command,
            created_at=time.time(),
        )
        self.sessions[session_id] = session

        await self._run_session_sync(
            session_id,
            timeout=timeout,
            use_input_pipe=use_input_pipe,
            inputs=inputs,
            include_screenshot_base64=include_screenshot_base64,
        )

        return {
            "command": " ".join(session.command),
            "stdout": session.stdout,
            "stderr": session.stderr,
            "return_code": session.return_code,
            "status": session.status,
            "screenshot_base64": session.screenshot_base64 if include_screenshot_base64 else None,
            "image_url": session.image_url,
        }

    @tool_action("create_session", "Create a terminal session and execute command (async)")
    async def create_session(self, params: Dict[str, Any]) -> Dict[str, Any]:
        token = params.get("token")
        expected = os.environ.get("TERMINAL_HUB_TOKEN") or os.environ.get("TOOL_TOKEN")
        if expected and token != expected:
            raise ValueError("Invalid token")

        cmd = params.get("cmd")
        args = params.get("args", [])
        auto_screenshot = bool(params.get("auto_screenshot", True))
        include_screenshot_base64 = params.get(
            "include_screenshot_base64",
            self.runtime_config.terminal_hub_return_base64_by_default,
        )

        if not cmd or not isinstance(cmd, str):
            raise ValueError("cmd is required and must be string")
        if not isinstance(args, list) or not all(isinstance(i, str) for i in args):
            raise ValueError("args must be string array")
        if not isinstance(include_screenshot_base64, bool):
            raise ValueError("include_screenshot_base64 must be boolean")

        self._check_tool_allowed(cmd)

        if len(self.sessions) >= self.max_sessions:
            raise RuntimeError("max sessions reached")

        session_id = str(uuid.uuid4())
        session = TerminalSession(
            session_id=session_id,
            command=[cmd, *args],
            created_at=time.time(),
        )
        self.sessions[session_id] = session

        asyncio.create_task(
            self._run_session_async(
                session_id,
                auto_screenshot,
                include_screenshot_base64,
            )
        )

        return {
            "session_id": session_id,
            "status": "running",
            "view_url": f"/terminal-hub/ui?session_id={session_id}",
        }

    @tool_action("get_session", "Get terminal session detail")
    async def get_session(self, params: Dict[str, Any]) -> Dict[str, Any]:
        session_id = params.get("session_id")
        include_screenshot_base64 = params.get(
            "include_screenshot_base64",
            self.runtime_config.terminal_hub_return_base64_by_default,
        )
        if not session_id or session_id not in self.sessions:
            raise ValueError("session not found")
        if not isinstance(include_screenshot_base64, bool):
            raise ValueError("include_screenshot_base64 must be boolean")

        s = self.sessions[session_id]
        return {
            "session_id": s.session_id,
            "command": s.command,
            "status": s.status,
            "return_code": s.return_code,
            "stdout": s.stdout,
            "stderr": s.stderr,
            "created_at": datetime.fromtimestamp(s.created_at).isoformat(),
            "finished_at": datetime.fromtimestamp(s.finished_at).isoformat() if s.finished_at else None,
            "screenshot_base64": s.screenshot_base64 if include_screenshot_base64 else None,
            "screenshot_path": s.screenshot_path,
            "image_url": s.image_url,
        }

    @tool_action("list_sessions", "List all terminal sessions")
    async def list_sessions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "count": len(self.sessions),
            "items": [
                {
                    "session_id": s.session_id,
                    "status": s.status,
                    "command": s.command,
                    "created_at": datetime.fromtimestamp(s.created_at).isoformat(),
                }
                for s in self.sessions.values()
            ],
        }

    async def _run_session_sync(
        self,
        session_id: str,
        timeout: int = 60,
        use_input_pipe: bool = False,
        inputs: List[str] = None,
        include_screenshot_base64: bool = False,
    ) -> None:
        """同步执行并等待完成（用于 run_cli）"""
        s = self.sessions[session_id]
        inputs = inputs or []
        # 将 inputs 记录在 stdout_data 中以模拟在终端中看到自己的输入
        interactive_log = b""
        
        try:
            stdin_arg = asyncio.subprocess.PIPE if use_input_pipe else None
            proc = await asyncio.create_subprocess_exec(
                *s.command,
                stdin=stdin_arg,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=os.setsid if os.name != 'nt' else None,  # 让进程成为新的进程组组长，以便发送信号给进程组
            )
            
            # 使用流读取以便在超时前捕获部分输出
            stdout_data = b""
            stderr_data = b""

            async def read_stream(stream, is_stdout):
                nonlocal stdout_data, stderr_data
                while True:
                    chunk = await stream.read(4096)
                    if not chunk:
                        break
                    if is_stdout:
                        stdout_data += chunk
                    else:
                        stderr_data += chunk

            read_tasks = []
            if proc.stdout:
                read_tasks.append(asyncio.create_task(read_stream(proc.stdout, True)))
            if proc.stderr:
                read_tasks.append(asyncio.create_task(read_stream(proc.stderr, False)))

            try:
                # 写入输入（如果需要）
                if use_input_pipe and proc.stdin:
                    if inputs:
                        await asyncio.sleep(0.5)
                        for inp in inputs:
                            if inp.strip().lower() == "quit":
                                # 如果是 quit，直接发送 Ctrl+C 并终止循环
                                if os.name != 'nt':
                                    import signal
                                    try:
                                        os.killpg(os.getpgid(proc.pid), signal.SIGINT)
                                    except ProcessLookupError:
                                        proc.kill()
                                else:
                                    proc.terminate()
                                interactive_log += b"^C\n"
                                break
                            
                            # 正常的交互输入
                            proc.stdin.write(f"{inp}\n".encode('utf-8'))
                            await proc.stdin.drain()
                            interactive_log += f"{inp}\n".encode('utf-8')
                            await asyncio.sleep(0.2)
                    
                    if not proc.stdin.is_closing():
                        proc.stdin.close()
                
                # 等待读取和进程结束
                await asyncio.wait_for(asyncio.gather(*read_tasks, proc.wait()), timeout=timeout)
                s.return_code = proc.returncode
                s.status = "finished"
            except asyncio.TimeoutError:
                # 发生超时，发送 SIGINT (Ctrl+C)
                if os.name != 'nt':
                    import signal
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGINT)
                    except ProcessLookupError:
                        proc.kill()
                else:
                    proc.terminate()
                
                # 给进程一点时间来处理 SIGINT 并退出
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    # 如果仍然没有退出，强制 kill
                    if os.name != 'nt':
                        try:
                            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                        except ProcessLookupError:
                            proc.kill()
                    else:
                        proc.kill()
                    await proc.wait()
                
                # 取消未完成的读取任务
                for t in read_tasks:
                    if not t.done():
                        t.cancel()

                s.status = "finished"
                s.return_code = proc.returncode
                # 标记 stderr 表明是超时退出
                stderr_data += b"\n[terminal] Ctrl+C"

            # 将交互记录附加在真实输出的末尾
            # 这不是最完美的终端模拟（真实的终端输入和输出是交织的），但能满足在截图中看到输入的需求
            s.stdout = (f"\n{interactive_log.decode('utf-8')}" if interactive_log else "") + stdout_data.decode("utf-8", errors="replace")
            s.stderr = stderr_data.decode("utf-8", errors="replace")
            s.finished_at = time.time()

            screenshot_path, screenshot_base64 = await asyncio.get_event_loop().run_in_executor(
                None,
                self._render_terminal_screenshot,
                s,
            )
            s.screenshot_path = screenshot_path
            s.screenshot_base64 = screenshot_base64 if include_screenshot_base64 else None

            if screenshot_base64:
                try:
                    file_bytes = base64.b64decode(screenshot_base64)
                    s.image_url = upload_and_get_url(file_bytes)
                except Exception as e:
                    self.logger.warning(f"image upload failed: {e}")

        except Exception as e:
            s.status = "failed"
            s.stderr = f"[terminal_hub_error] {str(e)}"
            s.finished_at = time.time()

    async def _run_session_async(
        self,
        session_id: str,
        auto_screenshot: bool,
        include_screenshot_base64: bool,
    ) -> None:
        """异步执行（用于 create_session）"""
        s = self.sessions[session_id]
        try:
            proc = await asyncio.create_subprocess_exec(
                *s.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await proc.communicate()
            s.stdout = stdout_b.decode("utf-8", errors="replace")
            s.stderr = stderr_b.decode("utf-8", errors="replace")
            s.return_code = proc.returncode
            s.status = "finished"
            s.finished_at = time.time()

            if auto_screenshot:
                screenshot_path, screenshot_base64 = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._render_terminal_screenshot,
                    s,
                )
                s.screenshot_path = screenshot_path
                s.screenshot_base64 = screenshot_base64 if include_screenshot_base64 else None

                if screenshot_base64:
                    try:
                        file_bytes = base64.b64decode(screenshot_base64)
                        s.image_url = upload_and_get_url(file_bytes)
                    except Exception as e:
                        self.logger.warning(f"image upload failed: {e}")
        except Exception as e:
            s.status = "failed"
            s.stderr += f"\n[terminal_hub_error] {str(e)}"
            s.finished_at = time.time()

    def _render_terminal_screenshot(self, session: TerminalSession) -> tuple[str, str]:
        """渲染纯黑底终端截图（无 session 元信息）"""
        html = self._build_terminal_html(session)
        artifacts_dir = Path("artifacts") / "terminal" / session.session_id
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        html_path = artifacts_dir / "view.html"
        png_path = artifacts_dir / "terminal.png"
        html_path.write_text(html, encoding="utf-8")

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1600,900")

        chromedriver_path = os.environ.get("CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver")
        chromium_binary = os.environ.get("CHROMIUM_BINARY", "/usr/bin/chromium")
        if os.path.exists(chromium_binary):
            options.binary_location = chromium_binary

        driver = None
        try:
            if os.path.exists(chromedriver_path):
                service = Service(executable_path=chromedriver_path)
                driver = webdriver.Chrome(service=service, options=options)
            else:
                driver = webdriver.Chrome(options=options)

            driver.get(f"file://{html_path.resolve()}")
            time.sleep(0.2)
            driver.save_screenshot(str(png_path))
        finally:
            if driver:
                driver.quit()

        data = png_path.read_bytes()
        return str(png_path), base64.b64encode(data).decode("utf-8")

    def _build_terminal_html(self, session: TerminalSession) -> str:
        """
        构建纯黑底终端样式 HTML（无 session/status 元信息）。
        模拟真实终端：仅显示 prompt + stdout + stderr。
        """
        def esc(text: str) -> str:
            return (text or "").replace("&", "&").replace("<", "<").replace(">", ">")

        prompt = "$ " + " ".join(session.command)
        stdout_html = esc(session.stdout)
        stderr_html = esc(session.stderr)

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Terminal</title>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      background: #000;
      overflow: hidden;
    }}
    body {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 14px;
      line-height: 1.3;
      color: #d1ffd1;
      background: #000;
      padding: 12px 16px;
      white-space: pre-wrap;
      word-break: break-all;
    }}
    .prompt {{ color: #4ade80; }}
    .stdout {{ color: #d1ffd1; }}
    .stderr {{ color: #ff6b6b; }}
  </style>
</head>
<body>
<span class="prompt">{esc(prompt)}</span>

<span class="stdout">{stdout_html}</span>
<span class="stderr">{stderr_html}</span>
</body>
</html>"""
