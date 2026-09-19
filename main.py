"""Main entry point for the unified external tools service."""

import os
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from core.tool_manager import ToolManager
from core.auth import AuthMiddleware
from core.config import ToolConfig
from core.mcp_server import MCPServer
import logging
from pathlib import Path

tool_manager: Optional[ToolManager] = None
config: Optional[ToolConfig] = None
mcp_server: Optional[MCPServer] = None

# Initialize MCP Server early
mcp_server = MCPServer("vulnverify-tools")


def get_instance_metadata() -> Dict[str, str]:
    return {
        "node_hostname": os.getenv("INSTANCE_NODE_HOSTNAME", ""),
        "task_name": os.getenv("INSTANCE_TASK_NAME", ""),
        "service_name": os.getenv("INSTANCE_SERVICE_NAME", ""),
        "container_hostname": os.getenv("HOSTNAME", ""),
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    global tool_manager, config, mcp_server
    config = ToolConfig()
    tool_manager = ToolManager()
    
    # Register tools with MCP Server
    mcp_server.register_tools_from_manager(tool_manager)
    
    logging.info("Unified external tools service started")
    logging.info(f"Loaded tools: {list(tool_manager.list_tools().keys())}")
    
    # Debug: Print all registered routes
    logging.info("=== Registered Routes ===")
    for route in app.routes:
        if hasattr(route, 'methods'):
            logging.info(f"Route: {route.methods} {route.path}")
        elif hasattr(route, 'path'):
            logging.info(f"Mount: {route.path} -> {type(route.app).__name__}")
        else:
            logging.info(f"Other: {type(route).__name__}")
    logging.info("=========================")

    # Start MCP session manager within the main app's lifespan
    # Note: get_asgi_app() now returns an app with its own lifespan handling
    # but we still need to initialize the tool manager and register tools first
    # The MCP app's lifespan is managed by Starlette when mounted,
    # OR we can manually manage it here if needed.
    # However, since we're mounting the app returned by get_asgi_app(),
    # and that app has lifespan=mcp_app.lifespan, it should be handled automatically
    # IF the main app triggers it. But FastAPI mounts don't automatically trigger sub-app lifespans.
    # So we should keep this explicit context manager.
    async with mcp_server.lifespan_context():
        yield

app = FastAPI(
    title="Unified External Tools Service",
    description="A unified service for all external vulnerability verification tools",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# Mount MCP app after app creation
mcp_asgi_app = mcp_server.get_asgi_app()
# Mount at /mcp to avoid shadowing other routes
app.mount("/mcp", mcp_asgi_app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Debug middleware to log all requests (skip MCP SSE to avoid interference)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    path = request.url.path
    if config and not config.enable_request_logging:
        return await call_next(request)
    # Skip logging for MCP SSE endpoints to avoid interfering with streaming
    if path.startswith("/mcp/"):
        return await call_next(request)
    
    logging.info(f"Incoming request: {request.method} {path}")
    response = await call_next(request)
    logging.info(f"Response status: {response.status_code} for {request.method} {path}")
    return response

async def verify_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    provided_token = auth_header.split(" ")[1]
    if provided_token != config.tool_token:
        raise HTTPException(status_code=403, detail="Invalid authentication token")
    return True

@app.get("/")
async def root():
    return {}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "unified-tools",
        "version": "1.0.0",
        "tools": tool_manager.list_tools() if tool_manager else {},
        "instance": get_instance_metadata(),
    }

@app.get("/health/{tool_name}", dependencies=[Depends(verify_token)])
async def tool_health_check(tool_name: str):
    if not tool_manager: raise HTTPException(status_code=503, detail="Service not initialized")
    try: return tool_manager.get_tool_health(tool_name)
    except ValueError as e: raise HTTPException(status_code=404, detail=str(e))

@app.get("/actions/{tool_name}", dependencies=[Depends(verify_token)])
async def list_tool_actions(tool_name: str):
    """List all available actions for a specific tool"""
    if not tool_manager: raise HTTPException(status_code=503, detail="Service not initialized")
    tool = tool_manager.get_tool(tool_name)
    if not tool: raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
    
    return {
        "tool_name": tool_name,
        "actions": tool.list_actions()
    }

@app.post("/execute/{tool_name}", dependencies=[Depends(verify_token)])
async def execute_tool(tool_name: str, request: Request):
    if not tool_manager: raise HTTPException(status_code=503, detail="Service not initialized")
    
    body = await request.json()
    try:
        return await tool_manager.execute_tool(tool_name, body.get("params", {}), None)
    except ValueError as e: raise HTTPException(status_code=404, detail=str(e))
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/execute/{tool_name}/{sub_function}", dependencies=[Depends(verify_token)])
async def execute_tool_with_subfunction(tool_name: str, sub_function: str, request: Request):
    if not tool_manager: raise HTTPException(status_code=503, detail="Service not initialized")
    
    body = await request.json()
    try:
        return await tool_manager.execute_tool(tool_name, body.get("params", {}), sub_function)
    except ValueError as e: raise HTTPException(status_code=404, detail=str(e))
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/terminal-hub/ui")
async def terminal_hub_ui():
    webui_path = Path(__file__).parent / "tools" / "terminal_hub" / "webui.html"
    if not webui_path.exists():
        raise HTTPException(status_code=404, detail="terminal_hub webui not found")
    return FileResponse(str(webui_path), media_type="text/html")

if __name__ == "__main__":
    import uvicorn
    runtime_config = ToolConfig()
    uvicorn.run(
        "main:app",
        host=runtime_config.host,
        port=runtime_config.port,
        reload=False,
        workers=runtime_config.web_concurrency,
    )
