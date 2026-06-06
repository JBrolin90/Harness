"""Request building for LLM API calls."""
import os

from .provider import ProviderConfig, ProviderType
from .response import LLMResponse


class RequestBuilder:
    """Builds HTTP request components for LLM API calls.
    
    Responsibilities:
    - Resolve API key from environment
    - Construct HTTP headers
    - Build request payload from config
    - Format tools for provider-specific requirements
    """
    
    def __init__(self, config: ProviderConfig):
        self.config = config
    
    def api_key(self) -> str:
        """Resolve API key from environment variable."""
        if not self.config.api_key_env_var:
            return ""
        return os.environ.get(self.config.api_key_env_var, "")
    
    def headers(self) -> dict:
        """Build HTTP headers including Authorization if key is available."""
        headers = {"Content-Type": "application/json"}
        key = self.api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers
    
    def _tools_wrapped(self, tools: list) -> bool:
        """Check if tools are already wrapped in type/function structure."""
        return any(
            isinstance(t, dict) and "type" in t and "function" in t 
            and isinstance(t.get("function"), dict)
            for t in tools
        )
    
    def _format_tools_for_provider(self, tools: list) -> list | None:
        """Format tools according to provider requirements.
        
        - minimax: requires {"type": "function", "function": ...} wrapping
        - openai / openrouter: use standard tool format
        - ollama: pass as-is
        """
        if not tools:
            return None
        
        already_wrapped = self._tools_wrapped(tools)
        
        if self.config.provider_type == ProviderType.MINIMAX:
            return tools if already_wrapped else [{"type": "function", "function": t} for t in tools]
        elif self.config.provider_type == ProviderType.OLLAMA:
            return tools
        else:
            # OpenAI-compatible
            return tools
    
    def payload(self, history: list, system_prompt: str) -> dict:
        """Build the request payload from config and messages."""
        messages = [{"role": "system", "content": system_prompt}] + list(history)
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": self.config.attributes.get("stream", False)
        }
        
        if "response_format" in self.config.attributes:
            payload["response_format"] = self.config.attributes["response_format"]
        
        formatted_tools = self._format_tools_for_provider(self.config.tools)
        if formatted_tools:
            payload["tools"] = formatted_tools
        
        if "tool_choice" in self.config.attributes:
            payload["tool_choice"] = self.config.attributes["tool_choice"]
        
        return payload