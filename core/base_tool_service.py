"""Base Tool Service class for external tools framework."""

import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional
from functools import wraps


def tool_action(action_name: str, description: str = ""):
    """
    Decorator to register a method as a tool action.
    
    Args:
        action_name: The name of the action (e.g., "register", "poll")
        description: Optional description of what this action does
    
    Usage:
        @tool_action("register", "Register a new session")
        async def register_session(self, params: Dict[str, Any]):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            return await func(self, *args, **kwargs)
        
        wrapper._is_tool_action = True
        wrapper._action_name = action_name
        wrapper._action_description = description
        return wrapper
    return decorator


class BaseToolService(ABC):
    """Abstract base class for all external tool services."""

    def __init__(self, tool_name: str, tool_version: str):
        self.tool_name = tool_name
        self.tool_version = tool_version
        self.start_time = time.time()
        self._actions: Dict[str, Callable] = {}
        self._action_descriptions: Dict[str, str] = {}

        from core.logger import JSONFormatter
        
        logger = logging.getLogger(f"tools.{tool_name}")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

        self.logger = logger
        
        # Auto-register tool actions
        self._register_actions()

    def _register_actions(self):
        """Automatically register all methods decorated with @tool_action."""
        for attr_name in dir(self):
            if attr_name.startswith('_'):
                continue
                
            attr = getattr(self, attr_name)
            if hasattr(attr, '_is_tool_action') and attr._is_tool_action:
                action_name = getattr(attr, '_action_name')
                action_desc = getattr(attr, '_action_description', '')
                self._actions[action_name] = attr
                self._action_descriptions[action_name] = action_desc
                self.logger.info(f"[{self.tool_name}] Registered action: {action_name}")

    @abstractmethod
    async def _execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy tool execution logic.
        Must be implemented by subclasses for backward compatibility.
        New tools should use @tool_action decorators instead.
        """
        pass

    @abstractmethod
    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Legacy parameter validation logic.
        Must be implemented by subclasses for backward compatibility.
        New tools should implement validation in each action method.
        """
        pass

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Public method to execute the tool with validation.
        Supports both legacy _execute and new @tool_action pattern.
        """
        start = time.time()
        
        # Check if this tool uses the new action-based pattern
        action = params.get("action", "default")
        
        if self._actions and action in self._actions:
            # New pattern: use action-based routing
            try:
                result = await self._actions[action](params)
                return {
                    "success": True,
                    "data": result,
                    "execution_time_ms": int((time.time() - start) * 1000),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "action": action
                }
            except Exception as e:
                self.logger.error(f"Action {action} execution failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": {
                        "code": "ACTION_EXECUTION_ERROR",
                        "message": str(e)
                    },
                    "execution_time_ms": int((time.time() - start) * 1000),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "action": action
                }
        else:
            # Legacy pattern: use _execute and validate_params
            if not await self.validate_params(params):
                raise ValueError("Invalid parameters")
            
            result = await self._execute(params)
            
            return {
                "success": True,
                "data": result,
                "execution_time_ms": int((time.time() - start) * 1000),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }

    def get_health_status(self) -> Dict[str, Any]:
        """Get tool health status."""
        status = {
            "status": "healthy",
            "tool_name": self.tool_name,
            "version": self.tool_version,
            "uptime_seconds": int(time.time() - self.start_time)
        }
        
        # Include available actions if using new pattern
        if self._actions:
            status["actions"] = {
                name: self._action_descriptions.get(name, "")
                for name in self._actions.keys()
            }
        
        return status

    def list_actions(self) -> Dict[str, str]:
        """
        List all available actions with their descriptions.
        Returns empty dict for legacy tools.
        """
        return self._action_descriptions.copy()
