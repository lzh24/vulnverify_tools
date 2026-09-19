"""
Unit tests for core/config.py - ToolConfig class
"""

import os
import pytest
from pydantic_core import ValidationError
from core.config import ToolConfig


class TestToolConfig:
    """Test suite for ToolConfig configuration management."""

    def test_config_with_all_env_vars(self, monkeypatch):
        """Test configuration loads correctly when all env vars are set."""
        monkeypatch.setenv("TOOL_TOKEN", "test-token-123")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("HOST", "127.0.0.1")
        monkeypatch.setenv("PORT", "9000")

        config = ToolConfig()

        assert config.tool_token == "test-token-123"
        assert config.log_level == "DEBUG"
        assert config.host == "127.0.0.1"
        assert config.port == 9000

    def test_config_defaults(self, monkeypatch):
        """Test configuration uses correct default values."""
        monkeypatch.setenv("TOOL_TOKEN", "default-token")

        config = ToolConfig()

        assert config.tool_token == "default-token"
        assert config.log_level == "INFO"
        assert config.host == "0.0.0.0"
        assert config.port == 8000

    def test_config_tool_token_is_required(self, monkeypatch):
        """Test that TOOL_TOKEN is required for configuration."""
        monkeypatch.setenv("TOOL_TOKEN", "valid-token")
        config = ToolConfig()
        assert config.tool_token == "valid-token"

    def test_config_port_as_string(self, monkeypatch):
        """Test configuration handles PORT as string (env var type)."""
        monkeypatch.setenv("TOOL_TOKEN", "test-token")
        monkeypatch.setenv("PORT", "8888")

        config = ToolConfig()

        assert isinstance(config.port, int)
        assert config.port == 8888

    def test_config_minimal_env_vars(self, monkeypatch):
        """Test configuration works with only required TOOL_TOKEN set."""
        monkeypatch.setenv("TOOL_TOKEN", "minimal-token")
        
        config = ToolConfig()
        
        assert config.tool_token == "minimal-token"
        assert config.log_level == "INFO"  # default
        assert config.host == "0.0.0.0"    # default
        assert config.port == 8000         # default

    def test_config_override_defaults(self, monkeypatch):
        """Test configuration can override all default values."""
        monkeypatch.setenv("TOOL_TOKEN", "override-token")
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "7000")

        config = ToolConfig()

        assert config.tool_token == "override-token"
        assert config.log_level == "WARNING"
        assert config.host == "localhost"
        assert config.port == 7000

    def test_config_missing_tool_token(self, monkeypatch):
        """Test configuration raises ValidationError when TOOL_TOKEN is missing."""
        monkeypatch.delenv("TOOL_TOKEN", raising=False)

        # Disable .env file loading to test actual missing token scenario
        with pytest.raises(ValidationError) as exc_info:
            ToolConfig(_env_file=None)

        errorDetails = exc_info.value.errors()
        assert len(errorDetails) == 1
        assert errorDetails[0]["loc"][0] == "tool_token"
        assert errorDetails[0]["type"] == "missing"

    def test_config_env_file_support(self, monkeypatch, tmp_path):
        """Test configuration can load from .env file."""
        # Create temporary .env file
        env_file = tmp_path / ".env"
        env_file.write_text("TOOL_TOKEN=from_env_file")
        
        # Change directory to temp location
        original_cwd = os.getcwd()
        monkeypatch.chdir(tmp_path)

        try:
            # We must clear the env var to ensure it reads from file
            monkeypatch.delenv("TOOL_TOKEN", raising=False)
            config = ToolConfig(_env_file=str(env_file), _env_file_encoding="utf-8")
            assert config.tool_token == "from_env_file"
        finally:
            monkeypatch.chdir(original_cwd)
