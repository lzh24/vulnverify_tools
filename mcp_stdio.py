import asyncio
import logging
import sys
from core.mcp_server import MCPServer
from core.tool_manager import ToolManager

# 配置日志
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

async def main():
    # 初始化工具管理器
    tool_manager = ToolManager()
    
    # 初始化 MCP 服务器
    mcp_server = MCPServer()
    
    # 注册工具
    mcp_server.register_tools_from_manager(tool_manager)
    
    # 运行 MCP 服务器 (stdio模式)
    await mcp_server.mcp.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(main())