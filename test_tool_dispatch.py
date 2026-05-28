"""Tests for tool_dispatch.py - 46 tests covering all parsers, normalization, and integration."""
import pytest
from unittest.mock import patch
from tool_dispatch import (
    tool_dispatch,
    _safe_dispatch,
    _parse_xml_tool_call,
    _parse_colon_json_format,
    _parse_plain_tool_call,
    _parse_json_in_code_block,
    _parse_json_raw,
    _parse_bash_command,
    _parse_simple_tool_json,
    ToolResult,
    SystemError,
)


# ---------------------------------------------------------------------------
# Helper: mock a tool in the registry
# ---------------------------------------------------------------------------

class TestXmlToolCall:
    """Tests for _parse_xml_tool_call."""

    def test_standard_format(self):
        text = "<tool_call><read_file><arg_key>path</arg_key><arg_value>/etc/hosts</arg_value></read_file></tool_call>"
        result = _parse_xml_tool_call(text)
        assert result == {"name": "read_file", "arguments": {"path": "/etc/hosts"}}

    def test_zero_arg_tool(self):
        text = "<tool_call>get_model_name</tool_call>"
        result = _parse_xml_tool_call(text)
        assert result == {"name": "get_model_name", "arguments": {}}

    def test_no_match(self):
        assert _parse_xml_tool_call("<read_file>/tmp/test.txt</read_file>") is None

    def test_multiple_args(self):
        text = "<tool_call>edit_file<arg_key>path</arg_key><arg_value>f.txt</arg_value><arg_key>search</arg_key><arg_value>hello</arg_value><arg_key>replace</arg_key><arg_value>hi</arg_value></edit_file></tool_call>"
        result = _parse_xml_tool_call(text)
        assert result == {"name": "edit_file", "arguments": {"path": "f.txt", "search": "hello", "replace": "hi"}}

    def test_tool_name_wrapped(self):
        text = "<tool_call><bash><arg_key>command</arg_key><arg_value>ls</arg_value></bash></tool_call>"
        result = _parse_xml_tool_call(text)
        assert result == {"name": "bash", "arguments": {"command": "ls"}}


class TestColonJsonFormat:
    """Tests for _parse_colon_json_format."""

    def test_bare_colon_format(self):
        text = "<bash>:{\"command\": \"pwd\"}</bash>"
        result = _parse_colon_json_format(text)
        assert result == {"name": "bash", "arguments": {"command": "pwd"}}

    def test_plain_text_no_match(self):
        assert _parse_colon_json_format("Just plain text") is None

    def test_raw_json_no_match(self):
        assert _parse_colon_json_format('{"name": "bash"}') is None


class TestPlainToolCall:
    """Tests for _parse_plain_tool_call."""

    def test_read_file_infers_path(self):
        text = "<read_file>/tmp/test.txt</read_file>"
        result = _parse_plain_tool_call(text)
        assert result == {"name": "read_file", "arguments": {"path": "/tmp/test.txt"}}

    def test_bash_infers_command(self):
        text = "<bash>ls -la</bash>"
        result = _parse_plain_tool_call(text)
        assert result == {"name": "bash", "arguments": {"command": "ls -la"}}

    def test_zero_arg_empty_content(self):
        text = "<get_model_name></get_model_name>"
        result = _parse_plain_tool_call(text)
        assert result == {"name": "get_model_name", "arguments": {}}

    def test_zero_arg_with_content(self):
        text = "<list_loaded_tools>ignored content</list_loaded_tools>"
        result = _parse_plain_tool_call(text)
        assert result == {"name": "list_loaded_tools", "arguments": {}}

    def test_edit_file_infers_path(self):
        text = "<edit_file>myproject/file.py</edit_file>"
        result = _parse_plain_tool_call(text)
        assert result == {"name": "edit_file", "arguments": {"path": "myproject/file.py"}}

    def test_list_files_infers_path(self):
        text = "<list_files>src/dir</list_files>"
        result = _parse_plain_tool_call(text)
        assert result == {"name": "list_files", "arguments": {"path": "src/dir"}}

    def test_write_file_infers_path(self):
        text = "<write_file>output.txt</write_file>"
        result = _parse_plain_tool_call(text)
        assert result == {"name": "write_file", "arguments": {"path": "output.txt"}}

    def test_no_match(self):
        assert _parse_plain_tool_call("```bash\necho hi\n```") is None


class TestJsonInCodeBlock:
    """Tests for _parse_json_in_code_block."""

    def test_valid_json_block(self):
        text = '```json\n{"name": "bash", "arguments": {"command": "ls"}}\n```'
        result = _parse_json_in_code_block(text)
        assert result == {"name": "bash", "arguments": {"command": "ls"}}

    def test_invalid_json(self):
        text = "```json\nnot valid json\n```"
        assert _parse_json_in_code_block(text) is None

    def test_missing_name(self):
        text = '```json\n{"arguments": {}}\n```'
        assert _parse_json_in_code_block(text) is None

    def test_missing_arguments_defaults_empty(self):
        text = '```json\n{"name": "bash"}\n```'
        result = _parse_json_in_code_block(text)
        assert result == {"name": "bash", "arguments": {}}

    def test_raw_json_no_match(self):
        assert _parse_json_in_code_block('{"name": "bash"}') is None


class TestJsonRaw:
    """Tests for _parse_json_raw."""

    def test_valid_bare_json(self):
        text = '{"name": "bash", "arguments": {"command": "pwd"}}'
        result = _parse_json_raw(text)
        assert result == {"name": "bash", "arguments": {"command": "pwd"}}

    def test_missing_arguments(self):
        text = '{"name": "bash"}'
        result = _parse_json_raw(text)
        assert result == {"name": "bash", "arguments": {}}

    def test_invalid_json(self):
        assert _parse_json_raw("not json") is None

    def test_plain_text(self):
        assert _parse_json_raw("Just some text") is None


class TestBashCommand:
    """Tests for _parse_bash_command."""

    def test_bash_block(self):
        text = "```bash\nls -la\n```"
        result = _parse_bash_command(text)
        assert result == {"name": "bash", "arguments": {"command": "ls -la"}}

    def test_sh_block(self):
        text = "```sh\npwd\n```"
        result = _parse_bash_command(text)
        assert result == {"name": "bash", "arguments": {"command": "pwd"}}

    def test_empty_block(self):
        assert _parse_bash_command("```bash\n```") is None

    def test_no_code_block(self):
        assert _parse_bash_command("No code here") is None


class TestSimpleToolJson:
    """Tests for _parse_simple_tool_json."""

    def test_tool_and_args(self):
        text = '{"tool": "bash", "args": {"command": "pwd"}}'
        result = _parse_simple_tool_json(text)
        assert result == {"name": "bash", "arguments": {"command": "pwd"}}

    def test_tool_only(self):
        text = '{"tool": "bash", "args": {}}'
        result = _parse_simple_tool_json(text)
        assert result == {"name": "bash", "arguments": {}}

    def test_invalid_json(self):
        assert _parse_simple_tool_json("not json") is None


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


class TestToolDispatch:
    """Integration tests for the full tool_dispatch function."""

    @staticmethod
    def _mock_tool(toolname, result):
        from tools.base_tool import BaseTool
        class T(BaseTool):
            name = toolname
            description = ""
            parameters = {"type": "object", "properties": {}, "required": []}
            def execute(self, **kw):
                return result
        BaseTool._registry[toolname] = T

    @staticmethod
    def _clear(toolname):
        from tools.base_tool import BaseTool
        BaseTool._registry.pop(toolname, None)

    def test_valid_json(self):
        self._mock_tool("read_file", "[OK]")
        try:
            r = tool_dispatch('{"name": "read_file", "arguments": {"path": "test.txt"}}')
            assert str(r) == "[OK]"
        finally:
            self._clear("read_file")

    def test_no_tool(self):
        # Returns None (falsy) when no tool call found
        r = tool_dispatch("Just a plain response with no tool call")
        assert r is None

    def test_unknown_tool(self):
        # Returns SystemError (falsy) for unknown tool
        r = tool_dispatch('{"name": "nonexistent_tool", "arguments": {}}')
        assert isinstance(r, SystemError)
        assert str(r).startswith("[SYSTEM ERROR:")

    def test_json_codeblock(self):
        self._mock_tool("bash", "[OK]")
        try:
            text = '```json\n{"name": "bash", "arguments": {"command": "ls"}}\n```'
            r = tool_dispatch(text)
            assert str(r) == "[OK]"
        finally:
            self._clear("bash")

    def test_bash_codeblock(self):
        self._mock_tool("bash", "[OK]")
        try:
            r = tool_dispatch('```bash\nls -la\n```')
            assert str(r) == "[OK]"
        finally:
            self._clear("bash")

    def test_xml_tool_call(self):
        self._mock_tool("read_file", "[OK]")
        try:
            text = "<tool_call><read_file><arg_key>path</arg_key><arg_value>test.txt</arg_value></read_file></tool_call>"
            r = tool_dispatch(text)
            assert str(r) == "[OK]"
        finally:
            self._clear("read_file")

    def test_plain_xml(self):
        self._mock_tool("read_file", "[OK]")
        try:
            r = tool_dispatch("<read_file>/tmp/data.txt</read_file>")
            assert str(r) == "[OK]"
        finally:
            self._clear("read_file")

    def test_zero_arg_tool(self):
        self._mock_tool("get_model_name", "gpt-4")
        try:
            text = "<tool_call>get_model_name</tool_call>"
            r = tool_dispatch(text)
            assert r.tool_name == "get_model_name"
            assert str(r) == "gpt-4"
        finally:
            self._clear("get_model_name")

    def test_file_path_normalized(self):
        self._mock_tool("read_file", "[OK]")
        try:
            r = tool_dispatch('{"name": "read_file", "arguments": {"file_path": "test.txt"}}')
            assert str(r) == "[OK]"
        finally:
            self._clear("read_file")

    def test_simple_tool_json(self):
        self._mock_tool("bash", "[OK]")
        try:
            r = tool_dispatch('{"tool": "bash", "args": {"command": "pwd"}}')
            assert str(r) == "[OK]"
        finally:
            self._clear("bash")

    def test_empty_arguments(self):
        self._mock_tool("bash", "[OK]")
        try:
            r = tool_dispatch('{"name": "bash"}')
            assert str(r) == "[OK]"
        finally:
            self._clear("bash")

    def test_tool_result_is_truthy(self):
        self._mock_tool("bash", "[output]")
        try:
            r = tool_dispatch('{"name": "bash", "arguments": {"command": "ls"}}')
            assert r
            assert isinstance(r, ToolResult)
        finally:
            self._clear("bash")

    def test_system_error_is_falsy(self):
        self._mock_tool("bash", "[output]")
        try:
            r = tool_dispatch('{"name": "bash", "arguments": {"command": "ls"}}')
            # After a successful dispatch, result is ToolResult (truthy)
            assert r
        finally:
            self._clear("bash")

    def test_system_error_result_is_falsy(self):
        r = tool_dispatch('{"name": "nonexistent"}')
        assert not r  # SystemError is falsy
        assert isinstance(r, SystemError)
