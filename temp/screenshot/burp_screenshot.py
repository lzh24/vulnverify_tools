"""
HTML+CSS渲染截图模块
使用Selenium将HTML渲染为高质量截图
纯HTML+CSS实现,无需JavaScript
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import tempfile
import os
from datetime import datetime
from typing import List, Dict, Any
import html as html_module
import time
import re


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
            --header-key-color: #000080; /* Navy Blue */
            --header-val-color: #333333;
            --cookie-key-color: #001080;
            --cookie-val-color: #a31515; /* Red */
            --method-color: #d15704; /* Orange */
            --url-color: #333333;
            --search-highlight-bg: #ffeb3b; /* Bright Yellow */
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
            min-width: 0; /* 防止内容撑开flex项 */
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
            line-height: 1.3; /* 更紧凑的行间距 */
            tab-size: 4;
            display: block; /* 确保没有额外空白 */
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

        /* Syntax Highlighting */
        .http-method { color: var(--method-color); font-weight: bold; }
        .http-url { color: var(--url-color); }
        .header-key { color: var(--header-key-color); font-weight: bold; }
        .header-val { color: var(--header-val-color); }
        .cookie-key { color: var(--cookie-key-color); }
        .cookie-val { color: var(--cookie-val-color); }
        .punct { color: #cccccc; }

        /* User Highlights */
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

        /* Scrollbar styling */
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
            banner_color = "#e6f7ff" # Light blue
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

    def render_to_image(self,
                       request_data: str,
                       response_data: str,
                       request_highlights: List[str] = None,
                       response_highlights: List[str] = None,
                       width: int = 1920,
                       height: int = 1080,
                       elapsed_ms: int = None,
                       is_retest: bool = False,
                       original_status: str = None) -> Dict[str, Any]:
        """渲染HTML到图片"""
        import logging
        logger = logging.getLogger(__name__)
        
        html_path = None
        screenshot_path = None
        driver = None
        
        try:
            logger.info("开始生成截图")
            
            # 在Python中直接生成HTML内容
            request_html, request_lines = self._render_http_lines(request_data, request_highlights)
            response_html, response_lines = self._render_http_lines(response_data, response_highlights)
            
            # 生成完整HTML
            html_content = self._generate_html(
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
            
            logger.info(f"HTML临时文件已创建: {html_path}")
            
            # 配置 Chromium 选项
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument(f'--window-size={width},{height}')
            chrome_options.add_argument('--font-render-hinting=medium')
            
            # 指定 Chromium 二进制路径
            chrome_options.binary_location = '/usr/bin/chromium'
            
            # 初始化 WebDriver - 使用系统安装的 chromium-driver
            logger.info("正在初始化 Chromium WebDriver")
            try:
                # 优先使用系统路径中的 chromium-driver
                service = Service('/usr/bin/chromedriver')
                driver = webdriver.Chrome(service=service, options=chrome_options)
                logger.info("使用系统 ChromeDriver 初始化成功")
            except Exception as e:
                logger.warning(f"系统 ChromeDriver 失败: {str(e)}, 尝试 webdriver-manager")
                # 如果失败，尝试使用 webdriver-manager 自动管理驱动
                try:
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                    logger.info("使用 webdriver-manager 初始化成功")
                except Exception as e2:
                    logger.warning(f"webdriver-manager 失败: {str(e2)}, 尝试默认路径")
                    # 最后尝试不指定 service
                    try:
                        driver = webdriver.Chrome(options=chrome_options)
                        logger.info("使用默认路径初始化成功")
                    except Exception as e3:
                        raise Exception(f"无法初始化 Chromium WebDriver: 系统驱动失败={str(e)}, webdriver-manager失败={str(e2)}, 默认路径失败={str(e3)}")
            
            # 加载HTML文件
            logger.info(f"加载HTML文件: file://{html_path}")
            driver.get(f'file://{html_path}')
            
            # 短暂等待确保渲染完成(纯HTML/CSS无需长时间等待)
            time.sleep(0.5)
            
            # 截图 - 使用 /tmp/ 目录的绝对路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"vuln_screenshot_{timestamp}.png"
            screenshot_path = os.path.join("/tmp", filename)
            
            logger.info(f"开始截图，保存到: {screenshot_path}")
            driver.save_screenshot(screenshot_path)
            
            # 验证截图文件
            if not os.path.exists(screenshot_path):
                raise Exception(f"截图文件未生成: {screenshot_path}")
            
            file_size = os.path.getsize(screenshot_path)
            if file_size == 0:
                raise Exception(f"截图文件为空: {screenshot_path}")
            
            logger.info(f"截图生成成功: {screenshot_path}, 大小: {file_size} bytes")
            
            return {
                "success": True,
                "local_path": screenshot_path,
                "filename": filename,
                "file_size": file_size
            }
                
        except Exception as e:
            logger.error(f"生成截图失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"生成截图失败: {str(e)}"
            }
        finally:
            # 清理资源
            if driver:
                try:
                    driver.quit()
                    logger.info("WebDriver 已关闭")
                except Exception as e:
                    logger.warning(f"关闭 WebDriver 失败: {str(e)}")
            
            # 清理HTML临时文件
            if html_path and os.path.exists(html_path):
                try:
                    os.unlink(html_path)
                    logger.info(f"已删除HTML临时文件: {html_path}")
                except Exception as e:
                    logger.warning(f"删除HTML临时文件失败: {str(e)}")


# 便捷函数
def create_burp_style_screenshot(request_data: str,
                                response_data: str,
                                request_highlights: List[str] = None,
                                response_highlights: List[str] = None,
                                width: int = 1920,
                                height: int = 1080,
                                elapsed_ms: int = None,
                                is_retest: bool = False,
                                original_status: str = None) -> Dict[str, Any]:
    """
    创建BurpSuite风格的截图
    """
    renderer = BurpStyleHTMLRenderer()
    return renderer.render_to_image(
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