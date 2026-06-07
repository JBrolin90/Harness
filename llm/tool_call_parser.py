"""Tool call parsing for different LLM provider formats."""
import json
from abc import ABC, abstractmethod

from .provider import ProviderType
from .response import ToolCall


def parse_arguments(arguments: str | dict) -> dict:
    """Parse tool call arguments from string or dict.
    
    Args:
        arguments: JSON string or dict of arguments
    
    Returns:
        Parsed arguments dict
    """
    if isinstance(arguments, dict):
        return arguments
    try:
        return json.loads(arguments)
    except json.JSONDecodeError:
        return {"_raw": arguments}


class ToolCallParser(ABC):
    """Base class for provider-specific tool call parsing."""
    
    @abstractmethod
    def extract_tool_calls(self, message: dict) -> list[ToolCall]:
        """Extract tool calls from a message dict.
        
        Args:
            message: Message dict from provider response
        
        Returns:
            List of ToolCall objects
        """
        pass
    
    def _build_tool_call(self, name: str, arguments: str | dict, tool_id: str = "") -> ToolCall:
        """Build a ToolCall from name, arguments, and optional id."""
        return ToolCall(name=name, arguments=parse_arguments(arguments), id=tool_id)


class OpenAIStyleParser(ToolCallParser):
    """Parser for OpenAI-style tool_calls array.
    
    Handles: message.tool_calls[i].function.name/arguments
    """
    
    def extract_tool_calls(self, message: dict) -> list[ToolCall]:
        tool_calls_data = message.get('tool_calls') or []
        return [tc for tc in (self._parse_call(call) for call in tool_calls_data) if tc is not None]
    
    def _parse_call(self, call: dict) -> ToolCall | None:
        fn = call.get('function', {})
        name = fn.get('name')
        tool_id = call.get('id', '')
        
        if not name:
            # Fallback: try function_call.name directly
            fc = call.get('function_call', {})
            name = fc.get('name') or fc.get('function', {}).get('name')
        
        if not name:
            return None
        
        return self._build_tool_call(name, fn.get('arguments', '{}'), tool_id)


class TopLevelFunctionCallParser(ToolCallParser):
    """Parser for top-level function_call messages.
    
    Handles: message.function_call.name/arguments
    """
    
    def extract_tool_calls(self, message: dict) -> list[ToolCall]:
        function_call = message.get('function_call')
        if not function_call:
            return []
        
        name = function_call.get('name', '')
        if not name:
            return []
        
        return [self._build_tool_call(name, function_call.get('arguments', '{}'))]


class OllamaParser(ToolCallParser):
    """Parser for Ollama-style tool_calls.
    
    Similar to OpenAI style but uses different field structure.
    Handles: message.tool_calls[i].function.name
    """
    
    def extract_tool_calls(self, message: dict) -> list[ToolCall]:
        tool_calls_data = message.get('tool_calls') or []
        return [tc for tc in (self._parse_call(call) for call in tool_calls_data) if tc is not None]
    
    def _parse_call(self, call: dict) -> ToolCall | None:
        fn = call.get('function', {})
        name = fn.get('name')
        tool_id = call.get('id', '')
        
        if not name and 'function_call' in call:
            fc = call.get('function_call', {})
            name = fc.get('name') or fc.get('function', {}).get('name')
        
        if not name:
            return None
        
        return self._build_tool_call(name, fn.get('arguments', '{}'), tool_id)


class MultiFormatParser(ToolCallParser):
    """Parser that tries multiple formats (OpenAI and top-level function_call).
    
    Useful for providers that may use either format.
    """
    
    def extract_tool_calls(self, message: dict) -> list[ToolCall]:
        # Try top-level function_call first
        if 'function_call' in message:
            parser = TopLevelFunctionCallParser()
            calls = parser.extract_tool_calls(message)
            if calls:
                return calls
        
        # Try OpenAI-style tool_calls
        parser = OpenAIStyleParser()
        return parser.extract_tool_calls(message)


def get_parser(provider_type: ProviderType | str) -> ToolCallParser:
    """Get appropriate tool call parser for provider type.
    
    Args:
        provider_type: ProviderType enum or string identifier
    
    Returns:
        ToolCallParser instance
    """
    # Normalize to enum
    if isinstance(provider_type, str):
        provider_type = ProviderType.from_string(provider_type)
    
    if provider_type == ProviderType.OLLAMA:
        return OllamaParser()
    elif provider_type == ProviderType.MINIMAX:
        return MultiFormatParser()
    else:
        # openai, openrouter, etc.
        return OpenAIStyleParser()