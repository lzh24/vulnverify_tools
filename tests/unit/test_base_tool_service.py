"""
Unit tests for core/base_tool_service.py - BaseToolService abstract class
"""

import time
import pytest
from typing import Dict, Any
from core.base_tool_service import BaseToolService


class MockToolService(BaseToolService):
    """Mock tool service for testing BaseToolService."""
    
    def __init__(self):
        super().__init__("mock-tool", "1.0.0")
        self.params_validated = False
        self.execution_count = 0
    
    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Mock parameter validation."""
        self.params_validated = True
        required_fields = ["test_param"]
        return all(field in params for field in required_fields)
    
    async def _execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mock execution logic."""
        self.execution_count += 1
        return {"result": "success", "input": params.get("test_param")}


class TestBaseToolService:
    """Test suite for BaseToolService abstract base class."""

    @pytest.mark.asyncio
    async def test_execute_with_valid_params(self):
        """Test execute() with valid parameters."""
        tool = MockToolService()
        params = {"test_param": "test_value"}
        
        result = await tool.execute(params)
        
        assert result["success"] is True
        assert "data" in result
        assert result["data"]["result"] == "success"
        assert result["data"]["input"] == "test_value"
        assert "execution_time_ms" in result
        assert "timestamp" in result
        assert tool.params_validated is True
        assert tool.execution_count == 1

    @pytest.mark.asyncio
    async def test_execute_with_invalid_params(self):
        """Test execute() raises ValueError with invalid parameters."""
        tool = MockToolService()
        params = {"wrong_param": "wrong_value"}
        
        with pytest.raises(ValueError, match="Invalid parameters"):
            await tool.execute(params)
        
        assert tool.params_validated is True
        assert tool.execution_count == 0

    @pytest.mark.asyncio
    async def test_execute_includes_execution_time(self):
        """Test execute() includes execution time in response."""
        tool = MockToolService()
        params = {"test_param": "test_value"}
        
        result = await tool.execute(params)
        
        assert "execution_time_ms" in result
        assert isinstance(result["execution_time_ms"], int)
        assert result["execution_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_execute_includes_timestamp(self):
        """Test execute() includes ISO timestamp in response."""
        tool = MockToolService()
        params = {"test_param": "test_value"}
        
        before = time.time()
        result = await tool.execute(params)
        after = time.time()
        
        assert "timestamp" in result
        assert isinstance(result["timestamp"], str)
        assert "T" in result["timestamp"]  # ISO format
        assert "Z" in result["timestamp"]  # UTC indicator

    def test_get_health_status(self):
        """Test get_health_status() returns correct information."""
        tool = MockToolService()
        
        status = tool.get_health_status()
        
        assert status["status"] == "healthy"
        assert status["tool_name"] == "mock-tool"
        assert status["version"] == "1.0.0"
        assert "uptime_seconds" in status
        assert isinstance(status["uptime_seconds"], int)
        assert status["uptime_seconds"] >= 0

    def test_tool_initialization(self):
        """Test tool initializes with correct attributes."""
        tool = MockToolService()
        
        assert tool.tool_name == "mock-tool"
        assert tool.tool_version == "1.0.0"
        assert hasattr(tool, "logger")
        assert hasattr(tool, "start_time")

    @pytest.mark.asyncio
    async def test_execute_response_structure(self):
        """Test execute() returns response with correct structure."""
        tool = MockToolService()
        params = {"test_param": "test_value"}
        
        result = await tool.execute(params)
        
        # Check all required fields exist
        required_fields = ["success", "data", "execution_time_ms", "timestamp"]
        for field in required_fields:
            assert field in result

    def test_cannot_instantiate_abstract_base_class(self):
        """Test BaseToolService cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseToolService("test", "1.0.0")
