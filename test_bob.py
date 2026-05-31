"""Unit tests for bob.py - CLI entry point."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from response import LLMResponse, NoToolFound, ToolResult, ToolCall


class TestHarnessControllerImport:
    """Tests for importing and basic instantiation."""

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    def test_harness_controller_class_exists(self, mock_pm_class, mock_terminal):
        """HarnessController class should be accessible from controller module."""
        from controller import HarnessController
        assert HarnessController is not None

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    def test_harness_controller_default_provider(self, mock_pm_class, mock_terminal):
        """HarnessController() should default to cloud-pro provider."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "cloud-pro"
        mock_provider.model = "MiniMax-M2"
        mock_pm_instance.get_provider.return_value = mock_provider

        from controller import HarnessController
        ctrl = HarnessController()

        mock_pm_instance.get_provider.assert_called_with("cloud-pro")
        assert ctrl.current_provider.name == "cloud-pro"

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    def test_harness_controller_named_provider(self, mock_pm_class, mock_terminal):
        """HarnessController('local-coder') should use specified provider."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "local-coder"
        mock_pm_instance.get_provider.return_value = mock_provider

        from controller import HarnessController
        ctrl = HarnessController("local-coder")

        mock_pm_instance.get_provider.assert_called_with("local-coder")
        assert ctrl.current_provider.name == "local-coder"


class TestHarnessControllerRunTask:
    """Tests for HarnessController.run_task() behavior with LLMResponse."""

    @pytest.fixture
    def controller_instance(self):
        """Create a mocked controller instance."""
        with patch('controller.terminal_history_upgrade'), \
             patch('controller.ProviderManager') as mock_pm_class:
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_pm_instance.get_provider.return_value = mock_provider

            from controller import HarnessController
            ctrl = HarnessController()
            ctrl.current_provider = MagicMock()
            ctrl.system_prompt = "Test prompt"
            ctrl.conversation_history = []
            ctrl.tool_engine = MagicMock(return_value=NoToolFound())
            yield ctrl

    @patch('controller.call_llm')
    def test_run_task_returns_response(self, mock_call_llm, controller_instance):
        """run_task() should return a response (string or LLMResponse)."""
        mock_call_llm.return_value = LLMResponse(text="Final response from Bob")

        result = controller_instance.run_task("Hello")

        # Result could be string or LLMResponse object
        if isinstance(result, LLMResponse):
            assert result.text == "Final response from Bob"
        else:
            assert result == "Final response from Bob"

    @patch('controller.call_llm')
    def test_run_task_with_tool_execution(self, mock_call_llm, controller_instance):
        """run_task() with tool call should execute tool and continue loop."""
        mock_call_llm.side_effect = [
            LLMResponse(tool_calls=[ToolCall(name="read_file", arguments={"path": "/path/to/file"})]),
            LLMResponse(text="Final response after tool")
        ]
        controller_instance.tool_engine.side_effect = [
            ToolResult(tool_name="read_file", output="[SYSTEM OUTPUT: File content]"),
            NoToolFound()
        ]

        result = controller_instance.run_task("Read the file")

        assert controller_instance.tool_engine.call_count == 2

    @patch('controller.call_llm')
    def test_run_task_no_tool_exits_loop_immediately(self, mock_call_llm, controller_instance):
        """run_task() when no tools detected should exit loop after one LLM call."""
        mock_call_llm.return_value = LLMResponse(text="I understand. How can I help?")

        result = controller_instance.run_task("Hello")

        assert mock_call_llm.call_count == 1

    @patch('controller.call_llm')
    def test_run_task_conversation_history_accumulates(self, mock_call_llm, controller_instance):
        """Multiple run_task() calls should accumulate in conversation_history."""
        mock_call_llm.return_value = LLMResponse(text="Response")

        controller_instance.run_task("First message")
        controller_instance.run_task("Second message")

        assert len(controller_instance.conversation_history) == 4


class TestModuleLevelCompatibility:
    """Tests for backward-compatible module-level init() and run_task()."""

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    def test_init_creates_global_controller(self, mock_pm_class, mock_terminal):
        """module init() should create a global _controller instance."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_pm_instance.get_provider.return_value = mock_provider

        import importlib
        import controller
        importlib.reload(controller)

        controller.init()

        assert controller._controller is not None
        from controller import HarnessController
        assert isinstance(controller._controller, HarnessController)

    def test_module_level_init_exists(self):
        """module init() function should exist."""
        from controller import init
        assert callable(init)

    def test_module_level_run_task_exists(self):
        """module run_task() function should exist."""
        from controller import run_task
        assert callable(run_task)


class TestControllerReset:
    """Tests for HarnessController.reset()."""

    @pytest.fixture
    def controller_instance(self):
        with patch('controller.terminal_history_upgrade'), \
             patch('controller.ProviderManager') as mock_pm_class:
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_pm_instance.get_provider.return_value = mock_provider

            from controller import HarnessController
            ctrl = HarnessController()
            yield ctrl

    def test_reset_clears_history(self, controller_instance):
        """reset() should clear conversation_history."""
        controller_instance.conversation_history = [
            {"role": "user", "content": "test1"},
            {"role": "assistant", "content": "test2"}
        ]

        controller_instance.reset()

        assert controller_instance.conversation_history == []

    def test_reset_clears_tool_engine(self, controller_instance):
        """After reset, tool_engine should remain set."""
        controller_instance.reset()
        assert hasattr(controller_instance, 'tool_engine')
        assert callable(controller_instance.tool_engine)