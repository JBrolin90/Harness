"""Unit tests for brain.py - LLM request handler."""
import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from brain import _parse_tool_call, _get_content, call_llm, _handle_openai_style_response, _handle_ollama_response


class TestParseToolCall:
    """Tests for _parse_tool_call helper."""

    def test_no_tool_calls_returns_none(self):
        """No tool_calls key should return None."""
        assert _parse_tool_call({}) is None
        assert _parse_tool_call({"content": "Hello"}) is None
        assert _parse_tool_call({"tool_calls": []}) is None
        assert _parse_tool_call({"tool_calls": None}) is None

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
        result = _parse_tool_call(message)
        parsed = json.loads(result)
        assert parsed == {"name": "read_file", "arguments": {"path": "/etc/hosts"}}

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
        result = _parse_tool_call(message)
        parsed = json.loads(result)
        assert parsed["name"] == "read_file"
        assert parsed["arguments"]["path"] == "/tmp/test.txt"

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
        result = _parse_tool_call(message)
        parsed = json.loads(result)
        assert parsed["arguments"] == {"query": "python", "limit": 5}

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
        result = _parse_tool_call(message)
        parsed = json.loads(result)
        assert parsed["name"] == "search"
        assert parsed["arguments"] == {"_raw": "not valid json {"}

    def test_missing_function_name(self):
        """Tool call without function name returns None."""
        message = {
            "tool_calls": [{
                "function": {
                    "arguments": {"path": "/tmp"}
                }
            }]
        }
        assert _parse_tool_call(message) is None

    def test_missing_function_container(self):
        """Tool call without function container returns None."""
        message = {
            "tool_calls": [{
                "name": "read_file"
            }]
        }
        assert _parse_tool_call(message) is None

    def test_extra_fields_ignored(self):
        """Extra fields in message are ignored."""
        message = {
            "content": "Some text",
            "tool_calls": [{
                "function": {
                    "name": "test",
                    "arguments": {}
                }
            }]
        }
        result = _parse_tool_call(message)
        assert json.loads(result)["name"] == "test"


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
        assert _handle_openai_style_response(data) == "Hello, how can I help you?"

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
        result = json.loads(_handle_openai_style_response(data))
        assert result["name"] == "read_file"
        assert result["arguments"]["path"] == "/etc/hosts"

    def test_minimax_tool_call_with_json_string(self):
        """MiniMax may return arguments as JSON string."""
        data = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "function": {
                            "name": "bash",
                            "arguments": '{"command": "ls -la"}'
                        }
                    }]
                }
            }]
        }
        result = json.loads(_handle_openai_style_response(data))
        assert result["name"] == "bash"
        assert result["arguments"] == {"command": "ls -la"}

    def test_missing_choices_key(self):
        """Missing choices key returns empty string."""
        result = _handle_openai_style_response({})
        assert result == "[BRAIN ERROR: Missing 'choices' in response]"

    def test_empty_choices_array(self):
        """Empty choices array returns empty string."""
        result = _handle_openai_style_response({"choices": []})
        assert result == "[BRAIN ERROR: Empty choices array]"

    def test_message_is_none(self):
        """choices[0].message is None returns empty string."""
        result = _handle_openai_style_response({"choices": [{"message": None}]})
        assert result == "[BRAIN ERROR: choices[0].message is None]"

    def test_message_key_missing(self):
        """choices[0] has no message key."""
        result = _handle_openai_style_response({"choices": [{}]})
        assert result == "[BRAIN ERROR: choices[0].message is None]"

    def test_content_is_none_with_no_tool_call(self):
        """Content is None but no tool_calls."""
        data = {
            "choices": [{
                "message": {
                    "content": None
                }
            }]
        }
        result = _handle_openai_style_response(data)
        assert result == ""


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
        assert _handle_ollama_response(data) == "I'm here to help."

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
        result = json.loads(_handle_ollama_response(data))
        assert result["name"] == "read_file"

    def test_missing_message_key(self):
        """Missing message key."""
        result = _handle_ollama_response({})
        assert result == "[BRAIN ERROR: Missing 'message' in Ollama response]"

    def test_message_is_none(self):
        """message is None."""
        result = _handle_ollama_response({"message": None})
        assert result == "[BRAIN ERROR: message is None in Ollama response]"

    def test_content_is_none(self):
        """Content is None."""
        result = _handle_ollama_response({"message": {"content": None}})
        assert result == ""


class TestCallLlm:
    """Integration tests for call_llm."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock ProviderConfig."""
        provider = MagicMock()
        provider.name = "test-provider"
        provider.provider_type = "openai"
        provider.url = "https://api.test.com/v1/chat/completions"
        provider.api_key_env_var = "TEST_API_KEY"
        provider.model = "gpt-4"
        provider.attributes = {"stream": False}
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

        result = call_llm([], "You are a helpful assistant.", mock_provider)

        assert result == "The capital of France is Paris."
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

        result = call_llm([], "Run whoami", mock_provider)
        parsed = json.loads(result)

        assert parsed["name"] == "bash"
        assert parsed["arguments"]["command"] == "whoami"

    @patch('brain.requests.post')
    def test_http_error_handling(self, mock_post, mock_provider):
        """HTTP errors are caught and returned as error string."""
        mock_post.return_value.status_code = 401
        mock_post.return_value.text = "Unauthorized"

        error_response = MagicMock()
        error_response.status_code = 401
        error_response.text = "Unauthorized"
        mock_post.return_value.raise_for_status.side_effect = Exception("HTTP 401")

        result = call_llm([], "Hello", mock_provider)

        assert "[BRAIN ERROR: HTTP" in result

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
        ollama_provider.attributes = {"stream": False}
        ollama_provider.tools = None

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "message": {
                "content": "Hello from Ollama"
            }
        }

        result = call_llm([], "Hello", ollama_provider)

        assert result == "Hello from Ollama"

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

        # Should complete without raising, just printing warning
        result = call_llm([], "Hello", mock_provider)

        assert result == "Response"
