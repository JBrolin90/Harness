"""Unit tests for brain.py - LLM request handler with native function calling."""
import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from brain import _parse_tool_calls, _get_content, consult_llm, _handle_openai_style_response, _handle_ollama_response
from response import LLMResponse, ToolCall


class TestParseToolCalls:
    """Tests for _parse_tool_calls helper."""

    def test_no_tool_calls_returns_empty_list(self):
        """No tool_calls key should return empty list."""
        assert _parse_tool_calls({}) == []
        assert _parse_tool_calls({"content": "Hello"}) == []
        assert _parse_tool_calls({"tool_calls": []}) == []
        assert _parse_tool_calls({"tool_calls": None}) == []

    def test_valid_openai_style_tool_call(self):
        """OpenAI style tool_call with dict arguments."""
        message = {
            "tool_calls": [{
                "function": {
                    "name": "read_file",
                    "arguments": {"path": "/etc/hosts"}
                }
            }]
        }
        result = _parse_tool_calls(message)
        assert len(result) == 1
        assert result[0].name == "read_file"
        assert result[0].arguments == {"path": "/etc/hosts"}

    def test_valid_ollama_style_tool_call(self):
        """Ollama style tool_call with nested structure."""
        message = {
            "tool_calls": [{
                "id": "call_123",
                "function": {
                    "name": "read_file",
                    "arguments": {"path": "/tmp/test.txt"}
                }
            }]
        }
        result = _parse_tool_calls(message)
        assert len(result) == 1
        assert result[0].name == "read_file"
        assert result[0].arguments["path"] == "/tmp/test.txt"

    def test_arguments_as_json_string(self):
        """Arguments may come as a JSON string that needs parsing."""
        message = {
            "tool_calls": [{
                "function": {
                    "name": "search",
                    "arguments": '{"query": "python", "limit": 5}'
                }
            }]
        }
        result = _parse_tool_calls(message)
        assert len(result) == 1
        assert result[0].arguments == {"query": "python", "limit": 5}

    def test_arguments_as_malformed_json_string(self):
        """Malformed JSON in arguments is handled gracefully."""
        message = {
            "tool_calls": [{
                "function": {
                    "name": "search",
                    "arguments": "not valid json {"
                }
            }]
        }
        result = _parse_tool_calls(message)
        assert len(result) == 1
        assert result[0].name == "search"
        assert result[0].arguments == {"_raw": "not valid json {"}

    def test_missing_function_name(self):
        """Tool call without function name is skipped."""
        message = {
            "tool_calls": [{
                "function": {
                    "arguments": {"path": "/tmp"}
                }
            }]
        }
        result = _parse_tool_calls(message)
        assert result == []

    def test_multiple_tool_calls(self):
        """Multiple tool calls are all extracted."""
        message = {
            "tool_calls": [
                {"function": {"name": "read_file", "arguments": {"path": "/tmp/a"}}},
                {"function": {"name": "bash", "arguments": {"command": "ls"}}}
            ]
        }
        result = _parse_tool_calls(message)
        assert len(result) == 2
        assert result[0].name == "read_file"
        assert result[1].name == "bash"


class TestGetContent:
    """Tests for _get_content helper."""

    def test_none_message_returns_empty_string(self):
        """None message should return empty string."""
        assert _get_content(None) == ""

    def test_empty_dict_returns_empty_string(self):
        """Empty dict should return empty string."""
        assert _get_content({}) == ""

    def test_content_as_string(self):
        """Content as normal string."""
        assert _get_content({"content": "Hello world"}) == "Hello world"

    def test_content_is_none(self):
        """Content key present but None should return empty string."""
        assert _get_content({"content": None}) == ""


class TestHandleOpenaiStyleResponse:
    """Tests for _handle_openai_style_response."""

    def test_text_only_response(self):
        """Simple text response with no tool call."""
        data = {
            "choices": [{
                "message": {
                    "content": "Hello, how can I help you?"
                }
            }]
        }
        result = _handle_openai_style_response(data)
        assert isinstance(result, LLMResponse)
        assert result.text == "Hello, how can I help you?"
        assert result.tool_calls == []
        assert result.error is None

    def test_openai_tool_call(self):
        """OpenAI style tool call."""
        data = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "function": {
                            "name": "read_file",
                            "arguments": {"path": "/etc/hosts"}
                        }
                    }]
                }
            }]
        }
        result = _handle_openai_style_response(data)
        assert isinstance(result, LLMResponse)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_file"
        assert result.tool_calls[0].arguments["path"] == "/etc/hosts"

    def test_missing_choices_key(self):
        """Missing choices key returns error response."""
        result = _handle_openai_style_response({})
        assert isinstance(result, LLMResponse)
        assert result.error is not None

    def test_empty_choices_array(self):
        """Empty choices array returns error response."""
        result = _handle_openai_style_response({"choices": []})
        assert isinstance(result, LLMResponse)
        assert result.error is not None

    def test_message_is_none(self):
        """choices[0].message is None returns error response."""
        result = _handle_openai_style_response({"choices": [{"message": None}]})
        assert isinstance(result, LLMResponse)
        assert result.error is not None


class TestHandleOllamaResponse:
    """Tests for _handle_ollama_response."""

    def test_text_only_response(self):
        """Ollama text response."""
        data = {
            "message": {
                "role": "assistant",
                "content": "I'm here to help."
            }
        }
        result = _handle_ollama_response(data)
        assert isinstance(result, LLMResponse)
        assert result.text == "I'm here to help."

    def test_ollama_tool_call(self):
        """Ollama tool call."""
        data = {
            "message": {
                "role": "assistant",
                "content": "Let me check that.",
                "tool_calls": [{
                    "function": {
                        "name": "read_file",
                        "arguments": {"path": "/tmp/data.txt"}
                    }
                }]
            }
        }
        result = _handle_ollama_response(data)
        assert isinstance(result, LLMResponse)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_file"

    def test_missing_message_key(self):
        """Missing message key returns error."""
        result = _handle_ollama_response({})
        assert isinstance(result, LLMResponse)
        assert result.error is not None

    def test_message_is_none(self):
        """message is None returns error."""
        result = _handle_ollama_response({"message": None})
        assert isinstance(result, LLMResponse)
        assert result.error is not None

    def test_content_is_none(self):
        """Content is None returns empty text."""
        result = _handle_ollama_response({"message": {"content": None}})
        assert isinstance(result, LLMResponse)
        assert result.text == ""


class TestCallLlm:
    """Integration tests for consult_llm."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock ProviderConfig."""
        provider = MagicMock()
        provider.name = "test-provider"
        provider.provider_type = "openai"
        provider.url = "https://api.test.com/v1/chat/completions"
        provider.api_key_env_var = "TEST_API_KEY"
        provider.model = "gpt-4"
        provider.attributes = {}
        provider.tools = None
        return provider

    @patch('brain.requests.post')
    def test_successful_text_response(self, mock_post, mock_provider):
        """Successful response with text content."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{
                "message": {
                    "content": "The capital of France is Paris."
                }
            }]
        }

        result = consult_llm([], "You are a helpful assistant.", mock_provider)

        assert isinstance(result, LLMResponse)
        assert result.text == "The capital of France is Paris."
        mock_post.assert_called_once()

    @patch('brain.requests.post')
    def test_successful_tool_call_response(self, mock_post, mock_provider):
        """Successful response with tool call."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "function": {
                            "name": "bash",
                            "arguments": {"command": "whoami"}
                        }
                    }]
                }
            }]
        }

        result = consult_llm([], "Run whoami", mock_provider)

        assert isinstance(result, LLMResponse)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "bash"
        assert result.tool_calls[0].arguments["command"] == "whoami"

    @patch('brain.requests.post')
    def test_http_error_handling(self, mock_post, mock_provider):
        """HTTP errors are caught and returned as error response."""
        mock_post.side_effect = Exception("HTTP 401 Unauthorized")

        result = consult_llm([], "Hello", mock_provider)

        assert isinstance(result, LLMResponse)
        assert result.error is not None

    @patch('brain.requests.post')
    @patch.dict(os.environ, {"TEST_API_KEY": "fake-key"})
    def test_ollama_provider(self, mock_post):
        """Ollama provider uses different response format."""
        ollama_provider = MagicMock()
        ollama_provider.name = "local-ollama"
        ollama_provider.provider_type = "ollama"
        ollama_provider.url = "http://localhost:11434/api/chat"
        ollama_provider.api_key_env_var = ""
        ollama_provider.model = "llama3"
        ollama_provider.attributes = {}
        ollama_provider.tools = None

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "message": {
                "content": "Hello from Ollama"
            }
        }

        result = consult_llm([], "Hello", ollama_provider)

        assert isinstance(result, LLMResponse)
        assert result.text == "Hello from Ollama"

    @patch('brain.requests.post')
    @patch.dict(os.environ, {})
    def test_missing_api_key_warning(self, mock_post, mock_provider):
        """Missing API key triggers a warning but still tries the request."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{
                "message": {"content": "Response"}
            }]
        }

        result = consult_llm([], "Hello", mock_provider)

        assert isinstance(result, LLMResponse)
        assert result.text == "Response"

    @patch('brain.requests.post')
    def test_tools_are_sent_in_payload(self, mock_post, mock_provider):
        """Tools are included in the request payload."""
        mock_provider.tools = [
            {"type": "function", "function": {"name": "bash", "description": "Run command", "parameters": {}}}
        ]
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "Done"}}]
        }

        consult_llm([], "Run bash", mock_provider)

        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert "tools" in payload
        assert payload["tools"][0]["function"]["name"] == "bash"


class TestFormatToolsForProvider:
    """Tests for _format_tools_for_provider tool formatting."""

    def test_unwrapped_tools_get_wrapped_for_minimax(self):
        """Unwrapped tools should be wrapped for MiniMax provider."""
        from brain import _format_tools_for_provider
        
        raw_tools = [
            {"name": "read_file", "description": "Read a file", "parameters": {}}
        ]
        formatted = _format_tools_for_provider(raw_tools, "minimax")
        
        assert formatted is not None
        assert len(formatted) == 1
        assert "type" in formatted[0]
        assert formatted[0]["type"] == "function"
        assert "function" in formatted[0]
        assert formatted[0]["function"]["name"] == "read_file"

    def test_pre_wrapped_tools_pass_through_for_minimax(self):
        """Already wrapped tools should not be double-wrapped for MiniMax.
        
        This is the critical bug fix: controller wraps tools as
        {"type": "function", "function": {...}}, and brain.py should
        detect this and not wrap again (which caused Empty choices error).
        """
        from brain import _format_tools_for_provider
        
        pre_wrapped_tools = [
            {"type": "function", "function": {"name": "read_file", "description": "Read a file", "parameters": {}}}
        ]
        formatted = _format_tools_for_provider(pre_wrapped_tools, "minimax")
        
        # Should NOT double-wrap
        assert formatted is not None
        assert len(formatted) == 1
        assert "type" in formatted[0]
        assert "function" in formatted[0]
        # The function should be the raw tool, not wrapped again
        assert "name" in formatted[0]["function"]
        assert "description" in formatted[0]["function"]  # description is at function level, not tool level

    def test_ollama_tools_pass_through_unwrapped(self):
        """Ollama receives tools as-is (unwrapped)."""
        from brain import _format_tools_for_provider
        
        raw_tools = [
            {"name": "read_file", "description": "Read a file", "parameters": {}}
        ]
        formatted = _format_tools_for_provider(raw_tools, "ollama")
        
        assert formatted is not None
        assert formatted == raw_tools

    def test_openai_provider_uses_standard_format(self):
        """OpenAI provider uses standard unwrapped format."""
        from brain import _format_tools_for_provider
        
        raw_tools = [
            {"name": "bash", "description": "Run command", "parameters": {}}
        ]
        formatted = _format_tools_for_provider(raw_tools, "openai")
        
        assert formatted is not None
        assert formatted == raw_tools

    def test_empty_tools_returns_none(self):
        """Empty tools list returns None."""
        from brain import _format_tools_for_provider
        
        assert _format_tools_for_provider([], "minimax") is None
        assert _format_tools_for_provider(None, "minimax") is None

    def test_openrouter_provider_uses_standard_format(self):
        """OpenRouter provider uses standard format."""
        from brain import _format_tools_for_provider
        
        raw_tools = [
            {"name": "read_file", "description": "Read", "parameters": {}}
        ]
        formatted = _format_tools_for_provider(raw_tools, "openrouter")
        
        assert formatted is not None
        assert formatted == raw_tools