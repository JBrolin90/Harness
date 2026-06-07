"""Unit tests for task.py - Task and related classes."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from task.task import Task; from session.conversation_history import ConversationHistory; from task.repetition_detector import RepetitionDetector


class TestConversationHistory:
    """Tests for ConversationHistory class."""

    def test_initial_state_empty(self):
        """New ConversationHistory should have empty history."""
        conv = ConversationHistory()
        assert conv.history == []
        assert conv.messages == []

    def test_add_user_message(self):
        """add_user_message should append to history."""
        conv = ConversationHistory()
        conv.add_user_message("Hello")
        assert conv.history == [{"role": "user", "content": "Hello"}]

    def test_add_assistant_message(self):
        """add_assistant_message should append to history."""
        conv = ConversationHistory()
        conv.add_assistant_message("Hello Bob")
        assert conv.history == [{"role": "assistant", "content": "Hello Bob"}]

    def test_add_tool_result(self):
        """add_tool_result should append to history."""
        conv = ConversationHistory()
        conv.add_tool_result("File content here")
        assert conv.history == [{"role": "tool", "content": "File content here"}]

    def test_clean_text_removes_tool_calls(self):
        """_clean_text should strip tool call blocks."""
        text = "Some text ```tool_call\n{\"name\": \"foo\"}\n``` more text"
        cleaned = ConversationHistory._clean_text(text)
        assert "tool_call" not in cleaned
        assert "foo" not in cleaned

    def test_get_stats(self):
        """get_stats should return formatted message count."""
        conv = ConversationHistory()
        conv.add_user_message("msg1")
        conv.add_assistant_message("msg2")
        conv.add_tool_result("msg3")
        stats = conv.get_stats()
        assert "3" in stats
        assert "u:1" in stats
        assert "a:1" in stats
        assert "t:1" in stats

    def test_reset(self):
        """reset should clear history."""
        conv = ConversationHistory()
        conv.add_user_message("msg1")
        conv.reset()
        assert conv.history == []


class TestRepetitionDetector:
    """Tests for RepetitionDetector class."""

    def test_no_repetition_on_first_check(self):
        """is_repetitive should return False on first check."""
        from llm.response import LLMResponse
        
        detector = RepetitionDetector()
        response = LLMResponse(text="Hello")
        assert detector.is_repetitive(response, None) is False

    def test_repetition_detected_for_same_action(self):
        """is_repetitive should detect repeated tool calls."""
        from llm.response import LLMResponse, ToolCall
        
        detector = RepetitionDetector()
        response1 = LLMResponse(
            text='{"name": "read_file"}',
            tool_calls=[ToolCall(name="read_file", arguments={"path": "a.txt"})]
        )
        response2 = LLMResponse(
            text='{"name": "read_file"}',
            tool_calls=[ToolCall(name="read_file", arguments={"path": "a.txt"})]
        )
        
        assert response1.has_tool_calls is True
        detector.record("read_file({\"path\":\"a.txt\"})", "action", True)
        
        assert detector.is_repetitive(response2, "read_file({\"path\":\"a.txt\"})") is True

    def test_record_stores_action(self):
        """record should store action for next check."""
        
        detector = RepetitionDetector()
        detector.record("action_sig", "some text", True)
        
        assert detector._previous.signature == "action_sig"
        assert detector._previous.assistant_text == "some text"
        assert detector._previous.had_tool_call is True


class TestTask:
    """Tests for Task class."""

    @pytest.fixture
    def mock_provider(self):
        provider = MagicMock()
        provider.name = "test-provider"
        provider.model = "test-model"
        return provider

    @pytest.fixture
    def mock_execute_tools(self):
        return MagicMock()

    def test_init_sets_up_execute_tools(self, mock_execute_tools):
        """__init__ should store the execute_tools."""
        
        handler = Task(mock_execute_tools)
        assert hasattr(handler, 'execute_tools')
        assert handler.execute_tools is mock_execute_tools

    def test_init_creates_conversation_state(self, mock_execute_tools):
        """__init__ should create ConversationHistory."""
        
        handler = Task(mock_execute_tools)
        assert hasattr(handler, 'conversation')
        assert hasattr(handler.conversation, 'history')
        assert handler.conversation.history == []

    def test_execute_no_tool_call(self, mock_provider, mock_execute_tools):
        """run should return text immediately if no tool call."""
        from llm.response import LLMResponse, NoToolFound
        
        handler = Task(mock_execute_tools)
        
        # When LLM returns text without tool_calls, execute_tools should return NoToolFound
        # which causes immediate return of the text response
        mock_execute_tools.return_value = NoToolFound()
        
        mock_response = LLMResponse(text="I can help with that.")
        custom_consult_llm = MagicMock(return_value=mock_response)
        
        result = handler.run("Hello", "System prompt", custom_consult_llm, mock_provider)
        
        assert result == "I can help with that."
        custom_consult_llm.assert_called_once()

    def test_execute_with_tool_call_triggers_loop(self, mock_provider, mock_execute_tools):
        """run should trigger loop when tool call detected."""
        from llm.response import LLMResponse, NoToolFound
        
        handler = Task(mock_execute_tools)
        
        response_with_tool = LLMResponse(text='{"name": "read_file"}')
        response_without_tool = LLMResponse(text="Done!")
        
        call_count = [0]
        def custom_consult_llm(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return response_with_tool
            return response_without_tool
        
        mock_execute_tools.return_value = NoToolFound()
        
        result = handler.run("Read a file", "System prompt", custom_consult_llm, mock_provider)
        
        assert call_count[0] >= 1


class TestTaskIntegration:
    """Integration tests for Task with real components."""

    @pytest.fixture
    def mock_provider(self):
        provider = MagicMock()
        provider.name = "test"
        provider.model = "test-model"
        return provider

    def test_execute_accumulates_in_conversation(self, mock_provider):
        """run should add messages to conversation."""
        from llm.response import LLMResponse, ToolResult, NoToolFound
        from tool_dispatch import dispatch
        
        # Use actual dispatch function which returns NoToolFound when no tool call detected
        handler = Task(dispatch)
        
        mock_response = LLMResponse(text="I can help with that.")
        custom_consult_llm = MagicMock(return_value=mock_response)
        
        result = handler.run("User prompt", "System prompt", custom_consult_llm, mock_provider)
        
        # Should have user message and assistant response (no tool result since no tool call)
        assert len(handler.conversation.history) == 2
        assert handler.conversation.history[0]["role"] == "user"
        assert handler.conversation.history[1]["role"] == "assistant"


class TestTextBasedToolCalls:
    """Tests for text-based tool call detection (e.g., bash-style ```bash ...```)."""

    @pytest.fixture
    def mock_provider(self):
        provider = MagicMock()
        provider.name = "test"
        provider.model = "test-model"
        return provider

    def test_task_executes_bash_style_text_tool_call(self, mock_provider):
        """Task.run() should execute text-based tool calls (e.g., ```bash read_file ...```)."""
        from llm.response import LLMResponse, ToolResult
        from tool_dispatch import dispatch_with_text_parsing
        
        handler = Task(dispatch_with_text_parsing)
        
        # Model outputs bash-style tool call in text (not structured tool_calls)
        bash_style_response = LLMResponse(
            text='```bash\nread_file bob.py\n```',
            tool_calls=[]
        )
        
        call_count = [0]
        def mock_consult_llm(messages, system_prompt, provider):
            call_count[0] += 1
            if call_count[0] == 1:
                return bash_style_response
            # Second call returns no tool call
            return LLMResponse(text="Done reading bob.py")
        
        # Use mock to avoid actual file read
        with patch('tools.base_tool.BaseTool.dispatch') as mock_dispatch:
            mock_dispatch.return_value = "file content here"
            result = handler.run("Read bob.py", "System prompt", mock_consult_llm, mock_provider)
        
        # Should have called the tool
        assert call_count[0] >= 1
        # dispatch should have been called with read_file
        mock_dispatch.assert_called()
        call_args = mock_dispatch.call_args
        assert call_args[0][0] == "bash"  # tool name
        assert "read_file" in call_args[0][1].get("command", "")

    def test_task_executes_json_codeblock_tool_call(self, mock_provider):
        """Task.run() should execute JSON codeblock tool calls (```json {"name": ...} ```)."""
        from llm.response import LLMResponse, ToolResult
        from tool_dispatch import dispatch_with_text_parsing
        
        handler = Task(dispatch_with_text_parsing)
        
        # Model outputs JSON codeblock tool call in text
        json_response = LLMResponse(
            text='```json\n{"name": "read_file", "arguments": {"path": "bob.py"}}\n```',
            tool_calls=[]
        )
        
        def mock_consult_llm(messages, system_prompt, provider):
            return json_response
        
        with patch('tools.base_tool.BaseTool.dispatch') as mock_dispatch:
            mock_dispatch.return_value = "file content"
            result = handler.run("Read bob.py", "System prompt", mock_consult_llm, mock_provider)
        
        # Should have called read_file tool
        mock_dispatch.assert_called()
        call_args = mock_dispatch.call_args
        assert call_args[0][0] == "read_file"

    def test_task_executes_json_embedded_in_text_without_code_fences(self, mock_provider):
        """Task.run() should find JSON embedded in text without code fences.
        
        Models like qwen may output: 'Here's the tool: {"name": "read_file", ...}'
        without code fences. This test ensures the parser can find and execute it.
        """
        from llm.response import LLMResponse, ToolResult
        from tool_dispatch import dispatch_with_text_parsing
        
        handler = Task(dispatch_with_text_parsing)
        
        # Model outputs JSON embedded in regular text (no code fences)
        embedded_json_response = LLMResponse(
            text='Sure, I\'ll call the read_file tool: {\"name\": \"read_file\", \"arguments\": {\"path\": \"bob.py\"}}',
            tool_calls=[]
        )
        
        def mock_consult_llm(messages, system_prompt, provider):
            return embedded_json_response
        
        with patch('tools.base_tool.BaseTool.dispatch') as mock_dispatch:
            mock_dispatch.return_value = "file content"
            result = handler.run("Read bob.py", "System prompt", mock_consult_llm, mock_provider)
        
        # Should have found and executed the JSON tool call
        mock_dispatch.assert_called()
        call_args = mock_dispatch.call_args
        assert call_args[0][0] == "read_file"
        assert call_args[0][1].get("path") == "bob.py"

    def test_task_executes_multiline_json_embedded_in_text(self, mock_provider):
        """Task.run() should find multiline JSON embedded in text without code fences.
        
        Model outputs JSON with newlines/indentation (like formatted JSON) embedded in text.
        This tests the bracket-counting approach for finding JSON in text.
        """
        from llm.response import LLMResponse, ToolResult
        from tool_dispatch import dispatch_with_text_parsing
        
        handler = Task(dispatch_with_text_parsing)
        
        # Model outputs multiline formatted JSON (no code fences)
        multiline_json_response = LLMResponse(
            text='Here is the tool call: {\n    "name": "read_file",\n    "arguments": {\n        "path": "bob.py"\n    }\n}',
            tool_calls=[]
        )
        
        def mock_consult_llm(messages, system_prompt, provider):
            return multiline_json_response
        
        with patch('tools.base_tool.BaseTool.dispatch') as mock_dispatch:
            mock_dispatch.return_value = "file content"
            result = handler.run("Read bob.py", "System prompt", mock_consult_llm, mock_provider)
        
        # Should have found and executed the JSON tool call
        mock_dispatch.assert_called()
        call_args = mock_dispatch.call_args
        assert call_args[0][0] == "read_file"
        assert call_args[0][1].get("path") == "bob.py"

    def test_task_returns_text_when_no_tool_call_found(self, mock_provider):
        """Task.run() should return text response when no tool call is detected."""
        from llm.response import LLMResponse, NoToolFound
        from tool_dispatch import dispatch_with_text_parsing
        
        handler = Task(dispatch_with_text_parsing)
        
        # Model outputs plain text (no tool call)
        text_response = LLMResponse(
            text="I cannot help with that.",
            tool_calls=[]
        )
        
        def mock_consult_llm(messages, system_prompt, provider):
            return text_response
        
        result = handler.run("Do something", "System prompt", mock_consult_llm, mock_provider)
        
        assert result == "I cannot help with that."

    def test_task_executes_tool_format_with_arguments_key(self, mock_provider):
        """Task.run() should handle {"tool": ..., "arguments": {...}} format (not just {"name": ...})."""
        from llm.response import LLMResponse, ToolResult
        from tool_dispatch import dispatch_with_text_parsing
        
        handler = Task(dispatch_with_text_parsing)
        
        # Model outputs JSON with "tool" (not "name") and "arguments" (not "args")
        json_response = LLMResponse(
            text='{"tool": "read_file", "arguments": {"path": "bob.py"}}',
            tool_calls=[]
        )
        
        def mock_consult_llm(messages, system_prompt, provider):
            return json_response
        
        with patch('tools.base_tool.BaseTool.dispatch') as mock_dispatch:
            mock_dispatch.return_value = "file content"
            result = handler.run("Read bob.py", "System prompt", mock_consult_llm, mock_provider)
        
        # Should have called read_file with correct arguments
        mock_dispatch.assert_called()
        call_args = mock_dispatch.call_args
        assert call_args[0][0] == "read_file"
        assert call_args[0][1].get("path") == "bob.py"

    def test_dispatch_engine_selection_with_text_parsing_attributes(self, mock_provider):
        """ToolManager should select dispatch_with_text_parsing when any text_parse_* attribute is True."""
        from tool_manager import ToolManager
        from tool_dispatch import dispatch, dispatch_with_text_parsing
        
        # All text parsing attribute combinations
        text_parsing_configs = [
            {"text_parse_json_codeblock": True},
            {"text_parse_json_raw": True},
            {"text_parse_bash": True},
            {"text_parse_xml": True},
            {"text_parse_colon_xml": True},
            {"text_parse_plain_xml": True},
            {"text_parse_json_codeblock": True, "text_parse_json_raw": True},
            {"text_parse_json_codeblock": True, "text_parse_bash": True, "text_parse_xml": True},
        ]
        
        for attrs in text_parsing_configs:
            tm = ToolManager(attrs)
            assert tm.execute_tools == dispatch_with_text_parsing, \
                f"Expected dispatch_with_text_parsing for attrs={attrs}, got {tm.execute_tools.__name__}"

    def test_dispatch_engine_selection_without_text_parsing_attributes(self, mock_provider):
        """ToolManager should select dispatch (not dispatch_with_text_parsing) when no text_parse_* is True."""
        from tool_manager import ToolManager
        from tool_dispatch import dispatch, dispatch_with_text_parsing
        
        no_text_parsing_configs = [
            {},
            {"enable_small_model_guidance": True},
            {"response_format": {"type": "json_object"}},
        ]
        
        for attrs in no_text_parsing_configs:
            tm = ToolManager(attrs)
            assert tm.execute_tools == dispatch, \
                f"Expected dispatch for attrs={attrs}, got {tm.execute_tools.__name__}"

    def test_repeated_text_tool_call_only_executes_once(self, mock_provider):
        """When model repeats the same text-based tool call, tool should only execute once.
        
        This tests the bug where the tool was being executed twice (once per iteration)
        before repetition was detected. The fix checks for repetition BEFORE executing
        the tool, not after.
        """
        from llm.response import LLMResponse
        from tool_dispatch import dispatch_with_text_parsing
        
        handler = Task(dispatch_with_text_parsing)
        
        # Model outputs same JSON tool call text twice (simulating repetition)
        json_tool_call = '{"name": "memory", "arguments": {"action": "read"}}'
        repeated_response = LLMResponse(text=json_tool_call, tool_calls=[])
        
        call_count = [0]
        def mock_consult_llm(messages, system_prompt, provider):
            call_count[0] += 1
            # Return the same response every time (simulating model repeating itself)
            return repeated_response
        
        with patch('tools.base_tool.BaseTool.dispatch') as mock_dispatch:
            mock_dispatch.return_value = 'memory content'
            result = handler.run('Check memory', 'You are helpful.', mock_consult_llm, mock_provider)
            
            # Tool should only be executed ONCE, not twice
            # If bug exists, tool would be called twice before repetition detected
            assert mock_dispatch.call_count == 1, \
                f"Tool was executed {mock_dispatch.call_count} times, expected 1"
            
            # Result should NOT be the JSON tool call text (that's the bug)
            # Result should be empty or a proper response, not the echoed JSON
            assert result != json_tool_call, \
                f"Result was JSON tool call text, should not echo repeated tool calls"

    def test_repeated_tool_call_returns_proper_response(self, mock_provider):
        """When repetition is detected, the loop should return a proper response, not JSON."""
        from llm.response import LLMResponse
        from tool_dispatch import dispatch_with_text_parsing
        
        handler = Task(dispatch_with_text_parsing)
        
        # First response: model calls memory
        # Second response: model calls memory again (repetition)
        # Third response: model provides actual content
        json_tool_call = '{"name": "memory", "arguments": {"action": "read"}}'
        
        responses = [
            LLMResponse(text=json_tool_call, tool_calls=[]),  # First call - executes tool
            LLMResponse(text=json_tool_call, tool_calls=[]),  # Second call - repetition detected
            LLMResponse(text='Here is the memory content you requested.', tool_calls=[]),  # Proper response
        ]
        
        response_index = [0]
        def mock_consult_llm(messages, system_prompt, provider):
            resp = responses[response_index[0]]
            response_index[0] = min(response_index[0] + 1, len(responses) - 1)
            return resp
        
        with patch('tools.base_tool.BaseTool.dispatch') as mock_dispatch:
            mock_dispatch.return_value = 'memory content'
            result = handler.run('Check memory', 'You are helpful.', mock_consult_llm, mock_provider)
            
            # When repetition is detected, result should be the repetition message, not JSON
            # The key is that it should NOT be the JSON tool call text
            assert result != json_tool_call, \
                f"Result was JSON tool call text, should not echo repeated tool calls"
            assert 'Repetition detected' in result or result == '', \
                f"Result should indicate repetition or be empty, got: {result}"
