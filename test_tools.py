"""Unit tests for tools.py - Tool definitions and execution."""
import pytest
import sys
import os
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


class TestToolDefinitions:
    """Tests for tool definitions."""

    def test_tools_list_exists(self):
        """TOOLS list should exist and be non-empty."""
        from tools import TOOLS
        assert isinstance(TOOLS, list)
        assert len(TOOLS) > 0

    def test_read_file_tool_defined(self):
        """read_file tool should be defined with required fields."""
        from tools import TOOLS
        tool = next((t for t in TOOLS if t["name"] == "read_file"), None)
        assert tool is not None
        assert "description" in tool
        assert "parameters" in tool
        assert "path" in tool["parameters"]["required"]

    def test_write_file_tool_defined(self):
        """write_file tool should be defined with required fields."""
        from tools import TOOLS
        tool = next((t for t in TOOLS if t["name"] == "write_file"), None)
        assert tool is not None
        assert "parameters" in tool
        params = tool["parameters"]["required"]
        assert "path" in params
        assert "content" in params

    def test_edit_file_tool_defined(self):
        """edit_file tool should be defined with required fields."""
        from tools import TOOLS
        tool = next((t for t in TOOLS if t["name"] == "edit_file"), None)
        assert tool is not None
        params = tool["parameters"]["required"]
        assert "path" in params
        assert "search" in params
        assert "replace" in params


class TestGetToolsInstructions:
    """Tests for get_tools_instructions()."""

    def test_returns_string(self):
        """get_tools_instructions should return a string."""
        from tools import get_tools_instructions
        result = get_tools_instructions()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mentions_json(self):
        """get_tools_instructions should mention JSON."""
        from tools import get_tools_instructions
        result = get_tools_instructions()
        assert "json" in result.lower()


class TestValidatePath:
    """Tests for path validation."""

    @patch('tools.os.getcwd', return_value="/test/cwd")
    @patch('tools.os.path.abspath')
    def test_accepts_simple_relative_path(self, mock_abspath, mock_getcwd):
        """Should accept paths within working directory."""
        mock_abspath.return_value = "/test/cwd/subdir/file.txt"
        from tools import _validate_path
        result = _validate_path("subdir/file.txt")
        assert result == "/test/cwd/subdir/file.txt"

    @patch('tools.os.getcwd', return_value="/test/cwd")
    @patch('tools.os.path.abspath')
    def test_accepts_nested_relative_path(self, mock_abspath, mock_getcwd):
        """Should accept deeply nested paths."""
        mock_abspath.return_value = "/test/cwd/a/b/c/file.txt"
        from tools import _validate_path
        result = _validate_path("a/b/c/file.txt")
        assert result == "/test/cwd/a/b/c/file.txt"

    @patch('tools.os.getcwd', return_value="/test/cwd")
    @patch('tools.os.path.abspath')
    def test_rejects_absolute_path_outside_cwd(self, mock_abspath, mock_getcwd):
        """Should reject absolute paths outside working directory."""
        mock_abspath.return_value = "/etc/passwd"
        from tools import _validate_path
        with pytest.raises(ValueError, match="Access denied"):
            _validate_path("/etc/passwd")

    @patch('tools.os.getcwd', return_value="/test/cwd")
    @patch('tools.os.path.abspath')
    def test_rejects_parent_traversal_outside_cwd(self, mock_abspath, mock_getcwd):
        """Should reject traversal attempts outside working directory."""
        mock_abspath.return_value = "/test/other_dir"
        from tools import _validate_path
        with pytest.raises(ValueError, match="Access denied"):
            _validate_path("../other_dir")


class TestToolEngineDispatch:
    """Tests for ToolEngine.dispatch()."""

    def test_dispatch_parses_valid_json(self):
        """dispatch should parse valid JSON tool call."""
        from tools import ToolEngine
        engine = ToolEngine()
        response = '''
        Let me read that file:
        ```json
        {"name": "read_file", "arguments": {"path": "test.txt"}}
        ```
        '''
        with patch('tools._execute_read', return_value="[OK]"):
            with patch('tools._validate_path', return_value="/cwd/test.txt"):
                result = engine.dispatch(response)
                assert result == "[OK]"

    def test_dispatch_returns_none_for_non_json(self):
        """dispatch should return None when no JSON found."""
        from tools import ToolEngine
        engine = ToolEngine()
        result = engine.dispatch("Just a plain response with no tool call")
        assert result is None

    def test_dispatch_returns_error_for_unknown_tool(self):
        """dispatch should return error for unknown tool."""
        from tools import ToolEngine
        engine = ToolEngine()
        response = '{"name": "unknown_tool", "arguments": {}}'
        result = engine.dispatch(response)
        assert "Unknown tool" in result

    def test_dispatch_handles_missing_params(self):
        """dispatch should handle missing parameters."""
        from tools import ToolEngine
        engine = ToolEngine()
        response = '{"name": "read_file", "arguments": {}}'
        result = engine.dispatch(response)
        assert result is not None
