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
        assert hasattr(ctrl, 'system_prompt_manager')

    @patch('controller.ProviderManager')
    def test_init_creates_system_prompt_manager(self, mock_pm_class):
        """__init__() should create SystemPromptManager."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from controller import HarnessController
        ctrl = HarnessController()

        assert hasattr(ctrl, 'system_prompt_manager')
        assert hasattr(ctrl.system_prompt_manager, 'get_system_prompt')


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
            yield ctrl

    @patch('iteration_handler.IterationHandler.execute')
    def test_run_task_returns_execute_result(self, mock_execute, controller_instance):
        """run_task() should return the result from IterationHandler.execute()."""
        from response import LLMResponse
        mock_execute.return_value = "Final answer"

        result = controller_instance.run_task("Hello Bob")

        assert result == "Final answer"
        mock_execute.assert_called_once()

    @patch('iteration_handler.IterationHandler.execute')
    def test_run_task_passes_parameters_to_execute(self, mock_execute, controller_instance):
        """run_task() should pass prompt and system_prompt to execute."""
        mock_execute.return_value = "Done"
        controller_instance.system_prompt_manager.get_system_prompt = MagicMock(return_value="System prompt")

        controller_instance.run_task("User prompt")

        call_kwargs = mock_execute.call_args.kwargs
        assert 'prompt' in call_kwargs
        assert 'system_prompt' in call_kwargs
        assert 'call_llm' in call_kwargs

    @patch('iteration_handler.IterationHandler.execute')
    def test_run_task_with_custom_call_llm(self, mock_execute, controller_instance):
        """run_task() should pass custom call_llm to execute."""
        mock_execute.return_value = "Done"
        controller_instance.system_prompt_manager.get_system_prompt = MagicMock(return_value="System prompt")
        custom_call_llm = MagicMock()

        controller_instance.run_task("Hello", call_llm=custom_call_llm)

        call_kwargs = mock_execute.call_args.kwargs
        assert call_kwargs['call_llm'] is custom_call_llm

    @patch('iteration_handler.IterationHandler.execute')
    def test_run_task_with_max_iterations(self, mock_execute, controller_instance):
        """run_task() should pass max_iterations to IterationHandler constructor."""
        mock_execute.return_value = "Done"
        controller_instance.system_prompt_manager.get_system_prompt = MagicMock(return_value="System prompt")

        with patch('controller.IterationHandler') as mock_handler_class:
            mock_handler_instance = MagicMock()
            mock_handler_instance.execute.return_value = "Done"
            mock_handler_class.return_value = mock_handler_instance

            controller_instance.run_task("Hello", max_iterations=10)

            mock_handler_class.assert_called_with(controller_instance.current_provider, 10)