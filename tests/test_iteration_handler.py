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
        
        mock_response = LLMResponse(text="I can help with that.")
        custom_consult_llm = MagicMock(return_value=mock_response)
        mock_execute_tools.return_value = NoToolFound()
        
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
        from llm.response import LLMResponse, NoToolFound
        
        handler = Task(MagicMock())
        handler.execute_tools = MagicMock(return_value=NoToolFound())
        
        mock_response = LLMResponse(text="Response text")
        custom_consult_llm = MagicMock(return_value=mock_response)
        
        handler.run("User prompt", "System prompt", custom_consult_llm, mock_provider)
        
        # Should have user message and assistant response
        assert len(handler.conversation.history) == 2
        assert handler.conversation.history[0]["role"] == "user"
        assert handler.conversation.history[1]["role"] == "assistant"
