"""
Screenshot Tool Service - 截图工具服务

本工具提供两种截图功能：
1. 无头浏览器网页截图
2. Burp风格的HTTP请求/响应截图
"""

import asyncio
import base64
import json
import logging
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import html as html_module
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

from core.base_tool_service import BaseToolService, tool_action
from core.config import ToolConfig
from core.image_hosting import upload_and_get_url


class BurpStyleHTMLRenderer:
    """BurpSuite风格的HTML渲染器"""
    
    def __init__(self):
        pass
    
    def _escape_html(self, text: str) -> str:
        """转义HTML特殊字符"""
        if not text:
            return ''
        return html_module.escape(text)
    
    def _highlight_text(self, text: str, highlights: List[str]) -> str:
        """在文本中高亮显示指定的字符串"""
        if not highlights:
            return self._escape_html(text)
        
        # 按长度降序排序,避免替换子串
        sorted_highlights = sorted([h for h in highlights if h], key=len, reverse=True)
        
        # 创建所有高亮位置的列表
        segments = []
        last_pos = 0
        
        for highlight in sorted_highlights:
            pos = 0
            while True:
                pos = text.find(highlight, pos)
                if pos == -1:
                    break
                segments.append((pos, pos + len(highlight), highlight))
                pos += len(highlight)
        
        # 按位置排序并合并重叠区域
        segments.sort()
        merged = []
        for start, end, hl in segments:
            if merged and start < merged[-1][1]:
                # 重叠,扩展前一个区域
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]), merged[-1][2])
            else:
                merged.append((start, end, hl))
        
        # 构建最终HTML
        result = ''
        last_pos = 0
        for start, end, hl in merged:
            result += self._escape_html(text[last_pos:start])
            result += f'<span class="user-highlight">{self._escape_html(text[start:end])}</span>'
            last_pos = end
        result += self._escape_html(text[last_pos:])
        
        return result
    
    def _parse_cookie_value(self, value: str) -> str:
        """解析并高亮Cookie值"""
        parts = value.split(';')
        result_parts = []
        
        for part in parts:
            eq_index = part.find('=')
            if eq_index > -1:
                key = part[:eq_index]
                val = part[eq_index + 1:]
                result_parts.append(
                    f'<span class="cookie-key">{self._escape_html(key)}</span>'
                    f'<span class="punct">=</span>'
                    f'<span class="cookie-val">{self._escape_html(val)}</span>'
                )
            else:
                result_parts.append(f'<span class="cookie-val">{self._escape_html(part)}</span>')
        
        return '<span class="punct">;</span>'.join(result_parts)
    
    def _render_http_lines(self, raw_data: str, highlights: List[str] = None) -> tuple:
        """渲染HTTP数据为HTML行"""
        if not raw_data:
            return '<div class="code-line"><div class="line-number">1</div><div class="line-content">&nbsp;</div></div>', 1
        
        lines = raw_data.split('\n')
        html_lines = []
        is_body = False
        
        for index, line in enumerate(lines):
            line_num = index + 1
            content_html = ''
            
            if is_body:
                # Body部分:直接显示,应用高亮
                content_html = self._highlight_text(line, highlights) if highlights else self._escape_html(line)
            else:
                if line.strip() == '':
                    # 空行标志着body开始
                    is_body = True
                    content_html = '&nbsp;'
                else:
                    # Header解析
                    if index == 0 and ': ' not in line:
                        # 请求行或状态行
                        highlighted = self._highlight_text(line, highlights) if highlights else self._escape_html(line)
                        content_html = f'<span class="http-method">{highlighted}</span>'
                    else:
                        colon_index = line.find(':')
                        if colon_index > -1:
                            key = line[:colon_index]
                            val = line[colon_index + 1:]
                            key_lower = key.lower().strip()
                            
                            # Cookie特殊处理
                            if key_lower in ['cookie', 'set-cookie']:
                                val_html = self._parse_cookie_value(val)
                            else:
                                val_html = self._highlight_text(val, highlights) if highlights else self._escape_html(val)
                            
                            key_html = self._highlight_text(key, highlights) if highlights else self._escape_html(key)
                            content_html = (
                                f'<span class="header-key">{key_html}</span>'
                                f'<span class="punct">:</span>'
                                f'<span class="header-val">{val_html}</span>'
                            )
                        else:
                            content_html = self._highlight_text(line, highlights) if highlights else self._escape_html(line)
            
            html_lines.append(
                f'<div class="code-line">'
                f'<div class="line-number">{line_num}</div>'
                f'<div class="line-content">{content_html}</div>'
                f'</div>'
            )
        
        return ''.join(html_lines), len(lines)
    
    def _get_css(self) -> str:
        """获取CSS样式"""
        css = """
        :root {
            --bg-color: #f5f5f5;
            --panel-bg: #ffffff;
            --text-color: #333333;
            --border-color: #d0d0d0;
            --line-num-color: #999999;
            --line-num-bg: #f8f8f8;
            --header-key-color: #000080;
            --header-val-color: #333333;
            --cookie-key-color: #001080;
            --cookie-val-color: #a31515;
            --method-color: #d15704;
            --url-color: #333333;
            --search-highlight-bg: #ffeb3b;
            --search-highlight-text: #000000;
            --tab-bg: #e8e8e8;
            --tab-active-bg: #ffffff;
            --tab-text: #666666;
            --tab-active-text: #333333;
            --status-bar-bg: #f0f0f0;
            --status-bar-text: #666666;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 12px;
            background-color: var(--bg-color);
            color: var(--text-color);
            height: 100vh;
            overflow: hidden;
        }
        
        .container {
            display: flex;
            height: 100%;
            width: 100%;
        }
        
        .panel {
            flex: 1;
            display: flex;
            flex-direction: column;
            border-right: 1px solid var(--border-color);
            background-color: var(--panel-bg);
            min-width: 0;
        }
        
        .panel:last-child {
            border-right: none;
        }
        
        .panel-header {
            background-color: #f0f0f0;
            padding: 0 8px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: flex-end;
            height: 28px;
            flex-shrink: 0;
        }
        
        .panel-title {
            font-weight: bold;
            color: #333333;
            font-size: 11px;
            margin-right: 15px;
            padding-bottom: 6px;
        }
        
        .tabs {
            display: flex;
            gap: 1px;
            height: 100%;
        }
        
        .tab {
            padding: 6px 12px;
            background-color: var(--tab-bg);
            cursor: pointer;
            font-size: 10px;
            color: var(--tab-text);
            border-top-left-radius: 3px;
            border-top-right-radius: 3px;
            margin-right: 1px;
            display: flex;
            align-items: center;
        }
        
        .tab.active {
            background-color: var(--panel-bg);
            color: var(--tab-active-text);
        }
        
        .panel-content {
            flex: 1;
            overflow-y: auto;
            padding: 5px 0;
            position: relative;
        }
        
        .code-view {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 11px;
            line-height: 1.3;
            tab-size: 4;
            display: block;
        }
        
        .code-line {
            display: flex;
            padding: 0;
            margin: 0;
            width: 100%;
        }
        
        .code-line:first-child {
            margin-top: 0;
        }
        
        .code-line:hover {
            background-color: #f5f5f5;
        }
        
        .line-number {
            color: var(--line-num-color);
            background-color: var(--line-num-bg);
            text-align: right;
            padding: 0 8px 0 10px;
            min-width: 40px;
            user-select: none;
            border-right: 1px solid #e0e0e0;
            flex-shrink: 0;
            font-size: 10px;
        }
        
        .line-content {
            padding-left: 8px;
            padding-right: 8px;
            flex: 1;
            white-space: pre-wrap;
            word-break: break-all;
            overflow-wrap: break-word;
            color: var(--text-color);
        }

        .http-method { color: var(--method-color); font-weight: bold; }
        .http-url { color: var(--url-color); }
        .header-key { color: var(--header-key-color); font-weight: bold; }
        .header-val { color: var(--header-val-color); }
        .cookie-key { color: var(--cookie-key-color); }
        .cookie-val { color: var(--cookie-val-color); }
        .punct { color: #cccccc; }

        .user-highlight {
            background-color: var(--search-highlight-bg);
            color: var(--search-highlight-text);
            border-radius: 2px;
            font-weight: bold;
            box-shadow: 0 0 2px rgba(241, 196, 15, 0.5);
        }
        
        .status-bar {
            background-color: var(--status-bar-bg);
            color: var(--status-bar-text);
            padding: 2px 8px;
            font-size: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            height: 20px;
            flex-shrink: 0;
        }

        ::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }
        ::-webkit-scrollbar-track {
            background: #f1f1f1; 
        }
        ::-webkit-scrollbar-thumb {
            background: #c1c1c1; 
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #a8a8a8; 
        }
        ::-webkit-scrollbar-corner {
            background: #f1f1f1;
        }
        """
        return css
    
    def _generate_html(self,
                      request_html: str,
                      response_html: str,
                      request_lines: int,
                      response_lines: int,
                      elapsed_ms: int = None,
                      is_retest: bool = False,
                      original_status: str = None) -> str:
        """生成完整的HTML文档"""
        
        css = self._get_css()
        elapsed_text = f'{elapsed_ms} ms' if elapsed_ms is not None else ''
        
        retest_banner = ""
        if is_retest:
            banner_color = "#e6f7ff"
            border_color = "#91d5ff"
            text_color = "#0050b3"
            
            retest_info = "RETEST EXECUTION"
            if original_status:
                retest_info += f" | Previous Status: {original_status}"
            
            retest_banner = f"""
            <div style="background-color: {banner_color}; border-bottom: 1px solid {border_color}; color: {text_color}; padding: 5px 10px; font-weight: bold; font-family: sans-serif; font-size: 12px; display: flex; justify-content: space-between; align-items: center;">
                <span>🛡️ VULNERABILITY RETEST</span>
                <span>{retest_info}</span>
                <span>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
            </div>
            """
        
        return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        {css}
    </style>
</head>
<body>
    {retest_banner}
    <div class="container" style="{'height: calc(100% - 28px);' if is_retest else 'height: 100%;'}">
        <!-- Request Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">Request</span>
                <div class="tabs">
                    <div class="tab">Pretty</div>
                    <div class="tab active">Raw</div>
                    <div class="tab">Hex</div>
                </div>
            </div>
            <div class="panel-content">
                <div class="code-view">
                    {request_html}
                </div>
            </div>
            <div class="status-bar">
                <span>{request_lines} lines</span>
            </div>
        </div>
        
        <!-- Response Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">Response</span>
                <div class="tabs">
                    <div class="tab">Pretty</div>
                    <div class="tab active">Raw</div>
                    <div class="tab">Hex</div>
                    <div class="tab">Render</div>
                </div>
            </div>
            <div class="panel-content">
                <div class="code-view">
                    {response_html}
                </div>
            </div>
            <div class="status-bar">
                <span>{response_lines} lines</span>
                <span style="opacity: 0.9;">{elapsed_text}</span>
            </div>
        </div>
    </div>
</body>
</html>
'''


class ScreenshotToolService(BaseToolService):
    """
    截图工具服务类
    
    提供两种截图功能：
    1. 无头浏览器网页截图
    2. Burp风格的HTTP请求/响应截图
    """
    
    def __init__(self):
        super().__init__("screenshot", "1.1.0")
        self.renderer = BurpStyleHTMLRenderer()
        self.runtime_config = ToolConfig()
        self.screenshot_semaphore = asyncio.Semaphore(
            self.runtime_config.screenshot_max_concurrency
        )
        self.executor = ThreadPoolExecutor(
            max_workers=self.runtime_config.screenshot_executor_workers,
            thread_name_prefix="screenshot-worker",
        )
        self.logger.info("Screenshot tool service initialized")

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Legacy parameter validation - kept for backward compatibility"""
        return True

    async def _execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy execution method - not used with new action pattern"""
        raise NotImplementedError("Use action-based methods instead")

    @tool_action("web_screenshot", "Capture screenshot of a webpage using headless browser")
    async def capture_web_screenshot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用无头浏览器捕获网页截图

        参数:
            url (str): 目标网页URL（必需）
            method (str): 请求方法，默认 GET
            headers (dict): 自定义请求头（可选）
            body (str | dict | list): 请求体（可选，复杂请求场景）
            cookies (dict): 请求 Cookie（可选）
            loading_strategy (str): 页面加载策略，可选值: none, eager, normal（默认: none）
            sleep_time (int): 页面加载后的等待时间（秒）（默认: 0）
            user_agent (str): 自定义用户代理字符串（可选）
            window_size (str): 浏览器窗口大小，格式: "宽,高"（默认: "1920,1080"）
            include_screenshot_base64 (bool): 是否返回 Base64 编码截图（默认: True）

        返回:
            screenshot (str): Base64编码的截图数据（当 include_screenshot_base64 为 True 时返回）
            image_url (str): 图片链接（如果上传成功）
            message (str): 处理信息
        """
        url = params.get("url")
        if not url:
            raise ValueError("url parameter is required")

        if not isinstance(url, str):
            raise ValueError("url must be a string")

        method = str(params.get("method", "GET")).upper()
        headers = params.get("headers")
        body = params.get("body")
        cookies = params.get("cookies")
        loading_strategy = params.get("loading_strategy", "none")
        sleep_time = int(params.get("sleep_time", 0))
        user_agent = params.get("user_agent")
        window_size = params.get("window_size", "1920,1080")
        include_screenshot_base64 = params.get(
            "include_screenshot_base64",
            self.runtime_config.screenshot_return_base64_by_default,
        )

        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            raise ValueError("method must be one of: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS")
        if headers is not None and not isinstance(headers, dict):
            raise ValueError("headers must be an object")
        if cookies is not None and not isinstance(cookies, dict):
            raise ValueError("cookies must be an object")
        if body is not None and not isinstance(body, (str, dict, list)):
            raise ValueError("body must be a string, object, or array")
        if not isinstance(include_screenshot_base64, bool):
            raise ValueError("include_screenshot_base64 must be a boolean")

        # 验证参数
        if loading_strategy not in ['none', 'eager', 'normal']:
            raise ValueError("loading_strategy must be one of: none, eager, normal")

        if not isinstance(sleep_time, int) or sleep_time < 0:
            raise ValueError("sleep_time must be a non-negative integer")
        if sleep_time > self.runtime_config.screenshot_max_sleep_time:
            raise ValueError(
                f"sleep_time must be less than or equal to {self.runtime_config.screenshot_max_sleep_time}"
            )

        has_complex_request = (
            method != "GET"
            or (headers is not None and len(headers) > 0)
            or body is not None
            or (cookies is not None and len(cookies) > 0)
        )
        self.logger.info(f"Capturing screenshot for URL: {url}, method: {method}")

        try:
            async with self.screenshot_semaphore:
                screenshot = await asyncio.get_running_loop().run_in_executor(
                    self.executor,
                    self._take_screenshot,
                    url,
                    method,
                    headers,
                    body,
                    cookies,
                    loading_strategy,
                    sleep_time,
                    user_agent,
                    window_size,
                )

            if screenshot:
                self.logger.info("Screenshot captured successfully")

                image_url = None
                file_content = base64.b64decode(screenshot)
                if self.runtime_config.screenshot_upload_enabled:
                    try:
                        self.logger.info("Uploading screenshot to image hosting service...")
                        image_url = await asyncio.get_running_loop().run_in_executor(
                            self.executor,
                            upload_and_get_url,
                            file_content,
                        )
                        if image_url:
                            self.logger.info(f"Screenshot uploaded successfully: {image_url}")
                        else:
                            self.logger.warning("Failed to upload screenshot: No URL returned")
                    except Exception as e:
                        self.logger.warning(f"Error uploading screenshot: {str(e)}")

                result = {
                    "image_url": image_url,
                    "message": "Screenshot captured successfully",
                    "request_mode": "complex" if has_complex_request else "navigate"
                }
                if include_screenshot_base64:
                    result["screenshot"] = screenshot
                return result
            else:
                raise RuntimeError("Failed to capture screenshot")

        except Exception as e:
            self.logger.error(f"Screenshot capture failed: {str(e)}", exc_info=True)
            raise RuntimeError(f"Screenshot capture failed: {str(e)}")

    def _take_screenshot(self, url: str, method: str, headers: Optional[Dict[str, Any]],
                        body: Optional[Any], cookies: Optional[Dict[str, Any]],
                        loading_strategy: str, sleep_time: int,
                        user_agent: Optional[str], window_size: str) -> str:
        """
        捕获网页截图的同步函数
        
        参数:
            url: 目标网页URL
            method: HTTP 请求方法
            headers: 自定义请求头
            body: 请求体
            cookies: Cookie 字典
            loading_strategy: 页面加载策略
            sleep_time: 页面加载后的等待时间(秒)
            user_agent: 自定义用户代理字符串
            window_size: 浏览器窗口大小
        
        返回:
            Base64编码的截图数据
        """
        driver = None
        temp_render_path: Optional[Path] = None
        try:
            # 初始化Chrome选项
            options = Options()
            options.headless = True
            options.page_load_strategy = loading_strategy
            
            # 添加通用参数
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument(f'--window-size={window_size}')
            options.add_argument('--ignore-certificate-errors')
            
            # 设置用户代理
            if user_agent:
                options.add_argument(f'user-agent={user_agent}')
            else:
                default_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
                options.add_argument(f'user-agent={default_ua}')
            
            # 初始化WebDriver - 多种方式尝试
            driver = self._init_webdriver(options)
            driver.set_page_load_timeout(self.runtime_config.screenshot_page_load_timeout)

            if method == "GET" and not headers and body is None and not cookies:
                # 访问目标URL（兼容旧逻辑）
                self.logger.info(f"Loading URL: {url}")
                driver.get(url)
            else:
                # 复杂请求：先发 HTTP 请求，再把响应渲染为 HTML 截图
                self.logger.info(f"Executing complex request screenshot flow: {method} {url}")
                response = self._send_http_request(url, method, headers, body, cookies, user_agent)
                rendered_html = self._build_response_render_page(url, method, response)
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as rendered_file:
                    rendered_file.write(rendered_html)
                    temp_render_path = Path(rendered_file.name)
                driver.get(temp_render_path.as_uri())
            
            # 等待页面加载
            if sleep_time > 0:
                self.logger.info(f"Sleeping for {sleep_time} seconds...")
                time.sleep(sleep_time)
            
            # 等待页面元素加载完成
            try:
                WebDriverWait(driver, self.runtime_config.screenshot_element_wait_timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except Exception as e:
                self.logger.warning(f"Page load timeout or error: {str(e)}")
            
            # 截图并转换为Base64
            screenshot = driver.get_screenshot_as_base64()
            self.logger.info("Screenshot captured successfully")
            
            return screenshot
        
        except Exception as e:
            self.logger.error(f"Screenshot error: {str(e)}", exc_info=True)
            raise
        finally:
            if driver:
                driver.quit()
            if temp_render_path and temp_render_path.exists():
                try:
                    temp_render_path.unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to clean temporary rendered file: {str(e)}")

    def _send_http_request(self,
                           url: str,
                           method: str,
                           headers: Optional[Dict[str, Any]],
                           body: Optional[Any],
                           cookies: Optional[Dict[str, Any]],
                           user_agent: Optional[str]) -> requests.Response:
        request_headers = {str(k): str(v) for k, v in (headers or {}).items()}
        request_cookies = {str(k): str(v) for k, v in (cookies or {}).items()}

        if user_agent and "User-Agent" not in request_headers and "user-agent" not in request_headers:
            request_headers["User-Agent"] = user_agent

        request_kwargs: Dict[str, Any] = {
            "headers": request_headers,
            "cookies": request_cookies,
            "timeout": self.runtime_config.screenshot_request_timeout,
            "allow_redirects": True,
            "verify": False,
        }

        if body is not None:
            content_type = request_headers.get("Content-Type", request_headers.get("content-type", "")).lower()
            if isinstance(body, str):
                request_kwargs["data"] = body
            elif isinstance(body, (dict, list)):
                if "application/x-www-form-urlencoded" in content_type:
                    request_kwargs["data"] = body
                else:
                    request_kwargs["json"] = body

        response = requests.request(method=method, url=url, **request_kwargs)
        return response

    def _build_response_render_page(self, url: str, method: str, response: requests.Response) -> str:
        content_type = response.headers.get("Content-Type", "").lower()
        final_url = response.url or url

        if "text/html" in content_type:
            html_text = response.text
            base_tag = f'<base href="{html_module.escape(final_url, quote=True)}">'
            if "<head" in html_text.lower():
                head_close_index = html_text.lower().find(">", html_text.lower().find("<head"))
                if head_close_index != -1:
                    return html_text[:head_close_index + 1] + base_tag + html_text[head_close_index + 1:]
            return f"<html><head>{base_tag}</head><body>{html_text}</body></html>"

        response_body = response.text
        if "application/json" in content_type:
            try:
                response_body = json.dumps(response.json(), ensure_ascii=False, indent=2)
            except Exception:
                response_body = response.text

        escaped_body = html_module.escape(response_body)
        escaped_url = html_module.escape(final_url)
        escaped_method = html_module.escape(method)

        return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset=\"UTF-8\" />
  <title>HTTP Response Render</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background: #f6f8fa; }}
    .meta {{ background: #fff; border-bottom: 1px solid #d0d7de; padding: 12px 16px; font-size: 13px; color: #24292f; }}
    .status {{ font-weight: 600; margin-bottom: 6px; }}
    .url {{ color: #57606a; word-break: break-all; }}
    pre {{ margin: 0; padding: 16px; white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class=\"meta\">
    <div class=\"status\">{escaped_method} {response.status_code} {html_module.escape(response.reason or '')}</div>
    <div class=\"url\">{escaped_url}</div>
  </div>
  <pre>{escaped_body}</pre>
</body>
</html>
"""

    def _normalize_input(self, text: str) -> str:
        """
        标准化输入文本：
        1. 替换转义的换行符为真实换行符
        2. 处理转义的双引号等特殊字符
        """
        if not text:
            return ""
        
        # 替换转义的换行符
        # 先把 \\n (字面量 \n) 替换为 \n (真实换行)
        text = text.replace('\\n', '\n').replace('\\r', '')
        
        # 处理转义的双引号 \" -> "
        text = text.replace('\\"', '"')
        
        return text

    @tool_action("burp_screenshot", "Create Burp-style screenshot of HTTP request/response")
    async def create_burp_screenshot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建BurpSuite风格的HTTP请求/响应截图
        
        参数:
            request_data (str): HTTP请求数据（必需）
            response_data (str): HTTP响应数据（必需）
            request_highlights (list): 请求中需要高亮的字符串列表（可选）
            response_highlights (list): 响应中需要高亮的字符串列表（可选）
            width (int): 截图宽度（默认: 1920）
            height (int): 截图高度（默认: 1080）
            elapsed_ms (int): 请求耗时（毫秒）（可选）
            is_retest (bool): 是否为重新测试（默认: False）
            original_status (str): 原始状态（可选）
            include_screenshot_base64 (bool): 是否返回 Base64 编码截图（默认: True）
        
        返回:
            screenshot (str): Base64编码的截图数据（当 include_screenshot_base64 为 True 时返回）
            filename (str): 截图文件名
            file_size (int): 文件大小（字节）
            image_url (str): 图片链接（如果上传成功）
            message (str): 处理信息
        """
        request_data = params.get("request_data")
        response_data = params.get("response_data")
        
        if not request_data:
            raise ValueError("request_data parameter is required")
        if not response_data:
            raise ValueError("response_data parameter is required")
        
        if not isinstance(request_data, str):
            raise ValueError("request_data must be a string")
        if not isinstance(response_data, str):
            raise ValueError("response_data must be a string")
        
        # 1. & 2. 规范化输入：处理换行符和转义字符
        request_data = self._normalize_input(request_data)
        response_data = self._normalize_input(response_data)
        
        request_highlights = params.get("request_highlights")
        response_highlights = params.get("response_highlights")
        include_screenshot_base64 = params.get(
            "include_screenshot_base64",
            self.runtime_config.screenshot_return_base64_by_default,
        )
        
        # 规范化高亮内容
        if request_highlights:
            request_highlights = [self._normalize_input(h) for h in request_highlights if h]
        if response_highlights:
            response_highlights = [self._normalize_input(h) for h in response_highlights if h]
            
        width = int(params.get("width", 1920))
        height = int(params.get("height", 1080))
        elapsed_ms = params.get("elapsed_ms")
        is_retest = params.get("is_retest", False)
        original_status = params.get("original_status")
        
        # 验证参数
        if not isinstance(include_screenshot_base64, bool):
            raise ValueError("include_screenshot_base64 must be a boolean")
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive integers")
        
        self.logger.info("Creating Burp-style screenshot")
        
        try:
            async with self.screenshot_semaphore:
                result = await asyncio.get_running_loop().run_in_executor(
                    self.executor,
                    self._render_burp_screenshot,
                    request_data,
                    response_data,
                    request_highlights,
                    response_highlights,
                    width,
                    height,
                    elapsed_ms,
                    is_retest,
                    original_status
                )
            
            if result.get("success"):
                # 读取截图文件
                screenshot_path = result["local_path"]
                with open(screenshot_path, "rb") as f:
                    file_content = f.read()
                
                # 转换为Base64
                screenshot_base64 = base64.b64encode(file_content).decode('utf-8')
                
                image_url = None
                if self.runtime_config.screenshot_upload_enabled:
                    try:
                        self.logger.info("Uploading screenshot to image hosting service...")
                        image_url = await asyncio.get_running_loop().run_in_executor(
                            self.executor,
                            upload_and_get_url,
                            file_content,
                        )
                        if image_url:
                            self.logger.info(f"Screenshot uploaded successfully: {image_url}")
                        else:
                            self.logger.warning("Failed to upload screenshot: No URL returned")
                    except Exception as e:
                        self.logger.warning(f"Error uploading screenshot: {str(e)}")
                
                # 删除临时文件
                try:
                    os.unlink(screenshot_path)
                except Exception as e:
                    self.logger.warning(f"Failed to delete temporary file: {str(e)}")
                
                self.logger.info(f"Burp-style screenshot created successfully: {result['filename']}")
                
                response_data = {
                    "filename": result["filename"],
                    "file_size": result["file_size"],
                    "image_url": image_url,
                    "message": "Burp-style screenshot created successfully"
                }
                if include_screenshot_base64:
                    response_data["screenshot"] = screenshot_base64
                return response_data
            else:
                raise RuntimeError(result.get("error", "Failed to create screenshot"))
                
        except Exception as e:
            self.logger.error(f"Burp screenshot creation failed: {str(e)}", exc_info=True)
            raise RuntimeError(f"Burp screenshot creation failed: {str(e)}")

    def _render_burp_screenshot(self,
                               request_data: str,
                               response_data: str,
                               request_highlights: List[str],
                               response_highlights: List[str],
                               width: int,
                               height: int,
                               elapsed_ms: int,
                               is_retest: bool,
                               original_status: str) -> Dict[str, Any]:
        """
        渲染Burp风格截图的同步函数
        
        参数:
            request_data: HTTP请求数据
            response_data: HTTP响应数据
            request_highlights: 请求高亮列表
            response_highlights: 响应高亮列表
            width: 截图宽度
            height: 截图高度
            elapsed_ms: 请求耗时
            is_retest: 是否为重新测试
            original_status: 原始状态
        
        返回:
            包含截图信息的字典
        """
        html_path = None
        screenshot_path = None
        driver = None
        
        try:
            self.logger.info("开始生成截图")
            
            # 生成HTML内容
            request_html, request_lines = self.renderer._render_http_lines(request_data, request_highlights)
            response_html, response_lines = self.renderer._render_http_lines(response_data, response_highlights)
            
            # 生成完整HTML
            html_content = self.renderer._generate_html(
                request_html,
                response_html,
                request_lines,
                response_lines,
                elapsed_ms,
                is_retest,
                original_status
            )

            # 保存HTML到临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html_content)
                html_path = f.name
            
            self.logger.info(f"HTML临时文件已创建: {html_path}")
            
            # 配置 Chrome 选项
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument(f'--window-size={width},{height}')
            chrome_options.add_argument('--font-render-hinting=medium')
            
            # 初始化 WebDriver
            self.logger.info("正在初始化 Chrome WebDriver")
            driver = self._init_webdriver(chrome_options)
            
            # 加载HTML文件
            self.logger.info(f"加载HTML文件: file://{html_path}")
            driver.get(f'file://{html_path}')
            
            # 短暂等待确保渲染完成
            time.sleep(0.5)
            
            # 截图
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"vuln_screenshot_{timestamp}.png"
            screenshot_path = os.path.join(tempfile.gettempdir(), filename)
            
            self.logger.info(f"开始截图，保存到: {screenshot_path}")
            driver.save_screenshot(screenshot_path)
            
            # 验证截图文件
            if not os.path.exists(screenshot_path):
                raise Exception(f"截图文件未生成: {screenshot_path}")
            
            file_size = os.path.getsize(screenshot_path)
            if file_size == 0:
                raise Exception(f"截图文件为空: {screenshot_path}")
            
            self.logger.info(f"截图生成成功: {screenshot_path}, 大小: {file_size} bytes")
            
            return {
                "success": True,
                "local_path": screenshot_path,
                "filename": filename,
                "file_size": file_size
            }
                
        except Exception as e:
            self.logger.error(f"生成截图失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"生成截图失败: {str(e)}"
            }
        finally:
            # 清理资源
            if driver:
                try:
                    driver.quit()
                    self.logger.info("WebDriver 已关闭")
                except Exception as e:
                    self.logger.warning(f"关闭 WebDriver 失败: {str(e)}")
            
            # 清理HTML临时文件
            if html_path and os.path.exists(html_path):
                try:
                    os.unlink(html_path)
                    self.logger.info(f"已删除HTML临时文件: {html_path}")
                except Exception as e:
                    self.logger.warning(f"删除HTML临时文件失败: {str(e)}")
    
    def _init_webdriver(self, options: Options) -> webdriver.Chrome:
        """
        初始化 WebDriver，支持多平台自动检测
        
        参数:
            options: Chrome选项
        
        返回:
            WebDriver实例
        """
        import platform
        system = platform.system()
        
        # 尝试顺序：
        # 1. 使用 webdriver-manager 自动管理（推荐）
        # 2. 使用环境变量指定的路径
        # 3. 使用系统常见路径
        # 4. 让 Selenium 自动查找
        
        errors = []
        
        # 1. 尝试 webdriver-manager（推荐）
        if WEBDRIVER_MANAGER_AVAILABLE:
            try:
                self.logger.info("尝试使用 webdriver-manager 自动管理 ChromeDriver")
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
                self.logger.info("✓ webdriver-manager 初始化成功")
                return driver
            except Exception as e:
                error_msg = f"webdriver-manager 失败: {str(e)}"
                self.logger.warning(error_msg)
                errors.append(error_msg)
        
        # 2. 尝试环境变量
        chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')
        chromium_binary = os.environ.get('CHROMIUM_BINARY')
        
        if chromedriver_path and os.path.exists(chromedriver_path):
            try:
                self.logger.info(f"尝试使用环境变量指定的 ChromeDriver: {chromedriver_path}")
                if chromium_binary and os.path.exists(chromium_binary):
                    options.binary_location = chromium_binary
                    self.logger.info(f"使用 Chrome 二进制: {chromium_binary}")
                service = Service(executable_path=chromedriver_path)
                driver = webdriver.Chrome(service=service, options=options)
                self.logger.info("✓ 环境变量路径初始化成功")
                return driver
            except Exception as e:
                error_msg = f"环境变量路径失败: {str(e)}"
                self.logger.warning(error_msg)
                errors.append(error_msg)
        
        # 3. 尝试常见系统路径
        common_paths = []
        
        if system == "Darwin":  # macOS
            common_paths = [
                "/opt/homebrew/bin/chromedriver",  # Apple Silicon
                "/usr/local/bin/chromedriver",     # Intel Mac
            ]
            # Mac Chrome 路径
            if not options.binary_location:
                chrome_app = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
                if os.path.exists(chrome_app):
                    options.binary_location = chrome_app
        elif system == "Linux":
            common_paths = [
                "/usr/bin/chromedriver",
                "/usr/local/bin/chromedriver",
            ]
            # Linux Chromium 路径
            if not options.binary_location and os.path.exists("/usr/bin/chromium"):
                options.binary_location = "/usr/bin/chromium"
        elif system == "Windows":
            common_paths = [
                r"C:\Program Files\chromedriver.exe",
                r"C:\chromedriver\chromedriver.exe",
            ]
        
        for path in common_paths:
            if os.path.exists(path):
                try:
                    self.logger.info(f"尝试使用系统路径: {path}")
                    service = Service(executable_path=path)
                    driver = webdriver.Chrome(service=service, options=options)
                    self.logger.info(f"✓ 系统路径初始化成功: {path}")
                    return driver
                except Exception as e:
                    error_msg = f"系统路径 {path} 失败: {str(e)}"
                    self.logger.warning(error_msg)
                    errors.append(error_msg)
        
        # 4. 最后尝试让 Selenium 自动查找
        try:
            self.logger.info("尝试让 Selenium 自动查找 ChromeDriver")
            driver = webdriver.Chrome(options=options)
            self.logger.info("✓ Selenium 自动查找成功")
            return driver
        except Exception as e:
            error_msg = f"Selenium 自动查找失败: {str(e)}"
            self.logger.error(error_msg)
            errors.append(error_msg)
        
        # 所有方法都失败，抛出详细错误
        error_summary = "\n".join([f"  - {err}" for err in errors])
        raise RuntimeError(
            f"无法初始化 ChromeDriver，已尝试所有方法:\n{error_summary}\n\n"
            f"解决方案:\n"
            f"1. 安装 Chrome/Chromium 浏览器\n"
            f"2. Mac: brew install chromedriver\n"
            f"3. Linux: apt install chromium-driver\n"
            f"4. 或设置环境变量 CHROMEDRIVER_PATH\n"
            f"5. 参考文档: docs/Mac本地开发环境配置.md"
        )
