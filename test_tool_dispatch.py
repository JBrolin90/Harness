"""Unit tests for tool_dispatch.py - Tool dispatch function."""
import pytest
from unittest.mock import patch


class TestToolDispatch:
    """Tests for tool_dispatch()."""

    def test_tool_dispatch_parses_valid_json(self):
        """tool_dispatch should parse valid JSON tool call (raw JSON from native function calling)."""
        from tool_dispatch import tool_dispatch
        from tools import BaseTool, ToolsManager
        import tools
        # Raw JSON response from structured tool calling API
        response = '{"name": "read_file", "arguments": {"path": "test.txt"}}'
        original_registry = dict(ToolsManager._registry)
        ToolsManager._registry = {"read_file": type("MockTool", (), {"name": "read_file", "execute": lambda self, **kw: "[OK]"})}
        try:
            result = tool_dispatch(response)
            assert result == "[OK]"
        finally:
            ToolsManager._registry = original_registry

    def test_tool_dispatch_returns_none_for_non_json(self):
        """tool_dispatch should return None when no JSON found."""
        from tool_dispatch import tool_dispatch
        result = tool_dispatch("Just a plain response with no tool call")
        assert result is None

    def test_tool_dispatch_returns_error_for_unknown_tool(self):
        """tool_dispatch should return error for unknown tool."""
        from tool_dispatch import tool_dispatch
        response = '{"name": "unknown_tool", "arguments": {}}'
        result = tool_dispatch(response)
        assert "Unknown tool" in result

    def test_tool_dispatch_handles_missing_params(self):
        """tool_dispatch should handle missing parameters."""
        from tool_dispatch import tool_dispatch
        response = '{"name": "read_file", "arguments": {}}'
        result = tool_dispatch(response)
        assert result is not None

    def test_tool_dispatch_handles_empty_arguments(self):
        """tool_dispatch should handle missing 'arguments' key."""
        from tool_dispatch import tool_dispatch
        from tools import ToolsManager
        response = '{"name": "bash", "command": "ls"}'
        original_registry = dict(ToolsManager._registry)
        ToolsManager._registry = {"bash": type("MockTool", (), {"name": "bash", "execute": lambda self, **kw: "[OK]"})}
        try:
            result = tool_dispatch(response)
            assert result == "[OK]"
        finally:
            ToolsManager._registry = original_registry