"""Tests for tool_dispatch.py - structured LLMResponse tool dispatch."""
import pytest
from unittest.mock import patch
from tool_dispatch import (
    dispatch,
    _safe_dispatch,
    _normalize_arguments,
    parse_bash_command,
    extract_json_string,
    ToolResult,
    SystemError,
    NoToolFound,
)
from response import LLMResponse, ToolCall


# ---------------------------------------------------------------------------
# Helper: mock a tool in the registry
# ---------------------------------------------------------------------------

def _mock_tool(toolname, result):
    from tools.base_tool import BaseTool
    class T(BaseTool):
        name = toolname
        description = ""
        parameters = {"type": "object", "properties": {}, "required": []}
        def execute(self, **kw):
            return result
    BaseTool._registry[toolname] = T


def _clear(toolname):
    from tools.base_tool import BaseTool
    BaseTool._registry.pop(toolname, None)


class TestNormalizeArguments:
    """Tests for argument normalization."""

    def test_file_path_normalized(self):
        result = _normalize_arguments({"file_path": "test.txt"})
        assert result == {"path": "test.txt"}

    def test_cmd_normalized(self):
        result = _normalize_arguments({"cmd": "ls"})
        assert result == {"command": "ls"}

    def test_old_text_new_text_normalized(self):
        result = _normalize_arguments({"old_text": "hi", "new_text": "hello", "path": "f.txt"})
        assert result == {"search": "hi", "replace": "hello", "path": "f.txt"}

    def test_preserves_unknown_keys(self):
        result = _normalize_arguments({"path": "test.txt", "extra": "value"})
        assert result == {"path": "test.txt", "extra": "value"}


class TestSafeDispatch:
    """Tests for parameter normalization in _safe_dispatch."""

    def test_file_path_normalized(self):
        with patch("tools.base_tool.BaseTool.dispatch", return_value="[OK]") as m:
            _safe_dispatch("read_file", {"file_path": "test.txt"})
            m.assert_called_once_with("read_file", {"path": "test.txt"})

    def test_cmd_normalized(self):
        with patch("tools.base_tool.BaseTool.dispatch", return_value="[OK]") as m:
            _safe_dispatch("bash", {"cmd": "ls"})
            m.assert_called_once_with("bash", {"command": "ls"})

    def test_old_text_new_text_normalized(self):
        with patch("tools.base_tool.BaseTool.dispatch", return_value="[OK]") as m:
            _safe_dispatch("edit_file", {"old_text": "hi", "new_text": "hello", "path": "f.txt"})
            m.assert_called_once_with("edit_file", {"search": "hi", "replace": "hello", "path": "f.txt"})


class TestExtractJsonString:
    """Tests for extract_json_string parser."""

    def test_valid_json_block(self):
        text = '```json\n{"name": "bash", "arguments": {"command": "ls"}}\n```'
        result = extract_json_string(text)
        assert result == {"name": "bash", "arguments": {"command": "ls"}}

    def test_invalid_json(self):
        text = "```json\nnot valid json\n```"
        assert extract_json_string(text) is None

    def test_missing_name(self):
        text = '```json\n{"arguments": {}}\n```'
        assert extract_json_string(text) is None

    def test_missing_arguments_defaults_empty(self):
        text = '```json\n{"name": "bash"}\n```'
        result = extract_json_string(text)
        assert result == {"name": "bash", "arguments": {}}


class TestParseBashCommand:
    """Tests for parse_bash_command parser."""

    def test_bash_block(self):
        text = "```bash\nls -la\n```"
        result = parse_bash_command(text)
        assert result == {"name": "bash", "arguments": {"command": "ls -la"}}

    def test_sh_block(self):
        text = "```sh\npwd\n```"
        result = parse_bash_command(text)
        assert result == {"name": "bash", "arguments": {"command": "pwd"}}

    def test_empty_block(self):
        assert parse_bash_command("```bash\n```") is None

    def test_no_code_block(self):
        assert parse_bash_command("No code here") is None


class TestDispatch:
    """Integration tests for the full dispatch function with LLMResponse."""

    def test_native_tool_call(self):
        """Native tool_calls field in LLMResponse."""
        _mock_tool("read_file", "[OK]")
        try:
            tc = ToolCall(name="read_file", arguments={"path": "test.txt"})
            response = LLMResponse(tool_calls=[tc])
            r = dispatch(response)
            assert isinstance(r, ToolResult)
            assert r.tool_name == "read_file"
        finally:
            _clear("read_file")

    def test_text_response_no_tool(self):
        """Text response with no tool call returns NoToolFound."""
        response = LLMResponse(text="Hello, how can I help?")
        r = dispatch(response)
        assert isinstance(r, NoToolFound)
        assert not r

    def test_error_response(self):
        """Error response returns SystemError."""
        response = LLMResponse(error="[BRAIN ERROR: HTTP 500]")
        r = dispatch(response)
        assert isinstance(r, SystemError)

    def test_unknown_tool(self):
        """Unknown tool returns SystemError."""
        tc = ToolCall(name="nonexistent_tool", arguments={})
        response = LLMResponse(tool_calls=[tc])
        r = dispatch(response)
        assert isinstance(r, SystemError)
        assert "Unknown tool" in str(r)

    def test_json_in_content(self):
        """JSON in text content is parsed and executed."""
        _mock_tool("bash", "[OK]")
        try:
            response = LLMResponse(text='{"name": "bash", "arguments": {"command": "pwd"}}')
            r = dispatch(response)
            assert isinstance(r, ToolResult)
            assert r.tool_name == "bash"
        finally:
            _clear("bash")

    def test_json_codeblock_in_content(self):
        """JSON code block in text content is parsed and executed."""
        _mock_tool("bash", "[OK]")
        try:
            response = LLMResponse(text='```json\n{"name": "bash", "arguments": {"command": "ls"}}\n```')
            r = dispatch(response)
            assert isinstance(r, ToolResult)
            assert r.tool_name == "bash"
        finally:
            _clear("bash")

    def test_bash_codeblock_in_content(self):
        """Bash code block in text content is executed as bash tool."""
        _mock_tool("bash", "[OK]")
        try:
            response = LLMResponse(text='```bash\nls -la\n```')
            r = dispatch(response)
            assert isinstance(r, ToolResult)
            assert r.tool_name == "bash"
        finally:
            _clear("bash")

    def test_empty_text_returns_no_tool(self):
        """Empty text returns NoToolFound."""
        response = LLMResponse(text="")
        r = dispatch(response)
        assert isinstance(r, NoToolFound)

    def test_tool_result_is_truthy(self):
        """ToolResult is truthy for loop continuation."""
        _mock_tool("bash", "[output]")
        try:
            tc = ToolCall(name="bash", arguments={"command": "ls"})
            response = LLMResponse(tool_calls=[tc])
            r = dispatch(response)
            assert r
            assert isinstance(r, ToolResult)
        finally:
            _clear("bash")

    def test_system_error_is_falsy(self):
        """SystemError is falsy to stop loop."""
        response = LLMResponse(error="[BRAIN ERROR: HTTP 500]")
        r = dispatch(response)
        assert not r
        assert isinstance(r, SystemError)

    def test_no_tool_found_is_falsy(self):
        """NoToolFound is falsy to stop loop."""
        response = LLMResponse(text="Just a response")
        r = dispatch(response)
        assert not r
        assert isinstance(r, NoToolFound)