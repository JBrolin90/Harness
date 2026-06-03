"""Integration test: MiniMax-M2.7 'Please review tool_dispatch.py' scenario.

With the fix: dispatch() now ONLY handles native tool_calls for cloud models.
Text responses are NOT parsed as commands. This prevents MiniMax's markdown
code blocks (```bash) from being misinterpreted as bash tool calls.

For smaller models (ollama) that may output tool calls in text format,
dispatch_with_text_parsing() can be used instead.
"""
import pytest
from tool_dispatch import dispatch, dispatch_with_text_parsing, parse_bash_command
from llm.response import LLMResponse, ToolCall, ToolResult, NoToolFound
from tools.base_tool import BaseTool


class MockBashTool(BaseTool):
    """Mock bash tool that records calls without executing anything."""
    name = "bash"
    description = ""
    parameters = {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}
    
    _calls = []
    
    def execute(self, **kw):
        MockBashTool._calls.append(kw)
        return f"[EXECUTED: bash with {kw}]"


class MockReadTool(BaseTool):
    """Mock read_file tool."""
    name = "read_file"
    description = ""
    parameters = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    
    _calls = []
    
    def execute(self, **kw):
        MockReadTool._calls.append(kw)
        return "[FILE CONTENT]"


@pytest.fixture(autouse=True)
def setup_mock_tools():
    """Register mock tools and clear call logs before each test."""
    MockBashTool._calls = []
    MockReadTool._calls = []
    BaseTool._registry["bash"] = MockBashTool
    BaseTool._registry["read_file"] = MockReadTool
    yield
    # Cleanup
    BaseTool._registry.pop("bash", None)
    BaseTool._registry.pop("read_file", None)


class TestDispatchCloudModel:
    """Tests for dispatch() - cloud models (MiniMax) - text NOT parsed as commands."""
    
    def test_review_with_bash_ellipsis_no_execution(self):
        """
        FIXED: With dispatch(), text ```bash\\n...\\n``` does NOT execute bash.
        
        This was the original bug - MiniMax outputs markdown with ```bash
        and parse_bash_command was incorrectly treating it as a command request.
        
        Now dispatch() only handles native tool_calls.
        """
        response = LLMResponse(
            text="Here's my review of `tool_dispatch.py`:\n\n```bash\n...\n```",
            tool_calls=[],
            error=None
        )
        
        result = dispatch(response)
        
        # With dispatch(), text is NOT parsed - should be NoToolFound
        assert isinstance(result, NoToolFound)
        assert not MockBashTool._calls  # No bash execution
    
    def test_ellipsis_only_is_not_bash(self):
        """Plain '...' without code fences does NOT execute bash."""
        response = LLMResponse(text="...", tool_calls=[], error=None)
        
        result = dispatch(response)
        
        assert isinstance(result, NoToolFound)
        assert not MockBashTool._calls
    
    def test_incomplete_bash_block_no_execution(self):
        """Incomplete ```bash\\n... (no closing ```) does NOT execute."""
        response = LLMResponse(text="```bash\n...", tool_calls=[], error=None)
        
        result = dispatch(response)
        
        assert isinstance(result, NoToolFound)
        assert not MockBashTool._calls
    
    def test_native_tool_call_bash_still_works(self):
        """
        Native tool_calls still work - model can still call bash when needed.
        """
        response = LLMResponse(
            tool_calls=[ToolCall(name="bash", arguments={"command": "ls -la"})],
            text="",
            error=None
        )
        
        result = dispatch(response)
        
        # Native tool call should still work
        assert isinstance(result, ToolResult)
        assert MockBashTool._calls == [{"command": "ls -la"}]
    
    def test_native_tool_call_bash_with_ellipsis(self):
        """Native tool_call with '...' as command works (model's choice)."""
        response = LLMResponse(
            tool_calls=[ToolCall(name="bash", arguments={"command": "..."})],
            text="",
            error=None
        )
        
        result = dispatch(response)
        
        # Native tool call with '...' - model intended this
        assert MockBashTool._calls == [{"command": "..."}]
    
    def test_read_then_review_pattern_fixed(self):
        """
        Full flow: model reads file, then produces review with ```bash block.
        
        With fix: the ```bash block in text is IGNORED - no spurious execution.
        """
        # Step 1: Model calls read_file (structured tool call)
        step1 = LLMResponse(
            tool_calls=[ToolCall(name="read_file", arguments={"path": "tool_dispatch.py"})],
            text="[Reading file...]",
            error=None
        )
        r1 = dispatch(step1)
        assert MockReadTool._calls == [{"path": "tool_dispatch.py"}]
        
        # Step 2: Model produces review with ```bash\n...\n``` in text
        step2 = LLMResponse(
            text="```bash\n...\n```\n\n## Summary\n\nThe module is well-structured.",
            tool_calls=[],
            error=None
        )
        r2 = dispatch(step2)
        
        # With dispatch(), text is NOT parsed - no bash execution
        assert isinstance(r2, NoToolFound)
        assert not MockBashTool._calls
    
    def test_review_without_bash_block(self):
        """Normal review without code blocks - no tool execution."""
        response = LLMResponse(
            text="Here's my review of tool_dispatch.py:\n\n## Parser Precedence\n\nThe dispatch function is well-structured.",
            tool_calls=[],
            error=None
        )
        
        result = dispatch(response)
        
        assert isinstance(result, NoToolFound)
        assert not MockBashTool._calls


class TestDispatchWithTextParsing:
    """Tests for dispatch_with_text_parsing() - smaller models that output text commands."""
    
    def test_bash_ellipsis_in_text_executes(self):
        """
        With dispatch_with_text_parsing(), text ```bash\\n...\\n``` DOES execute bash.
        
        This is intended for smaller models (ollama) that may not use structured
        tool calls consistently and may output tool calls in text format.
        """
        response = LLMResponse(
            text="```bash\n...\n```",
            tool_calls=[],
            error=None
        )
        
        result = dispatch_with_text_parsing(response)
        
        # With text parsing enabled, this executes bash (intended for smaller models)
        assert isinstance(result, ToolResult)
        assert MockBashTool._calls == [{"command": "..."}]
    
    def test_native_tool_call_takes_precedence(self):
        """Native tool_calls still work in dispatch_with_text_parsing."""
        response = LLMResponse(
            tool_calls=[ToolCall(name="bash", arguments={"command": "ls -la"})],
            text="Some text",
            error=None
        )
        
        result = dispatch_with_text_parsing(response)
        
        # Native tool call should be executed (not text parsing)
        assert MockBashTool._calls == [{"command": "ls -la"}]
    
    def test_plain_json_in_text(self):
        """JSON in text is parsed and executed."""
        response = LLMResponse(
            text='{"name": "bash", "arguments": {"command": "pwd"}}',
            tool_calls=[],
            error=None
        )
        
        result = dispatch_with_text_parsing(response)
        
        assert isinstance(result, ToolResult)
        assert MockBashTool._calls == [{"command": "pwd"}]


class TestBashCommandValidation:
    """Tests for command validation (for potential future safeguards)."""
    
    def test_parse_bash_command_still_parses_ellipsis(self):
        """
        parse_bash_command() still correctly parses ```bash\\n...\\n```
        
        The difference is that dispatch() no longer USES parse_bash_command
        for cloud models. The parser itself is not broken - it just shouldn't
        be applied to cloud model text responses.
        """
        result = parse_bash_command("```bash\n...\n```")
        assert result == {"name": "bash", "arguments": {"command": "..."}}
    
    def test_parse_bash_command_valid_command(self):
        """parse_bash_command works correctly for valid commands."""
        result = parse_bash_command("```bash\nls -la\n```")
        assert result == {"name": "bash", "arguments": {"command": "ls -la"}}