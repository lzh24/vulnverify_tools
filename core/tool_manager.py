"""Tool Manager for loading and managing external tools."""

import os
import sys
import importlib
import logging
from typing import Dict, Any, Optional
from .base_tool_service import BaseToolService


class ToolManager:
    """Manages loading and execution of external tools."""
    
    def __init__(self, tools_directory: str = "tools"):
        self.tools_directory = tools_directory
        self.tools: Dict[str, BaseToolService] = {}
        self.logger = logging.getLogger(__name__)
        self._load_tools()
    
    def _load_tools(self):
        """Dynamically load all tools from the tools directory."""
        tools_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.tools_directory)
        
        if not os.path.exists(tools_path):
            self.logger.warning(f"Tools directory not found: {tools_path}")
            return
        
        if tools_path not in sys.path:
            sys.path.insert(0, os.path.dirname(tools_path))
        
        for tool_name in os.listdir(tools_path):
            tool_path = os.path.join(tools_path, tool_name)
            
            if not os.path.isdir(tool_path) or tool_name.startswith('.') or tool_name.startswith('__'):
                continue
            
            try:
                module_name = f"{self.tools_directory}.{tool_name}.main"
                
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                module = importlib.import_module(module_name)
                
                tool_service = None
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BaseToolService) and 
                        attr != BaseToolService):
                        tool_service = attr()
                        break
                
                if tool_service:
                    self.tools[tool_service.tool_name] = tool_service
                    self.logger.info(f"Loaded tool: {tool_service.tool_name} (v{tool_service.tool_version})")
                else:
                    self.logger.warning(f"No valid tool service found in {tool_name}")
                    
            except Exception as e:
                self.logger.error(f"Failed to load tool {tool_name}: {e}", exc_info=True)
    
    def get_tool(self, tool_name: str) -> Optional[BaseToolService]:
        """Get a tool by name."""
        return self.tools.get(tool_name)
    
    def list_tools(self) -> Dict[str, str]:
        """List all available tools with their versions."""
        return {name: tool.tool_version for name, tool in self.tools.items()}
    
    async def execute_tool(self, tool_name: str, params: Dict[str, Any], sub_function: str = None) -> Dict[str, Any]:
        """
        Execute a tool by name with optional sub-function routing.
        
        Args:
            tool_name: Name of the tool to execute
            params: Parameters to pass to the tool
            sub_function: Optional sub-function name (for multi-layer routing)
        
        Returns:
            Tool execution result
        """
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        # If sub_function is provided, inject it as action parameter
        if sub_function:
            params = params.copy()
            params["action"] = sub_function
        
        return await tool.execute(params)
    
    def get_tool_health(self, tool_name: str) -> Dict[str, Any]:
        """Get health status of a tool."""
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        return tool.get_health_status()
    
    def get_all_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all tools."""
        health_status = {}
        for name, tool in self.tools.items():
            health_status[name] = tool.get_health_status()
        return health_status
