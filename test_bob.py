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
    def test_harness_controller_class_exists(self, mock_pm_class):
        """HarnessController class should be accessible from controller module."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from controller import HarnessController
        assert HarnessController is not None

    @patch('controller.ProviderManager')
    def test_harness_controller_default_provider(self, mock_pm_class):
        """HarnessController() should default to cloud-pro provider."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "cloud-pro"
        mock_provider.model = "MiniMax-M2"
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from controller import HarnessController
        ctrl = HarnessController()

        mock_pm_instance.get_provider.assert_called_with("cloud-pro")
        assert ctrl.current_provider.name == "cloud-pro"

    @patch('controller.ProviderManager')
    def test_harness_controller_named_provider(self, mock_pm_class):
        """HarnessController('local-coder') should use specified provider."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "local-coder"
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
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
            yield ctrl

    @patch('iteration_handler.IterationHandler.execute')
    def test_run_task_returns_response(self, mock_execute, controller_instance):
        """run_task() should return a response string."""
        mock_execute.return_value = "Final response from Bob"

        result = controller_instance.run_task("Hello")

        assert result == "Final response from Bob"

    @patch('iteration_handler.IterationHandler.execute')
    def test_run_task_with_tool_execution(self, mock_execute, controller_instance):
        """run_task() dispatches tool when response contains tool call."""
        mock_execute.return_value = "Done"

        controller_instance.run_task("Read the file")

        mock_execute.assert_called_once()

    @patch('iteration_handler.IterationHandler.execute')
    def test_run_task_no_tool_exits_loop_immediately(self, mock_execute, controller_instance):
        """run_task() when no tools detected should exit after execute()."""
        mock_execute.return_value = "I understand. How can I help?"

        controller_instance.run_task("Hello")

        mock_execute.assert_called_once()


class TestControllerReset:
    """Tests for HarnessController.reset()."""

    @patch('controller.ProviderManager')
    def test_reset_is_noop(self, mock_pm_class):
        """reset() is no longer needed - IterationHandler manages conversation state."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from controller import HarnessController
        ctrl = HarnessController()
        
        # Should not raise
        ctrl.reset()