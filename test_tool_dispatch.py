"""Tests for tool_dispatch.py - structured LLMResponse tool dispatch."""
import pytest
from unittest.mock import patch
from tool_dispatch import (
    dispatch,
    dispatch_with_text_parsing,
    _safe_dispatch,
    _normalize_arguments,
    parse_bash_command,
    extract_json_string,
    ToolResult,
    SystemError,
    NoToolFound,
)
from llm.response import LLMResponse, ToolCall


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


class TestStreamingIncompleteOutput:
    """Tests for handling incomplete/partial streaming output that may trigger spurious bash commands."""

    def test_incomplete_bash_block_no_closing_fence(self):
        """Incomplete bash block without closing ``` should not execute."""
        _mock_tool("bash", "[OK]")
        try:
            # Simulates streaming: model output got cut off mid-generation
            response = LLMResponse(text='```bash\nls -la')
            r = dispatch(response)
            # Should NOT execute - no closing fence, parse_bash_command returns None
            # The response should fall through to NoToolFound or be handled safely
            assert not isinstance(r, ToolResult) or r.tool_name != "bash"
        finally:
            _clear("bash")

    def test_empty_content_after_bash_fence(self):
        """Empty content after ```bash marker should not produce a command."""
        response = LLMResponse(text='```bash\n```')
        r = dispatch(response)
        # parse_bash_command returns None for empty block
        assert isinstance(r, NoToolFound)

    def test_plain_ellipsis_not_bash(self):
        """Plain '...' text should not be interpreted as a bash command."""
        _mock_tool("bash", "[OK]")
        try:
            response = LLMResponse(text="...")
            r = dispatch(response)
            # '...' alone has no code fences, so parse_bash_command returns None
            # Should fall through to NoToolFound, not execute bash
            assert isinstance(r, NoToolFound)
        finally:
            _clear("bash")

    def test_ellipsis_in_text_not_bash(self):
        """'...' embedded in regular text should not trigger bash."""
        _mock_tool("bash", "[OK]")
        try:
            response = LLMResponse(text="Running command...")
            r = dispatch(response)
            # No code fences, so no bash parsing
            assert isinstance(r, NoToolFound)
        finally:
            _clear("bash")

    def test_partial_bash_block_with_random_content(self):
        """Random content between bash fences with text parsing should execute.
        
        This test uses dispatch_with_text_parsing() since dispatch() no longer
        parses text for cloud models.
        """
        _mock_tool("bash", "[OK]")
        try:
            response = LLMResponse(text='```bash\nrandom stuff here\n```')
            r = dispatch_with_text_parsing(response)
            # With text parsing enabled, this executes bash
            assert isinstance(r, ToolResult)
            assert r.tool_name == "bash"
            assert r.output == "[OK]"
        finally:
            _clear("bash")

    def test_malformed_tool_call_xml_not_bash(self):
        """Malformed XML that looks like tool call should not become bash."""
        _mock_tool("bash", "[OK]")
        try:
            # Various malformed patterns that should NOT result in bash execution
            malformed_inputs = [
                '<tool_call>bash',  # incomplete
                '<tool_call>...</tool_call>',  # ellipsis inside
                '```bash\n...\n',  # partial
            ]
            for text in malformed_inputs:
                r = dispatch(LLMResponse(text=text))
                # None of these should result in bash ToolResult
                if isinstance(r, ToolResult):
                    assert r.tool_name != "bash", f"'{text}' should not parse as bash"
        finally:
            _clear("bash")


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
        """JSON in text content is parsed and executed with text parsing enabled."""
        _mock_tool("bash", "[OK]")
        try:
            response = LLMResponse(text='{"name": "bash", "arguments": {"command": "pwd"}}')
            r = dispatch_with_text_parsing(response)
            assert isinstance(r, ToolResult)
            assert r.tool_name == "bash"
        finally:
            _clear("bash")

    def test_json_codeblock_in_content(self):
        """JSON code block in text content is parsed and executed with text parsing."""
        _mock_tool("bash", "[OK]")
        try:
            response = LLMResponse(text='```json\n{"name": "bash", "arguments": {"command": "ls"}}\n```')
            r = dispatch_with_text_parsing(response)
            assert isinstance(r, ToolResult)
            assert r.tool_name == "bash"
        finally:
            _clear("bash")

    def test_bash_codeblock_in_content(self):
        """Bash code block in text content is executed with text parsing enabled."""
        _mock_tool("bash", "[OK]")
        try:
            response = LLMResponse(text='```bash\nls -la\n```')
            r = dispatch_with_text_parsing(response)
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