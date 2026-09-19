"""
Unit tests for core/tool_manager.py - ToolManager class
"""

import os
import sys
import pytest
from typing import Dict, Any
from unittest.mock import patch, MagicMock
from core.tool_manager import ToolManager
from core.base_tool_service import BaseToolService


class MockToolService(BaseToolService):
    """Mock tool service for testing."""
    
    def __init__(self):
        super().__init__("mock-tool", "1.0.0")
    
    async def validate_params(self, params: Dict[str, Any]) -> bool:
        return "test_param" in params
    
    async def _execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "mock_success"}


class TestToolManager:
    """Test suite for ToolManager."""

    def test_tool_manager_initialization(self):
        """Test ToolManager initializes correctly."""
        with patch.object(ToolManager, '_load_tools', return_value=None):
            manager = ToolManager()
            assert hasattr(manager, 'tools')
            assert isinstance(manager.tools, dict)

    def test_list_tools_empty(self):
        """Test list_tools() returns empty dict when no tools loaded."""
        with patch.object(ToolManager, '_load_tools', return_value=None):
            manager = ToolManager()
            assert manager.list_tools() == {}

    def test_list_tools_with_tools(self):
        """Test list_tools() returns tools with versions."""
        with patch.object(ToolManager, '_load_tools', return_value=None):
            manager = ToolManager()
            mock_tool = MockToolService()
            manager.tools["mock-tool"] = mock_tool
            
            tools = manager.list_tools()
            assert "mock-tool" in tools
            assert tools["mock-tool"] == "1.0.0"

    def test_get_tool_success(self):
        """Test get_tool() returns correct tool."""
        with patch.object(ToolManager, '_load_tools', return_value=None):
            manager = ToolManager()
            mock_tool = MockToolService()
            manager.tools["mock-tool"] = mock_tool
            
            tool = manager.get_tool("mock-tool")
            assert tool is mock_tool

    def test_get_tool_not_found(self):
        """Test get_tool() returns None for non-existent tool."""
        with patch.object(ToolManager, '_load_tools', return_value=None):
            manager = ToolManager()
            
            tool = manager.get_tool("non-existent")
            assert tool is None

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """Test execute_tool() successfully executes a tool."""
        with patch.object(ToolManager, '_load_tools', return_value=None):
            manager = ToolManager()
            mock_tool = MockToolService()
            manager.tools["mock-tool"] = mock_tool
            
            result = await manager.execute_tool("mock-tool", {"test_param": "value"})
            
            assert result["success"] is True
            assert "data" in result
            assert result["data"]["result"] == "mock_success"

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        """Test execute_tool() raises ValueError for non-existent tool."""
        with patch.object(ToolManager, '_load_tools', return_value=None):
            manager = ToolManager()
            
            with pytest.raises(ValueError, match="Tool not found"):
                await manager.execute_tool("non-existent", {})

    def test_get_tool_health_success(self):
        """Test get_tool_health() returns health status."""
        with patch.object(ToolManager, '_load_tools', return_value=None):
            manager = ToolManager()
            mock_tool = MockToolService()
            manager.tools["mock-tool"] = mock_tool
            
            health = manager.get_tool_health("mock-tool")
            
            assert health["status"] == "healthy"
            assert health["tool_name"] == "mock-tool"
            assert health["version"] == "1.0.0"

    def test_get_tool_health_not_found(self):
        """Test get_tool_health() raises ValueError for non-existent tool."""
        with patch.object(ToolManager, '_load_tools', return_value=None):
            manager = ToolManager()
            
            with pytest.raises(ValueError, match="Tool not found"):
                manager.get_tool_health("non-existent")

    def test_get_all_health(self):
        """Test get_all_health() returns health for all tools."""
        with patch.object(ToolManager, '_load_tools', return_value=None):
            manager = ToolManager()
            mock_tool1 = MockToolService()
            mock_tool2 = MockToolService()
            mock_tool2.tool_name = "mock-tool-2"
            manager.tools["mock-tool"] = mock_tool1
            manager.tools["mock-tool-2"] = mock_tool2
            
            all_health = manager.get_all_health()
            
            assert len(all_health) == 2
            assert "mock-tool" in all_health
            assert "mock-tool-2" in all_health
            assert all_health["mock-tool"]["status"] == "healthy"
            assert all_health["mock-tool-2"]["status"] == "healthy"

    def test_load_tools_creates_tools_dict(self):
        """Test _load_tools initializes tools dictionary."""
        # Use a non-existent tools directory to avoid loading real tools
        with patch('os.path.exists', return_value=False):
            manager = ToolManager(tools_directory="non_existent")
            assert isinstance(manager.tools, dict)
