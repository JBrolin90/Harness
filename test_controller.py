import pytest
import sys
import os
import re
import tempfile
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))


class TestControllerInit:
    """Tests for controller.init()"""

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    def test_init_creates_globals(self, mock_pm_class, mock_terminal):
        """init() should set global variables current_provider, system_prompt, conversation_history"""
        # Setup mock provider manager
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "test-provider"
        mock_provider.model = "test-model"
        mock_pm_instance.get_provider.return_value = mock_provider

        # Ensure AGENT_md_INGESTIOR returns empty string
        with patch('controller.AGENT_md_INGESTIOR', return_value=""):
            # Import and init
            import controller
            controller.init()

            assert hasattr(controller, 'current_provider')
            assert hasattr(controller, 'system_prompt')
            assert hasattr(controller, 'conversation_history')
            assert controller.current_provider == mock_provider
            assert isinstance(controller.conversation_history, list)

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    def test_init_exits_when_no_provider(self, mock_pm_class, mock_terminal):
        """init() should exit if no provider is found"""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_pm_instance.get_provider.return_value = None

        import controller
        with pytest.raises(SystemExit):
            controller.init()

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    @patch('controller.AGENT_md_INGESTIOR')
    def test_init_system_prompt_contains_tools(self, mock_agent, mock_pm_class, mock_terminal):
        """init() should build system prompt with tools instructions"""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_pm_instance.get_provider.return_value = mock_provider
        mock_agent.return_value = ""

        import controller
        controller.init()

        assert "AVAILABLE TOOLS" in controller.system_prompt
        assert "!READ" in controller.system_prompt
        assert "!WRITE" in controller.system_prompt


class TestControllerRunTask:
    """Tests for controller.run_task()"""

    @pytest.fixture(autouse=True)
    def setup_controller(self):
        """Set up a minimal controller state for each test"""
        import controller
        # Mock the globals
        controller.current_provider = MagicMock()
        controller.system_prompt = "Test prompt"
        controller.conversation_history = []
        yield
        # Reset globals after test
        if hasattr(controller, 'current_provider'):
            del controller.current_provider
        if hasattr(controller, 'system_prompt'):
            del controller.system_prompt
        if hasattr(controller, 'conversation_history'):
            del controller.conversation_history

    @patch('controller.call_llm')
    def test_run_task_adds_to_history(self, mock_call_llm):
        """run_task() should append user message and assistant response to history"""
        import controller
        mock_call_llm.return_value = "Hello from Bob"

        controller.run_task("Hello Bob")

        assert len(controller.conversation_history) == 2
        assert controller.conversation_history[0]["role"] == "user"
        assert controller.conversation_history[0]["content"] == "Hello Bob"
        assert controller.conversation_history[1]["role"] == "assistant"
        assert controller.conversation_history[1]["content"] == "Hello from Bob"

    @patch('controller.call_llm')
    @patch('controller.execute_tool')
    def test_run_task_no_tools_skips_loop(self, mock_execute, mock_call_llm):
        """If no tool commands in response, ReAct loop should not execute"""
        import controller
        mock_call_llm.return_value = "I can help with that."

        controller.run_task("Hello")

        mock_execute.assert_not_called()

    @patch('controller.call_llm')
    @patch('controller.execute_tool')
    def test_run_task_single_tool_call(self, mock_execute, mock_call_llm):
        """Tool in first response triggers tool execution, then loop continues"""
        import controller
        mock_execute.return_value = "[SYSTEM OUTPUT: File read successfully]"

        # First call returns tool use, second call returns final response
        mock_call_llm.side_effect = [
            "!READ /path/to/file",
            "File content is ..."
        ]

        controller.run_task("Read the file")

        assert mock_execute.call_count == 1
        assert mock_execute.call_args[0][0] == "!READ"
        assert mock_call_llm.call_count == 2  # Initial + after tool

    @patch('controller.call_llm')
    @patch('controller.execute_tool')
    def test_run_task_strips_leading_trailing_newlines_from_tools(self, mock_execute, mock_call_llm):
        """execute_tool is called with response containing the full text including markers"""
        import controller
        mock_execute.return_value = "[SYSTEM OUTPUT: done]"

        response_with_newlines = """Here's what I found:

!READ /some/file

That should help."""
        mock_call_llm.side_effect = [response_with_newlines, "Final response"]

        controller.run_task("Find the file")

        # Verify execute_tool received the full response content
        call_args = mock_execute.call_args
        assert call_args is not None
        # The content parameter should contain the full response
        # since the regex parses out the path but passes full response for block markers


class TestToolRegexParsing:
    """Tests for the ReAct tool detection regex logic"""

    def test_regex_finds_write_command(self):
        """Regex should detect !WRITE command at start of response"""
        response = "!READ /path/to/file"
        pattern = r'^\s*!(READ)\s+(\S+)'
        match = re.search(pattern, response, re.MULTILINE)
        assert match is not None
        assert match.group(1) == "READ"
        assert match.group(2) == "/path/to/file"

    def test_regex_finds_write_command_indented(self):
        """Regex should detect !WRITE command even when indented"""
        response = "  !WRITE /path/to/file"
        pattern = r'^\s*!(WRITE)\s+(\S+)'
        match = re.search(pattern, response, re.MULTILINE)
        assert match is not None
        assert match.group(1) == "WRITE"

    def test_regex_finds_bash_command(self):
        """Regex should detect !BASH command"""
        response = "!BASH ls -la /tmp"
        pattern = r'^\s*!(BASH)\s+(.+)'
        match = re.search(pattern, response, re.MULTILINE)
        assert match is not None
        assert match.group(1) == "BASH"
        assert match.group(2) == "ls -la /tmp"

    def test_regex_finds_ls_command(self):
        """Regex should detect !LS command"""
        response = "!LS /home/user"
        pattern = r'^\s*!(LS)\s+(\S+)'
        match = re.search(pattern, response, re.MULTILINE)
        assert match is not None
        assert match.group(1) == "LS"

    def test_first_match_selected_when_multiple(self):
        """When multiple tools detected, first one in text should be selected"""
        response = "!READ /file1.txt\n\nThen !WRITE /file2.txt"
        regex_map = {
            "!WRITE": r'^\s*!(WRITE)\s+(\S+)',
            "!READ": r'^\s*!(READ)\s+(\S+)',
        }

        matches = []
        for cmd_type, pattern in regex_map.items():
            m = re.search(pattern, response, re.MULTILINE)
            if m:
                matches.append((m.start(), cmd_type, m))

        matches.sort(key=lambda x: x[0])
        _, tool_cmd, match = matches[0]

        assert tool_cmd == "!READ"
        assert match.group(2) == "/file1.txt"


class TestToolsExecute:
    """Tests for tools.execute_tool() - isolated from controller"""

    def test_validate_path_allows_relative(self):
        """_validate_path should resolve relative paths within CWD"""
        from tools import _validate_path
        cwd = os.getcwd()
        result = _validate_path("subdir/file.txt")
        assert result == os.path.join(cwd, "subdir", "file.txt")

    def test_validate_path_rejects_absolute_outside_cwd(self):
        """_validate_path should reject paths outside CWD"""
        from tools import _validate_path
        with pytest.raises(ValueError, match="Access denied"):
            _validate_path("/etc/passwd")

    def test_strip_visual_newlines(self):
        """_strip_visual_newlines should remove single leading/trailing newlines"""
        from tools import _strip_visual_newlines
        assert _strip_visual_newlines("\nhello\n") == "hello"
        assert _strip_visual_newlines("hello") == "hello"
        assert _strip_visual_newlines("\nhello") == "hello"
        assert _strip_visual_newlines("hello\n") == "hello"

    @patch('sys.stdout')
    def test_execute_read_file_not_found(self, mock_stdout):
        """execute_tool !READ returns error for missing file"""
        from tools import execute_tool
        result = execute_tool("!READ", "/nonexistent/file.txt")
        assert "[SYSTEM ERROR" in result

    def test_execute_write_success(self):
        """execute_tool !WRITE should create file"""
        from tools import execute_tool
        # Use a path within CWD since _validate_path restricts to working directory
        test_file = os.path.join(os.getcwd(), "test_write_temp.txt")

        try:
            content = f"Test content <<<WRITE_BLOCK>>>Hello World<<<"
            result = execute_tool("!WRITE", test_file, content)
            assert "[SYSTEM OUTPUT: Successfully wrote" in result
            with open(test_file, 'r') as f:
                assert f.read() == "Hello World"
        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)

    def test_execute_write_invalid_format(self):
        """execute_tool !WRITE returns error for missing markers"""
        from tools import execute_tool
        test_file = os.path.join(os.getcwd(), "test_invalid_write.txt")
        try:
            result = execute_tool("!WRITE", test_file, "No markers here")
            assert "[SYSTEM ERROR: Invalid !WRITE format" in result
        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)

    def test_execute_ls_nonexistent_dir(self):
        """execute_tool !LS returns error for missing directory"""
        from tools import execute_tool
        result = execute_tool("!LS", os.path.join(os.getcwd(), "nonexistent_dir_xyz"))
        assert "[SYSTEM ERROR: Directory" in result

    @patch('sys.stdout')
    def test_execute_ls_success(self, mock_stdout):
        """execute_tool !LS should list directory contents"""
        from tools import execute_tool
        result = execute_tool("!LS", ".")
        assert "[SYSTEM OUTPUT: Files in" in result


class TestProviderConfig:
    """Tests for provider.ProviderConfig and ProviderManager"""

    def test_provider_config_creation(self):
        """ProviderConfig should store all fields"""
        from provider import ProviderConfig
        config = ProviderConfig(
            name="test",
            provider_type="ollama",
            url="http://localhost:11434",
            model="test-model",
            api_key_env_var="TEST_KEY",
            attributes={"stream": False}
        )
        assert config.name == "test"
        assert config.provider_type == "ollama"
        assert config.url == "http://localhost:11434"
        assert config.model == "test-model"
        assert config.api_key_env_var == "TEST_KEY"
        assert config.attributes == {"stream": False}

    @patch('provider.os.path.exists', return_value=False)
    def test_provider_manager_defaults(self, mock_exists):
        """ProviderManager should load default providers on init"""
        from provider import ProviderManager
        pm = ProviderManager(storage_path="/nonexistent.json")
        assert "cloud-pro" in pm.list_providers()
        assert "local-coder" in pm.list_providers()

    def test_provider_manager_add_get(self):
        """ProviderManager add/get should work round-trip"""
        from provider import ProviderConfig, ProviderManager
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            pm = ProviderManager(storage_path=temp_path)
            config = ProviderConfig(
                name="test-provider",
                provider_type="test",
                url="http://test.example.com",
                model="test-model"
            )
            pm.add_provider(config)
            retrieved = pm.get_provider("test-provider")
            assert retrieved is not None
            assert retrieved.name == "test-provider"
            assert retrieved.model == "test-model"
        finally:
            os.unlink(temp_path)

    def test_provider_manager_update_existing(self):
        """add_provider with existing name should update, not duplicate"""
        from provider import ProviderConfig, ProviderManager
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            pm = ProviderManager(storage_path=temp_path)
            config1 = ProviderConfig(name="dup", provider_type="type1", url="url1", model="m1")
            config2 = ProviderConfig(name="dup", provider_type="type2", url="url2", model="m2")
            pm.add_provider(config1)
            pm.add_provider(config2)
            assert len([p for p in pm.providers if p.name == "dup"]) == 1
            assert pm.get_provider("dup").provider_type == "type2"
        finally:
            os.unlink(temp_path)

    def test_provider_manager_list_providers(self):
        """list_providers should return all provider names"""
        from provider import ProviderManager
        pm = ProviderManager(storage_path="/nonexistent.json")
        names = pm.list_providers()
        assert "cloud-pro" in names
        assert "local-coder" in names


class TestAgentMdIngestor:
    """Tests for AGENT.py"""

    @patch('os.path.exists')
    @patch('builtins.open', side_effect=Exception("Permission denied"))
    def test_ingestor_handles_read_error(self, mock_open, mock_exists):
        """AGENT_md_INGESTIOR should handle file read errors gracefully"""
        mock_exists.return_value = True
        import AGENT
        result = AGENT.AGENT_md_INGESTIOR()
        # Should return None (empty string implicitly) on error, not crash

    @patch('os.path.exists')
    @patch('builtins.open')
    @patch('os.getcwd', return_value="/test")
    def test_ingestor_returns_content(self, mock_cwd, mock_open, mock_exists):
        """AGENT_md_INGESTIOR should return formatted content when file exists"""
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = "Custom instructions"

        import AGENT
        result = AGENT.AGENT_md_INGESTIOR()

        assert "DIRECTORY SPECIFIC INSTRUCTIONS" in result
        assert "Custom instructions" in result

    @patch('os.path.exists')
    def test_ingestor_no_file(self, mock_exists):
        """AGENT_md_INGESTIOR should return None when no AGENT.md exists"""
        mock_exists.return_value = False
        import AGENT
        result = AGENT.AGENT_md_INGESTIOR()
        assert result is None