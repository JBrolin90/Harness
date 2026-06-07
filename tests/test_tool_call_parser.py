"""Unit tests for tool_call_parser.py - tool call parsing for different LLM provider formats."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'llm'))

from llm.tool_call_parser import (
    MultiFormatParser,
    OpenAIStyleParser,
    TopLevelFunctionCallParser,
    OllamaParser,
    get_parser,
    parse_arguments,
)
from llm.provider import ProviderType
from llm.response import ToolCall


class TestParseArguments:
    """Tests for parse_arguments helper."""

    def test_dict_returns_as_is(self):
        """Dict argument returns unchanged."""
        args = {"path": "/etc/hosts", "line_count": 10}
        assert parse_arguments(args) == args

    def test_valid_json_string(self):
        """Valid JSON string is parsed."""
        args = '{"path": "/etc/hosts", "line_count": 10}'
        result = parse_arguments(args)
        assert result == {"path": "/etc/hosts", "line_count": 10}

    def test_malformed_json_string(self):
        """Malformed JSON returns _raw key."""
        args = "not valid json {"
        result = parse_arguments(args)
        assert result == {"_raw": "not valid json {"}


class TestOpenAIStyleParser:
    """Tests for OpenAIStyleParser."""

    def test_no_tool_calls_returns_empty_list(self):
        """No tool_calls key should return empty list."""
        parser = OpenAIStyleParser()
        assert parser.extract_tool_calls({}) == []
        assert parser.extract_tool_calls({"content": "Hello"}) == []
        assert parser.extract_tool_calls({"tool_calls": []}) == []
        assert parser.extract_tool_calls({"tool_calls": None}) == []

    def test_valid_openai_style_tool_call(self):
        """OpenAI style tool_call with dict arguments."""
        parser = OpenAIStyleParser()
        message = {
            "tool_calls": [{
                "function": {
                    "name": "read_file",
                    "arguments": {"path": "/etc/hosts"}
                }
            }]
        }
        result = parser.extract_tool_calls(message)
        assert len(result) == 1
        assert result[0].name == "read_file"
        assert result[0].arguments == {"path": "/etc/hosts"}

    def test_tool_call_with_id(self):
        """Tool call with id field is extracted and preserved."""
        parser = OpenAIStyleParser()
        message = {
            "tool_calls": [{
                "id": "call_abc123",
                "function": {
                    "name": "bash",
                    "arguments": {"command": "ls"}
                }
            }]
        }
        result = parser.extract_tool_calls(message)
        assert len(result) == 1
        assert result[0].name == "bash"
        assert result[0].id == "call_abc123", f"Expected id 'call_abc123', got '{result[0].id}'"

    def test_arguments_as_json_string(self):
        """Arguments may come as a JSON string that needs parsing."""
        parser = OpenAIStyleParser()
        message = {
            "tool_calls": [{
                "function": {
                    "name": "search",
                    "arguments": '{"query": "python", "limit": 5}'
                }
            }]
        }
        result = parser.extract_tool_calls(message)
        assert len(result) == 1
        assert result[0].arguments == {"query": "python", "limit": 5}

    def test_arguments_as_malformed_json_string(self):
        """Malformed JSON in arguments is handled gracefully."""
        parser = OpenAIStyleParser()
        message = {
            "tool_calls": [{
                "function": {
                    "name": "search",
                    "arguments": "not valid json {"
                }
            }]
        }
        result = parser.extract_tool_calls(message)
        assert len(result) == 1
        assert result[0].name == "search"
        assert result[0].arguments == {"_raw": "not valid json {"}

    def test_missing_function_name(self):
        """Tool call without function name is skipped."""
        parser = OpenAIStyleParser()
        message = {
            "tool_calls": [{
                "function": {
                    "arguments": {"path": "/tmp"}
                }
            }]
        }
        result = parser.extract_tool_calls(message)
        assert result == []

    def test_multiple_tool_calls(self):
        """Multiple tool calls are all extracted."""
        parser = OpenAIStyleParser()
        message = {
            "tool_calls": [
                {"function": {"name": "read_file", "arguments": {"path": "/tmp/a"}}},
                {"function": {"name": "bash", "arguments": {"command": "ls"}}}
            ]
        }
        result = parser.extract_tool_calls(message)
        assert len(result) == 2
        assert result[0].name == "read_file"
        assert result[1].name == "bash"


class TestOllamaParser:
    """Tests for OllamaParser."""

    def test_ollama_style_tool_call(self):
        """Ollama style tool_call with nested structure."""
        parser = OllamaParser()
        message = {
            "tool_calls": [{
                "id": "call_123",
                "function": {
                    "name": "read_file",
                    "arguments": {"path": "/tmp/test.txt"}
                }
            }]
        }
        result = parser.extract_tool_calls(message)
        assert len(result) == 1
        assert result[0].name == "read_file"
        assert result[0].arguments["path"] == "/tmp/test.txt"

    def test_ollama_function_call_fallback(self):
        """Ollama parser handles function_call fallback."""
        parser = OllamaParser()
        message = {
            "tool_calls": [{
                "function_call": {
                    "name": "bash",
                    "arguments": '{"command": "pwd"}'
                }
            }]
        }
        result = parser.extract_tool_calls(message)
        assert len(result) == 1
        assert result[0].name == "bash"


class TestMultiFormatParser:
    """Tests for MultiFormatParser - tries multiple formats."""

    def test_function_call_at_top_level(self):
        """Top-level function_call is detected."""
        parser = MultiFormatParser()
        message = {
            "function_call": {
                "name": "read_file",
                "arguments": '{"path": "/etc/hosts"}'
            }
        }
        result = parser.extract_tool_calls(message)
        assert len(result) == 1
        assert result[0].name == "read_file"

    def test_openai_style_fallback(self):
        """Falls back to OpenAI style if no top-level function_call."""
        parser = MultiFormatParser()
        message = {
            "tool_calls": [{
                "function": {
                    "name": "bash",
                    "arguments": {"command": "whoami"}
                }
            }]
        }
        result = parser.extract_tool_calls(message)
        assert len(result) == 1
        assert result[0].name == "bash"


class TestGetParser:
    """Tests for get_parser factory function."""

    def test_ollama_returns_ollama_parser(self):
        """OLLAMA provider returns OllamaParser."""
        parser = get_parser(ProviderType.OLLAMA)
        assert isinstance(parser, OllamaParser)

    def test_minimax_returns_multi_format_parser(self):
        """MINIMAX provider returns MultiFormatParser."""
        parser = get_parser(ProviderType.MINIMAX)
        assert isinstance(parser, MultiFormatParser)

    def test_openai_returns_openai_parser(self):
        """OPENAI provider returns OpenAIStyleParser."""
        parser = get_parser(ProviderType.OPENAI)
        assert isinstance(parser, OpenAIStyleParser)

    def test_string_provider_type(self):
        """String provider type is normalized."""
        parser = get_parser("ollama")
        assert isinstance(parser, OllamaParser)
        parser = get_parser("openai")
        assert isinstance(parser, OpenAIStyleParser)