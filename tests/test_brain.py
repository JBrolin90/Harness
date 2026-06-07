"""Unit tests for brain.py - LLM request handler with native function calling."""
import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'llm'))

from llm.brain import _extract_text_content, _handle_response, consult_llm
from llm.response import LLMResponse, ToolCall
from llm.provider import ProviderType


class TestExtractTextContent:
    """Tests for _extract_text_content helper."""

    def test_none_message_returns_empty_string(self):
        """None message should return empty string."""
        assert _extract_text_content(None) == ""

    def test_empty_dict_returns_empty_string(self):
        """Empty dict should return empty string."""
        assert _extract_text_content({}) == ""

    def test_content_as_string(self):
        """Content as normal string."""
        assert _extract_text_content({"content": "Hello world"}) == "Hello world"

    def test_content_is_none(self):
        """Content key present but None should return empty string."""
        assert _extract_text_content({"content": None}) == ""


class TestHandleResponse:
    """Tests for unified _handle_response function."""

    def test_text_only_response_openai_style(self):
        """Simple text response with no tool call."""
        data = {
            "choices": [{
                "message": {
                    "content": "Hello, how can I help you?"
                }
            }]
        }
        result = _handle_response(data, ProviderType.OPENAI)
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
        result = _handle_response(data, ProviderType.OPENAI)
        assert isinstance(result, LLMResponse)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_file"
        assert result.tool_calls[0].arguments["path"] == "/etc/hosts"

    def test_missing_choices_key(self):
        """Missing choices key returns error response."""
        result = _handle_response({}, ProviderType.OPENAI)
        assert isinstance(result, LLMResponse)
        assert result.error is not None

    def test_empty_choices_array(self):
        """"Empty choices array returns empty response (graceful handling)."""
        result = _handle_response({"choices": []}, ProviderType.OPENAI)
        assert isinstance(result, LLMResponse)
        # Empty choices is treated as empty response, not an error
        assert result.text == ""
        assert result.tool_calls == []
        assert result.error is None

    def test_message_is_none(self):
        """choices[0].message is None returns error response."""
        result = _handle_response({"choices": [{"message": None}]}, ProviderType.OPENAI)
        assert isinstance(result, LLMResponse)
        assert result.error is not None

    def test_ollama_text_only_response(self):
        """Ollama text response."""
        data = {
            "message": {
                "role": "assistant",
                "content": "I'm here to help."
            }
        }
        result = _handle_response(data, ProviderType.OLLAMA)
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
        result = _handle_response(data, ProviderType.OLLAMA)
        assert isinstance(result, LLMResponse)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_file"

    def test_ollama_missing_message_key(self):
        """Missing message key returns error."""
        result = _handle_response({}, ProviderType.OLLAMA)
        assert isinstance(result, LLMResponse)
        assert result.error is not None

    def test_ollama_message_is_none(self):
        """message is None returns error."""
        result = _handle_response({"message": None}, ProviderType.OLLAMA)
        assert isinstance(result, LLMResponse)
        assert result.error is not None

    def test_ollama_content_is_none(self):
        """Content is None returns empty text."""
        result = _handle_response({"message": {"content": None}}, ProviderType.OLLAMA)
        assert isinstance(result, LLMResponse)
        assert result.text == ""


class TestCallLlm:
    """Integration tests for consult_llm."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock ProviderConfig."""
        provider = MagicMock()
        provider.name = "test-provider"
        provider.provider_type = ProviderType.OPENAI
        provider.url = "https://api.test.com/v1/chat/completions"
        provider.api_key_env_var = "TEST_API_KEY"
        provider.model = "gpt-4"
        provider.attributes = {}
        provider.tools = None
        return provider

    @patch('llm.brain.requests.post')
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

    @patch('llm.brain.requests.post')
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

    @patch('llm.brain.requests.post')
    def test_http_error_handling(self, mock_post, mock_provider):
        """HTTP errors are caught and returned as error response."""
        mock_post.side_effect = Exception("HTTP 401 Unauthorized")

        result = consult_llm([], "Hello", mock_provider)

        assert isinstance(result, LLMResponse)
        assert result.error is not None

    @patch('llm.brain.requests.post')
    @patch.dict(os.environ, {"TEST_API_KEY": "fake-key"})
    def test_ollama_provider(self, mock_post):
        """Ollama provider uses different response format."""
        ollama_provider = MagicMock()
        ollama_provider.name = "local-ollama"
        ollama_provider.provider_type = ProviderType.OLLAMA
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

    @patch('llm.brain.requests.post')
    @patch.dict(os.environ, {})
    def test_missing_api_key_warning(self, mock_post, mock_provider):
        """Missing API key triggers a warning but still tries the request."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "Response"}}]
        }

        result = consult_llm([], "Hello", mock_provider)

        assert isinstance(result, LLMResponse)
        assert result.text == "Response"

    @patch('llm.brain.requests.post')
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