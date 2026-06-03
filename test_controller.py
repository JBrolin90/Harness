"""Unit tests for controller.py - Harness controller."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


class TestHarnessControllerInit:
    """Tests for HarnessController.__init__()"""

    @patch('controller.ProviderManager')
    def test_init_creates_instance_state(self, mock_pm_class):
        """__init__() should create instance attributes."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "test-provider"
        mock_provider.model = "test-model"
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from controller import HarnessController
        ctrl = HarnessController()

        assert hasattr(ctrl, 'current_provider')
        assert hasattr(ctrl, 'conversation_manager')
        assert hasattr(ctrl, 'system_prompt_manager')

    @patch('controller.ProviderManager')
    def test_reset_clears_history(self, mock_pm_class):
        """reset() should clear conversation history."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from controller import HarnessController
        ctrl = HarnessController()
        ctrl.conversation_manager.history = [{"role": "user", "content": "test"}]

        ctrl.reset()

        assert ctrl.conversation_manager.history == []


class TestHarnessControllerRunTask:
    """Tests for HarnessController.run_task()"""

    @pytest.fixture
    def controller_instance(self):
        """Create a mocked controller instance for testing."""
        with patch('controller.ProviderManager') as mock_pm_class:
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_provider.name = "test"
            mock_provider.model = "test-model"
            mock_provider.provider_type = "minimax"
            mock_provider.attributes = {}
            mock_pm_instance.get_provider.return_value = mock_provider

            from controller import HarnessController
            ctrl = HarnessController()
            ctrl.current_provider = MagicMock()
            ctrl.system_prompt = "Test prompt"
            ctrl._mock_tool_engine = MagicMock()
            yield ctrl

    @patch('brain.call_llm')
    def test_run_task_adds_to_history(self, mock_call_llm, controller_instance):
        """run_task() should append user message and assistant response to history."""
        from response import LLMResponse
        mock_call_llm.return_value = LLMResponse(text="Hello from Bob")

        controller_instance.run_task("Hello Bob")

        assert len(controller_instance.conversation_manager.history) == 2
        assert controller_instance.conversation_manager.history[0]["role"] == "user"
        assert controller_instance.conversation_manager.history[0]["content"] == "Hello Bob"
        assert controller_instance.conversation_manager.history[1]["role"] == "assistant"

    @patch('brain.call_llm')
    def test_run_task_no_tool_returns_immediately(self, mock_call_llm, controller_instance):
        """If no tool call detected, run_task should return immediately."""
        from response import LLMResponse
        mock_call_llm.return_value = LLMResponse(text="I can help with that.")

        controller_instance.run_task("Hello")

        assert mock_call_llm.call_count == 1

    @patch('brain.call_llm')
    def test_run_task_with_tool_call(self, mock_call_llm, controller_instance):
        """Tool dispatch is triggered when response has tool call."""
        from response import LLMResponse, NoToolFound
        mock_call_llm.return_value = LLMResponse(text="Done")
        controller_instance._mock_tool_engine = MagicMock(return_value=NoToolFound())

        controller_instance.run_task("Read the file", call_llm=mock_call_llm)

        assert mock_call_llm.call_count >= 1

    @patch('brain.call_llm')
    def test_run_task_returns_final_response(self, mock_call_llm, controller_instance):
        """run_task() should return the final response."""
        from response import LLMResponse
        mock_call_llm.return_value = LLMResponse(text="Final answer from Bob")

        result = controller_instance.run_task("What is the answer?")

        assert result == "Final answer from Bob"


class TestToolEngineIntegration:
    """Tests for tool integration via IterationHandler."""

    @pytest.fixture
    def controller(self):
        with patch('controller.ProviderManager') as mock_pm_class:
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_provider.provider_type = "minimax"
            mock_provider.attributes = {}
            mock_pm_instance.get_provider.return_value = mock_provider

            from controller import HarnessController
            ctrl = HarnessController()
            return ctrl

    def test_tool_dispatch_function_exists(self, controller):
        """Tool dispatch should be available through IterationHandler."""
        from tool_dispatch import dispatch, dispatch_with_text_parsing
        assert callable(dispatch)
        assert callable(dispatch_with_text_parsing)

    def test_dispatch_returns_no_tool_found_for_plain_text(self, controller):
        """dispatch() should return NoToolFound for plain text responses."""
        from tool_dispatch import dispatch
        from response import LLMResponse, NoToolFound
        result = dispatch(LLMResponse(text="Plain text, no tool"))
        assert isinstance(result, NoToolFound)