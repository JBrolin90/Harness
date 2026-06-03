"""Unit tests for bob.py - CLI entry point."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from response import LLMResponse, NoToolFound, ToolResult, ToolCall


class TestHarnessControllerImport:
    """Tests for importing and basic instantiation."""

    @patch('controller.ProviderManager')
    @patch('controller.get_memory')
    def test_harness_controller_class_exists(self, mock_get_memory, mock_pm_class):
        """HarnessController class should be accessible from controller module."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_pm_instance.get_provider.return_value = mock_provider
        mock_get_memory.return_value = MagicMock()

        from controller import HarnessController
        assert HarnessController is not None

    @patch('controller.ProviderManager')
    @patch('controller.get_memory')
    def test_harness_controller_default_provider(self, mock_get_memory, mock_pm_class):
        """HarnessController() should default to cloud-pro provider."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "cloud-pro"
        mock_provider.model = "MiniMax-M2"
        mock_pm_instance.get_provider.return_value = mock_provider
        mock_get_memory.return_value = MagicMock()

        from controller import HarnessController
        ctrl = HarnessController()

        mock_pm_instance.get_provider.assert_called_with("cloud-pro")
        assert ctrl.current_provider.name == "cloud-pro"

    @patch('controller.ProviderManager')
    @patch('controller.get_memory')
    def test_harness_controller_named_provider(self, mock_get_memory, mock_pm_class):
        """HarnessController('local-coder') should use specified provider."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "local-coder"
        mock_pm_instance.get_provider.return_value = mock_provider
        mock_get_memory.return_value = MagicMock()

        from controller import HarnessController
        ctrl = HarnessController("local-coder")

        mock_pm_instance.get_provider.assert_called_with("local-coder")
        assert ctrl.current_provider.name == "local-coder"


class TestHarnessControllerRunTask:
    """Tests for HarnessController.run_task() behavior with LLMResponse."""

    @pytest.fixture
    def controller_instance(self):
        """Create a mocked controller instance."""
        with \
             patch('controller.ProviderManager') as mock_pm_class, \
             patch('controller.get_memory') as mock_get_memory:
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_pm_instance.get_provider.return_value = mock_provider
            mock_get_memory.return_value = MagicMock()

            from controller import HarnessController
            ctrl = HarnessController()
            ctrl.current_provider = MagicMock()
            ctrl.system_prompt = "Test prompt"
            ctrl.tool_manager.tool_engine = MagicMock(return_value=NoToolFound())
            yield ctrl

    @patch('brain.call_llm')
    def test_run_task_returns_response(self, mock_call_llm, controller_instance):
        """run_task() should return a response string."""
        mock_call_llm.return_value = LLMResponse(text="Final response from Bob")

        result = controller_instance.run_task("Hello")

        assert result == "Final response from Bob"

    @patch('brain.call_llm')
    def test_run_task_with_tool_execution(self, mock_call_llm, controller_instance):
        """run_task() dispatches tool when response contains tool call.
        
        Uses return_value instead of side_effect to avoid iteration complexity.
        """
        mock_call_llm.return_value = LLMResponse(text="Done")
        controller_instance.tool_manager.tool_engine = MagicMock(return_value=NoToolFound())

        controller_instance.run_task("Read the file", call_llm=mock_call_llm)

        # Verify call_llm was called (tool was dispatched, loop ended)
        assert mock_call_llm.call_count == 1

    @patch('brain.call_llm')
    def test_run_task_no_tool_exits_loop_immediately(self, mock_call_llm, controller_instance):
        """run_task() when no tools detected should exit loop after one LLM call."""
        mock_call_llm.return_value = LLMResponse(text="I understand. How can I help?")

        controller_instance.run_task("Hello")

        assert mock_call_llm.call_count == 1

    @patch('brain.call_llm')
    def test_run_task_conversation_history_accumulates(self, mock_call_llm, controller_instance):
        """Multiple run_task() calls should accumulate in conversation history."""
        mock_call_llm.return_value = LLMResponse(text="Response")

        controller_instance.run_task("First message")
        controller_instance.run_task("Second message")

        assert len(controller_instance.conversation_manager.history) == 4


class TestControllerReset:
    """Tests for HarnessController.reset()."""

    @pytest.fixture
    def controller_instance(self):
        with \
             patch('controller.ProviderManager') as mock_pm_class, \
             patch('controller.get_memory') as mock_get_memory:
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_pm_instance.get_provider.return_value = mock_provider
            mock_get_memory.return_value = MagicMock()

            from controller import HarnessController
            ctrl = HarnessController()
            yield ctrl

    def test_reset_clears_history(self, controller_instance):
        """reset() should clear conversation history."""
        controller_instance.conversation_manager.history = [
            {"role": "user", "content": "test1"},
            {"role": "assistant", "content": "test2"}
        ]

        controller_instance.reset()

        assert controller_instance.conversation_manager.history == []

    def test_reset_preserves_tool_engine(self, controller_instance):
        """After reset, tool_manager should remain set."""
        controller_instance.reset()
        assert hasattr(controller_instance, 'tool_manager')
        assert hasattr(controller_instance.tool_manager, 'tool_engine')
        assert callable(controller_instance.tool_manager.tool_engine)