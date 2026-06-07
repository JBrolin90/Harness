"""Unit tests for request_builder.py - HTTP request building for LLM API calls."""
import pytest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'llm'))

from llm.request_builder import RequestBuilder
from llm.provider import ProviderConfig, ProviderType


class TestFormatToolsForProvider:
    """Tests for _format_tools_for_provider tool formatting."""

    @pytest.fixture
    def config_minimax(self):
        """MiniMax provider config."""
        return ProviderConfig(
            name="cloud-pro",
            provider_type=ProviderType.MINIMAX,
            url="https://api.minimax.io/v1/text/chatcompletion_v2",
            model="MiniMax-M2.7",
            api_key_env_var="MINIMAX_API_KEY",
        )

    @pytest.fixture
    def config_ollama(self):
        """Ollama provider config."""
        return ProviderConfig(
            name="local-coder",
            provider_type=ProviderType.OLLAMA,
            url="http://lmde:11434/api/chat",
            model="qwen2.5-coder:7b-instruct-q8_0",
        )

    @pytest.fixture
    def config_openai(self):
        """OpenAI provider config."""
        return ProviderConfig(
            name="openai-test",
            provider_type=ProviderType.OPENAI,
            url="https://api.openai.com/v1/chat/completions",
            model="gpt-4",
            api_key_env_var="OPENAI_API_KEY",
        )

    def test_unwrapped_tools_get_wrapped_for_minimax(self, config_minimax):
        """Unwrapped tools should be wrapped for MiniMax provider."""
        builder = RequestBuilder(config_minimax)
        raw_tools = [
            {"name": "read_file", "description": "Read a file", "parameters": {}}
        ]
        formatted = builder._format_tools_for_provider(raw_tools)
        
        assert formatted is not None
        assert len(formatted) == 1
        assert "type" in formatted[0]
        assert formatted[0]["type"] == "function"
        assert "function" in formatted[0]
        assert formatted[0]["function"]["name"] == "read_file"

    def test_pre_wrapped_tools_pass_through_for_minimax(self, config_minimax):
        """Already wrapped tools should not be double-wrapped for MiniMax.
        
        This is the critical bug fix: controller wraps tools as
        {"type": "function", "function": {...}}, and brain.py should
        detect this and not wrap again (which caused Empty choices error).
        """
        builder = RequestBuilder(config_minimax)
        pre_wrapped_tools = [
            {"type": "function", "function": {"name": "read_file", "description": "Read a file", "parameters": {}}}
        ]
        formatted = builder._format_tools_for_provider(pre_wrapped_tools)
        
        # Should NOT double-wrap
        assert formatted is not None
        assert len(formatted) == 1
        assert "type" in formatted[0]
        assert "function" in formatted[0]
        # The function should be the raw tool, not wrapped again
        assert "name" in formatted[0]["function"]
        assert "description" in formatted[0]["function"]  # description is at function level, not tool level

    def test_ollama_tools_pass_through_unwrapped(self, config_ollama):
        """Ollama receives tools as-is (unwrapped)."""
        builder = RequestBuilder(config_ollama)
        raw_tools = [
            {"name": "read_file", "description": "Read a file", "parameters": {}}
        ]
        formatted = builder._format_tools_for_provider(raw_tools)
        
        assert formatted is not None
        assert formatted == raw_tools

    def test_openai_provider_uses_standard_format(self, config_openai):
        """OpenAI provider uses standard unwrapped format."""
        builder = RequestBuilder(config_openai)
        raw_tools = [
            {"name": "bash", "description": "Run command", "parameters": {}}
        ]
        formatted = builder._format_tools_for_provider(raw_tools)
        
        assert formatted is not None
        assert formatted == raw_tools

    def test_empty_tools_returns_none(self, config_minimax):
        """Empty tools list returns None."""
        builder = RequestBuilder(config_minimax)
        assert builder._format_tools_for_provider([]) is None

    def test_openrouter_provider_uses_standard_format(self):
        """OpenRouter provider uses standard format."""
        config = ProviderConfig(
            name="openrouter-test",
            provider_type=ProviderType.OPENROUTER,
            url="https://openrouter.ai/api/v1/chat/completions",
            model="deepseek-ai/deepseek-coder-6.7b-instruct",
            api_key_env_var="OPENROUTER_API_KEY",
        )
        builder = RequestBuilder(config)
        raw_tools = [
            {"name": "read_file", "description": "Read", "parameters": {}}
        ]
        formatted = builder._format_tools_for_provider(raw_tools)
        
        assert formatted is not None
        assert formatted == raw_tools