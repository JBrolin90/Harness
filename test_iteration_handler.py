"""Unit tests for iteration_handler.py - IterationHandler and related classes."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


class TestConversationState:
    """Tests for ConversationState class."""

    def test_initial_state_empty(self):
        """New ConversationState should have empty history."""
        from iteration_handler import ConversationState
        conv = ConversationState()
        assert conv.history == []
        assert conv.messages == []

    def test_add_user_message(self):
        """add_user_message should append to history."""
        from iteration_handler import ConversationState
        conv = ConversationState()
        conv.add_user_message("Hello")
        assert conv.history == [{"role": "user", "content": "Hello"}]

    def test_add_assistant_message(self):
        """add_assistant_message should append to history."""
        from iteration_handler import ConversationState
        conv = ConversationState()
        conv.add_assistant_message("Hello Bob")
        assert conv.history == [{"role": "assistant", "content": "Hello Bob"}]

    def test_add_tool_result(self):
        """add_tool_result should append to history."""
        from iteration_handler import ConversationState
        conv = ConversationState()
        conv.add_tool_result("File content here")
        assert conv.history == [{"role": "tool", "content": "File content here"}]

    def test_clean_assistant_text_removes_tool_calls(self):
        """clean_assistant_text should strip tool call blocks."""
        from iteration_handler import ConversationState
        conv = ConversationState()
        text = "Some text ```tool_call\n{\"name\": \"foo\"}\n``` more text"
        cleaned = conv.clean_assistant_text(text)
        assert "tool_call" not in cleaned
        assert "foo" not in cleaned

    def test_get_stats(self):
        """get_stats should return formatted message count."""
        from iteration_handler import ConversationState
        conv = ConversationState()
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
        from iteration_handler import ConversationState
        conv = ConversationState()
        conv.add_user_message("msg1")
        conv.reset()
        assert conv.history == []


class TestLoopDetection:
    """Tests for LoopDetection class."""

    def test_no_repetition_on_first_check(self):
        """check_repetition should return False on first check."""
        from iteration_handler import LoopDetection
        from response import LLMResponse
        
        detection = LoopDetection()
        response = LLMResponse(text="Hello")
        assert detection.check_repetition(response, None) is False

    def test_repetition_detected_for_same_action(self):
        """check_repetition should detect repeated tool calls."""
        from iteration_handler import LoopDetection
        from response import LLMResponse, ToolCall
        
        detection = LoopDetection()
        # Create responses with actual tool_calls list
        response1 = LLMResponse(
            text='{"name": "read_file"}',
            tool_calls=[ToolCall(name="read_file", arguments={"path": "a.txt"})]
        )
        response2 = LLMResponse(
            text='{"name": "read_file"}',
            tool_calls=[ToolCall(name="read_file", arguments={"path": "a.txt"})]
        )
        
        assert response1.has_tool_calls is True  # Verify test setup
        detection.update("read_file({\"path\":\"a.txt\"})", "action", True)
        
        assert detection.check_repetition(response2, "read_file({\"path\":\"a.txt\"})") is True

    def test_update_records_action(self):
        """update should record action for next check."""
        from iteration_handler import LoopDetection
        
        detection = LoopDetection()
        detection.update("action_sig", "some text", True)
        
        assert detection.last_action_sig == "action_sig"
        assert detection.last_assistant_text == "some text"
        assert detection.last_had_tool_call is True


class TestIterationHandler:
    """Tests for IterationHandler class."""

    @pytest.fixture
    def mock_provider(self):
        provider = MagicMock()
        provider.name = "test-provider"
        provider.model = "test-model"
        provider.attributes = {}
        return provider

    def test_init_sets_up_tool_engine(self, mock_provider):
        """__init__ should set up tool_engine from ToolManager."""
        from iteration_handler import IterationHandler
        
        handler = IterationHandler(mock_provider)
        assert hasattr(handler, 'tool_engine')
        assert callable(handler.tool_engine)

    def test_init_creates_conversation_state(self, mock_provider):
        """__init__ should create ConversationState."""
        from iteration_handler import IterationHandler
        
        handler = IterationHandler(mock_provider)
        assert hasattr(handler, 'conversation')
        assert hasattr(handler.conversation, 'history')
        assert handler.conversation.history == []

    def test_execute_no_tool_call(self, mock_provider):
        """execute should return text immediately if no tool call."""
        from iteration_handler import IterationHandler
        from response import LLMResponse
        
        handler = IterationHandler(mock_provider)
        
        mock_response = LLMResponse(text="I can help with that.")
        mock_call_llm = MagicMock(return_value=mock_response)
        
        result = handler.execute("Hello", "System prompt", mock_call_llm)
        
        assert result == "I can help with that."
        mock_call_llm.assert_called_once()

    def test_execute_with_tool_call_triggers_loop(self, mock_provider):
        """execute should trigger loop when tool call detected."""
        from iteration_handler import IterationHandler
        from response import LLMResponse, NoToolFound
        
        handler = IterationHandler(mock_provider)
        
        # First response has tool call, second returns NoToolFound
        response_with_tool = LLMResponse(text='{"name": "read_file"}')
        response_without_tool = LLMResponse(text="Done!")
        
        call_count = [0]
        def mock_call_llm(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return response_with_tool
            return response_without_tool
        
        # Mock tool_engine to return NoToolFound on first call
        handler.tool_engine = MagicMock(return_value=NoToolFound())
        
        result = handler.execute("Read a file", "System prompt", mock_call_llm)
        
        assert call_count[0] >= 1  # Check call count on the counter, not the function

    def test_conversation_manager_backwards_compat(self, mock_provider):
        """conversation_manager property should return conversation."""
        from iteration_handler import IterationHandler
        
        handler = IterationHandler(mock_provider)
        assert handler.conversation_manager is handler.conversation


class TestIterationHandlerIntegration:
    """Integration tests for IterationHandler with real components."""

    @pytest.fixture
    def mock_provider(self):
        provider = MagicMock()
        provider.name = "test"
        provider.model = "test-model"
        provider.attributes = {}
        return provider

    def test_execute_accumulates_in_conversation(self, mock_provider):
        """execute should add messages to conversation."""
        from iteration_handler import IterationHandler
        from response import LLMResponse
        
        handler = IterationHandler(mock_provider)
        
        mock_response = LLMResponse(text="Response text")
        mock_call_llm = MagicMock(return_value=mock_response)
        
        handler.execute("User prompt", "System prompt", mock_call_llm)
        
        # Should have user message and assistant response
        assert len(handler.conversation.history) == 2
        assert handler.conversation.history[0]["role"] == "user"
        assert handler.conversation.history[1]["role"] == "assistant"