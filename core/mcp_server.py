"""MCP Server module for Model Context Protocol integration."""

import json
import logging
import contextlib
from typing import Dict, Any, Optional, Annotated, List
from pydantic import Field
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
from starlette.requests import Request
from starlette.routing import Route, Mount
from .tool_manager import ToolManager
from .config import ToolConfig


class PathRewriteMiddleware(BaseHTTPMiddleware):
    """中间件：路径重写（已简化）。
    
    由于 FastMCP 的 streamable_http_app() 自带 /mcp 路由结构，
    且主应用已将其挂载在 /mcp 下，路径重写逻辑已不再需要。
    """
    
    async def dispatch(self, request: Request, call_next):
        # 直接传递请求，不再重写路径
        return await call_next(request)


class AuthMiddleware(BaseHTTPMiddleware):
    """中间件：强制执行 MCP 端点的身份验证。"""
    
    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token
        self.logger = logging.getLogger(__name__)
        
    async def dispatch(self, request: Request, call_next):
        # 使用 request.url.path 获取完整路径，这在 mounted app 中是包含前缀的
        # 但我们也应该检查 request.scope['path']，这是相对于当前 app 的路径
        full_path = request.url.path
        scope_path = request.scope.get("path", "")
        
        # Log request details for debugging
        self.logger.debug(f"AuthMiddleware processing request: full_path={full_path}, scope_path={scope_path}")
        
        # Allow root path and health check without authentication
        # Check both full path and relative path
        if (full_path == "/" or full_path == "/health" or
            full_path.endswith("/mcp/") or full_path.endswith("/mcp") or
            scope_path == "/" or scope_path == "/health"):
             self.logger.debug(f"Allowing request to {full_path} without authentication")
             return await call_next(request)
             
        # Authentication logic
        auth_header = request.headers.get("Authorization")
        token = None
        
        if auth_header:
            if " " in auth_header:
                token = auth_header.split(" ")[1]
            else:
                token = auth_header
        
        if not token:
            token = request.query_params.get("token")

        if not token or token != self.token:
             self.logger.warning(f"Authentication failed for full_path={full_path}, scope_path={scope_path}")
             return Response("Unauthorized", status_code=401)
             
        self.logger.debug("Authentication successful")
        response = await call_next(request)
        return response


class MCPServer:
    """MCP 服务器包装器，用于工具集成。"""
    
    # 工具描述映射表
    TOOL_DESCRIPTIONS = {
        "curl-exec": {
            "name": "Curl 执行工具",
            "description": "执行 HTTP 请求的工具，支持 curl 参数和原始 HTTP 请求包格式。适用于漏洞请求复现、攻防 PoC 生成、抓包请求标准化等场景。",
            "actions": {
                "curl_args": {
                    "name": "执行 Curl 命令",
                    "description": "使用提供的 curl 参数执行 HTTP 请求",
                    "params": {
                        "curl_args": {
                            "type": "array",
                            "description": "curl 参数列表（不含 'curl' 命令本身），例如：['http://example.com', '-X', 'POST', '-H', 'Content-Type: application/json']",
                            "required": True
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "请求超时时间（秒），默认 15 秒",
                            "required": False
                        }
                    }
                },
                "rawhttp": {
                    "name": "执行原始 HTTP 请求",
                    "description": "接收原始 HTTP 请求和 URL，转换为 curl 参数并执行",
                    "params": {
                        "url": {
                            "type": "string",
                            "description": "目标 URL（必需），例如：http://example.com",
                            "required": True
                        },
                        "raw_http": {
                            "type": "string",
                            "description": "原始 HTTP 请求文本（必需），例如：'GET /path HTTP/1.1\\nHost: example.com\\n\\n'",
                            "required": True
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "请求超时时间（秒），默认 15 秒",
                            "required": False
                        },
                        "drop_headers": {
                            "type": "array",
                            "description": "需要丢弃的 header 列表（可选），例如：['Content-Length']",
                            "required": False
                        },
                        "mask_headers": {
                            "type": "array",
                            "description": "需要脱敏的 header 列表（可选），例如：['Authorization']",
                            "required": False
                        }
                    }
                }
            }
        },
        "dnslog-service": {
            "name": "DNSLog 服务",
            "description": "提供 DNSLog 功能，用于漏洞验证。可用于检测 XXE、SSRF 和 RCE 漏洞的带外交互。",
            "actions": {
                "register": {
                    "name": "注册 DNSLog 会话",
                    "description": "注册一个新的 DNSLog 会话，获取一个唯一的域名用于检测 DNS 请求",
                    "params": {
                        "domain_prefix": {
                            "type": "string",
                            "description": "域名前缀（可选），默认为 'test'",
                            "required": False
                        }
                    }
                },
                "poll": {
                    "name": "轮询 DNSLog 交互",
                    "description": "轮询指定会话的 DNS 交互记录",
                    "params": {
                        "session_id": {
                            "type": "string",
                            "description": "会话 ID（必需），由 register 操作返回",
                            "required": True
                        }
                    }
                },
                "deregister": {
                    "name": "注销 DNSLog 会话",
                    "description": "注销指定的 DNSLog 会话",
                    "params": {
                        "session_id": {
                            "type": "string",
                            "description": "会话 ID（必需），由 register 操作返回",
                            "required": True
                        }
                    }
                }
            }
        },
        "screenshot": {
            "name": "截图工具",
            "description": "提供两种截图功能：1. 无头浏览器网页截图 2. Burp 风格的 HTTP 请求/响应截图",
            "actions": {
                "web_screenshot": {
                    "name": "网页截图",
                    "description": "使用无头浏览器捕获网页截图",
                    "params": {
                        "url": {
                            "type": "string",
                            "description": "目标网页 URL（必需），例如：https://example.com",
                            "required": True
                        },
                        "method": {
                            "type": "string",
                            "description": "HTTP 请求方法，默认：GET。支持 GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS",
                            "required": False
                        },
                        "headers": {
                            "type": "object",
                            "description": "自定义请求头（可选）",
                            "required": False
                        },
                        "body": {
                            "type": "any",
                            "description": "请求体（可选），支持字符串、对象或数组",
                            "required": False
                        },
                        "cookies": {
                            "type": "object",
                            "description": "请求 Cookie（可选）",
                            "required": False
                        },
                        "loading_strategy": {
                            "type": "string",
                            "description": "页面加载策略，可选值：none（不等待）、eager（等待 DOM 加载）、normal（等待所有资源加载），默认：none",
                            "required": False
                        },
                        "sleep_time": {
                            "type": "integer",
                            "description": "页面加载后的等待时间（秒），默认：0",
                            "required": False
                        },
                        "user_agent": {
                            "type": "string",
                            "description": "自定义用户代理字符串（可选）",
                            "required": False
                        },
                        "window_size": {
                            "type": "string",
                            "description": "浏览器窗口大小，格式：'宽,高'，默认：'1920,1080'",
                            "required": False
                        }
                    }
                },
                "burp_screenshot": {
                    "name": "Burp 风格截图",
                    "description": "创建 BurpSuite 风格的 HTTP 请求/响应截图，支持高亮显示",
                    "params": {
                        "request_data": {
                            "type": "string",
                            "description": "HTTP 请求数据（必需），原始 HTTP 请求文本",
                            "required": True
                        },
                        "response_data": {
                            "type": "string",
                            "description": "HTTP 响应数据（必需），原始 HTTP 响应文本",
                            "required": True
                        },
                        "request_highlights": {
                            "type": "array",
                            "description": "请求中需要高亮的字符串列表（可选）",
                            "required": False
                        },
                        "response_highlights": {
                            "type": "array",
                            "description": "响应中需要高亮的字符串列表（可选）",
                            "required": False
                        },
                        "width": {
                            "type": "integer",
                            "description": "截图宽度（像素），默认：1920",
                            "required": False
                        },
                        "height": {
                            "type": "integer",
                            "description": "截图高度（像素），默认：1080",
                            "required": False
                        },
                        "elapsed_ms": {
                            "type": "integer",
                            "description": "请求耗时（毫秒）（可选），会显示在截图底部",
                            "required": False
                        },
                        "is_retest": {
                            "type": "boolean",
                            "description": "是否为重新测试（默认：False），为 True 时会在截图顶部显示重新测试横幅",
                            "required": False
                        },
                        "original_status": {
                            "type": "string",
                            "description": "原始状态（可选），配合 is_retest 使用，显示在重新测试横幅中",
                            "required": False
                        }
                    }
                }
            }
        }
    }
    
    def __init__(self, name: str = "vulnverify-tools"):
        """
        初始化 MCP 服务器。
        
        Args:
            name: MCP 服务器名称
        """
        self.mcp = FastMCP(name)
        self.logger = logging.getLogger(__name__)
        self._tool_manager: Optional[ToolManager] = None
        self._config = ToolConfig()
        self._asgi_app = None
    
    def register_tools_from_manager(self, tool_manager: ToolManager) -> None:
        """
        从 ToolManager 动态注册所有工具为 MCP 工具。
        
        Args:
            tool_manager: 包含所有工具的 ToolManager 实例
        """
        self._tool_manager = tool_manager
        
        for tool_name, tool_service in tool_manager.tools.items():
            self._register_tool(tool_name, tool_service)
        
        self.logger.info(f"已向 MCP 服务器注册 {len(tool_manager.tools)} 个工具")
    
    def _register_tool(self, tool_name: str, tool_service) -> None:
        """
        将单个工具服务注册为 MCP 工具。
        
        Args:
            tool_name: 工具名称
            tool_service: BaseToolService 实例
        """
        version = tool_service.tool_version
        actions = tool_service.list_actions()
        
        # 获取工具配置信息
        tool_info = self.TOOL_DESCRIPTIONS.get(tool_name, {})
        actions_info = tool_info.get("actions", {})
        
        # 如果没有定义具体操作，或者工具描述中也没有操作，则回退到旧的注册方式
        if not actions and not actions_info:
            self.logger.warning(f"工具 {tool_name} 没有定义操作，跳过注册")
            return

        # 为每个操作注册一个独立的 MCP 工具
        for action_name in actions:
            action_desc = actions[action_name]
            action_config = actions_info.get(action_name, {})
            
            self._register_action_tool(
                tool_name=tool_name,
                tool_service=tool_service,
                action_name=action_name,
                action_desc=action_desc,
                action_config=action_config
            )
            
    def _register_action_tool(
        self,
        tool_name: str,
        tool_service,
        action_name: str,
        action_desc: str,
        action_config: Dict[str, Any]
    ) -> None:
        """
        注册单个操作为 MCP 工具
        """
        import inspect
        
        # 构造工具名称: {tool_name}_{action_name}
        # 将中划线替换为下划线，以符合 Python 函数命名规范
        safe_tool_name = tool_name.replace("-", "_")
        mcp_tool_name = f"{safe_tool_name}_{action_name}"
        
        # 获取参数配置
        params_config = action_config.get("params", {})
        
        # 1. 动态定义参数签名
        parameters = []
        
        # 类型映射表
        type_mapping = {
            "string": str,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        for param_name, param_info in params_config.items():
            param_type_str = param_info.get("type", "string")
            python_type = type_mapping.get(param_type_str, str)
            description = param_info.get("description", "")
            required = param_info.get("required", False)
            
            # 使用 Annotated 和 Field 定义参数
            # Annotated[type, Field(description="...")]
            annotation = Annotated[python_type, Field(description=description)]
            
            # 默认值
            default = inspect.Parameter.empty if required else None
            
            parameters.append(
                inspect.Parameter(
                    name=param_name,
                    kind=inspect.Parameter.KEYWORD_ONLY,
                    default=default,
                    annotation=annotation
                )
            )
            
        # 2. 创建动态函数
        async def dynamic_tool_func(**kwargs) -> str:
            # 将参数包装为 dict，并添加 action 字段
            exec_params = kwargs.copy()
            exec_params["action"] = action_name
            
            try:
                result = await tool_service.execute(exec_params)
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                error_result = {
                    "success": False,
                    "error": {
                        "code": "MCP_EXECUTION_ERROR",
                        "message": str(e)
                    },
                    "tool_name": tool_name,
                    "action": action_name
                }
                return json.dumps(error_result, ensure_ascii=False)
        
        # 3. 设置函数元数据
        dynamic_tool_func.__name__ = mcp_tool_name
        dynamic_tool_func.__doc__ = f"{action_desc}\n\n所属工具: {tool_name} (v{tool_service.tool_version})"
        
        # 4. 设置函数签名
        sig = inspect.Signature(parameters=parameters)
        dynamic_tool_func.__signature__ = sig
        
        # 5. 注册为 MCP 工具
        # FastMCP 会检查 __signature__ 来生成 schema
        self.mcp.tool(name=mcp_tool_name)(dynamic_tool_func)
        
        self.logger.info(f"已注册 MCP 工具操作: {mcp_tool_name}")

    def _generate_tool_description(self, tool_name: str, version: str, actions: Dict[str, str]) -> str:
        """
        为 MCP 工具生成详细的中文描述。
        
        Args:
            tool_name: 工具名称
            version: 工具版本
            actions: 工具可用的操作
            
        Returns:
            格式化的描述字符串
        """
        # 获取工具的详细描述
        tool_info = self.TOOL_DESCRIPTIONS.get(tool_name, {})
        
        # 构建基础描述
        description = f"# {tool_info.get('name', tool_name)} (v{version})\n\n"
        description += f"{tool_info.get('description', f'执行 {tool_name} 工具。')}\n\n"
        
        # 添加操作说明
        if actions:
            description += "## 可用操作\n\n"
            for action_name, action_desc in actions.items():
                # 获取操作的详细信息
                action_info = tool_info.get("actions", {}).get(action_name, {})
                action_name_cn = action_info.get("name", action_name)
                action_desc_cn = action_info.get("description", action_desc)
                
                description += f"### {action_name_cn} (`{action_name}`)\n\n"
                description += f"{action_desc_cn}\n\n"
                
                # 添加参数说明
                params_info = action_info.get("params", {})
                if params_info:
                    description += "**参数：**\n\n"
                    for param_name, param_info in params_info.items():
                        required_mark = " **(必需)**" if param_info.get("required") else " **(可选)**"
                        description += f"- `{param_name}` ({param_info.get('type', 'any')}){required_mark}: {param_info.get('description', '')}\n"
                    description += "\n"
                else:
                    description += "**参数：** 无特定参数\n\n"
        
        # 添加使用说明
        description += "## 使用说明\n\n"
        description += "使用 `action` 参数指定要执行的操作。\n\n"
        
        # 为每个工具生成特定的使用示例
        if tool_name == "curl-exec":
            description += "**示例 1 - 执行 Curl 命令：**\n"
            description += '```json\n{"action": "curl_args", "curl_args": ["http://example.com", "-X", "POST", "-H", "Content-Type: application/json"]}\n```\n\n'
            description += "**示例 2 - 执行原始 HTTP 请求：**\n"
            description += '```json\n{"action": "rawhttp", "url": "http://example.com", "raw_http": "GET /path HTTP/1.1\\nHost: example.com\\n\\n"}\n```\n'
        elif tool_name == "dnslog-service":
            description += "**示例 1 - 注册 DNSLog 会话：**\n"
            description += '```json\n{"action": "register", "domain_prefix": "test"}\n```\n\n'
            description += "**示例 2 - 轮询 DNS 交互：**\n"
            description += '```json\n{"action": "poll", "session_id": "abc123"}\n```\n\n'
            description += "**示例 3 - 注销会话：**\n"
            description += '```json\n{"action": "deregister", "session_id": "abc123"}\n```\n'
        elif tool_name == "screenshot":
            description += "**示例 1 - 网页截图：**\n"
            description += '```json\n{"action": "web_screenshot", "url": "https://example.com", "loading_strategy": "normal", "sleep_time": 2}\n```\n\n'
            description += "**示例 2 - Burp 风格截图：**\n"
            description += '```json\n{"action": "burp_screenshot", "request_data": "GET / HTTP/1.1\\nHost: example.com\\n\\n", "response_data": "HTTP/1.1 200 OK\\n\\n<html>...</html>"}\n```\n'
        else:
            description += "**示例：**\n"
            description += '```json\n{"action": "' + list(actions.keys())[0] + '"}\n```\n'
        
        return description
    
    async def handle_root(self, request: Request):
        """处理 MCP 根路径请求，返回服务状态信息。"""
        return JSONResponse({
            "status": "running",
            "service": "MCP Server (FastMCP Streamable HTTP)",
            "endpoints": {
                "mcp": "/mcp"
            },
            "note": "MCP endpoint is available at /mcp (Streamable HTTP mode)"
        })

    def get_asgi_app(self):
        """
        获取 MCP 服务器 ASGI 应用程序（不含生命周期管理）。
        
        注意：生命周期管理需要通过 lifespan_context() 在主应用中处理。
        
        Returns:
            ASGI 应用程序实例
        """
        if self._asgi_app:
            return self._asgi_app
            
        # 获取 FastMCP streamable app (包含 /mcp 路由)
        mcp_app = self.mcp.streamable_http_app()
        
        # 创建 Starlette 应用
        # 将 mcp_app 挂载到根路径，这样它自带的 /mcp 路由就会生效
        routes = [
            Route("/", self.handle_root, methods=["GET"]),
            Mount("/", app=mcp_app)
        ]
        
        # 不传递 lifespan，因为生命周期由 main.py 中的 lifespan_context() 管理
        app = Starlette(routes=routes)
        
        # 添加认证中间件
        app.add_middleware(AuthMiddleware, token=self._config.tool_token)
        # 添加路径重写中间件 (runs before AuthMiddleware)
        app.add_middleware(PathRewriteMiddleware)
        
        self._asgi_app = app
        return self._asgi_app
    
    @contextlib.asynccontextmanager
    async def lifespan_context(self):
        """
        MCP 会话管理器的生命周期上下文管理器。
        
        在主应用的 lifespan 中使用此方法来正确管理 MCP 会话。
        
        Usage:
            async with mcp_server.lifespan_context():
                yield
        """
        self.logger.info("Starting MCP session manager...")
        async with self.mcp.session_manager.run():
            self.logger.info("MCP session manager started")
            yield
            self.logger.info("MCP session manager stopping...")
        self.logger.info("MCP session manager stopped")
    
    def get_session_manager(self):
        """
        获取会话管理器用于生命周期管理。
        
        Returns:
            会话管理器实例
        """
        return self.mcp.session_manager