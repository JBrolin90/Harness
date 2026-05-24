"""Unit tests for bob.py - CLI entry point."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


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
    """Tests for HarnessController.run_task() behavior."""

    @pytest.fixture
    def controller_instance(self):
        """Create a mocked controller instance."""
        with patch('controller.terminal_history_upgrade'), \
             patch('controller.ProviderManager') as mock_pm_class, \
             patch('controller.AGENT_md_INGESTIOR', return_value=""):
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_pm_instance.get_provider.return_value = mock_provider

            from controller import HarnessController
            ctrl = HarnessController(enable_context=False)
            ctrl.current_provider = MagicMock()
            ctrl.system_prompt = "Test prompt"
            ctrl.conversation_history = []
            yield ctrl

    @patch('controller.call_llm')
    def test_run_task_returns_response_string(self, mock_call_llm, controller_instance):
        """run_task() should return the final response as a string."""
        mock_call_llm.return_value = "Final response from Bob"

        result = controller_instance.run_task("Hello")

        assert isinstance(result, str)
        assert result == "Final response from Bob"

    @patch('controller.call_llm')
    def test_run_task_with_tool_execution(self, mock_call_llm, controller_instance):
        """run_task() with tool call should execute tool and continue loop."""
        mock_call_llm.side_effect = [
            "!READ /path/to/file",
            "File content is ready"
        ]

        with patch('controller.execute_tool') as mock_execute:
            mock_execute.return_value = "[SYSTEM OUTPUT: File content]"

            result = controller_instance.run_task("Read the file")

            assert mock_execute.called
            assert result == "File content is ready"

    @patch('controller.call_llm')
    def test_run_task_no_tool_exits_loop_immediately(self, mock_call_llm, controller_instance):
        """run_task() when no tools detected should exit loop after one LLM call."""
        mock_call_llm.return_value = "I understand. How can I help?"

        result = controller_instance.run_task("Hello")

        assert mock_call_llm.call_count == 1
        assert result == "I understand. How can I help?"

    @patch('controller.call_llm')
    def test_run_task_conversation_history_accumulates(self, mock_call_llm, controller_instance):
        """Multiple run_task() calls should accumulate in conversation_history."""
        mock_call_llm.return_value = "Response"

        controller_instance.run_task("First message")
        controller_instance.run_task("Second message")

        # Each run_task adds 2 messages (user + assistant)
        assert len(controller_instance.conversation_history) == 4


class TestModuleLevelCompatibility:
    """Tests for backward-compatible module-level init() and run_task()."""

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    @patch('controller.AGENT_md_INGESTIOR')
    def test_init_creates_global_controller(self, mock_agent, mock_pm_class, mock_terminal):
        """module init() should create a global _controller instance."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_pm_instance.get_provider.return_value = mock_provider
        mock_agent.return_value = ""

        # Force fresh import
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
             patch('controller.ProviderManager') as mock_pm_class, \
             patch('controller.AGENT_md_INGESTIOR', return_value=""):
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

    def test_reset_allows_fresh_conversation(self, controller_instance):
        """After reset, run_task should start clean."""
        controller_instance.conversation_history = [{"role": "user", "content": "old"}]

        with patch('controller.call_llm') as mock_llm:
            mock_llm.return_value = "Fresh response"
            controller_instance.reset()
            controller_instance.run_task("New prompt")

            # History should have only the new exchange
            assert len(controller_instance.conversation_history) == 2
            assert controller_instance.conversation_history[0]["content"] == "New prompt"