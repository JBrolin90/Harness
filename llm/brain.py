"""LLM request handler - brain of the agent."""
import json
import requests

from .provider import ProviderConfig, ProviderType
from .request_builder import RequestBuilder
from .tool_call_parser import get_parser, MultiFormatParser
from .retry_handler import RetryHandler
from .response import LLMResponse, ToolCall


# Error formatting constants
ERROR_PREFIX = "[BRAIN ERROR: "
ERROR_SUFFIX = "]"


def _make_error_response(message: str) -> LLMResponse:
    """Create a properly formatted error LLMResponse."""
    return LLMResponse(error=f"{ERROR_PREFIX}{message}{ERROR_SUFFIX}")


# Tool call limits to prevent runaway responses
MAX_TOOL_CALLS: int = 50


def _parse_tool_calls(message: dict) -> list[ToolCall]:
    """Parse tool calls using MultiFormatParser (backward compatible)."""
    return MultiFormatParser().extract_tool_calls(message)


def _format_tools_for_provider(tools: list, provider_type: ProviderType | str) -> list | None:
    """Format tools according to provider requirements (delegates to RequestBuilder)."""
    from .request_builder import RequestBuilder
    # Normalize to ProviderType enum
    pt = provider_type if isinstance(provider_type, ProviderType) else ProviderType.from_string(provider_type)
    config = type('Config', (), {'provider_type': pt, 'tools': tools})()
    builder = RequestBuilder(config)  # type: ignore - anonymous class for backward compatibility
    return builder._format_tools_for_provider(tools)


def _extract_text_content(message: dict | str | None) -> str:
    """Safely extract text content from a message dict."""
    if message is None or isinstance(message, str):
        return ""
    return message.get('content', "") or ""


def _make_request_with_retry(url: str, headers: dict, payload: dict, max_retries: int = 3) -> requests.Response:
    """Make HTTP request with exponential backoff retry (delegates to RetryHandler)."""
    return RetryHandler(max_retries=max_retries).execute(url, headers, payload)


def consult_llm(history: list, system_prompt: str, config: ProviderConfig) -> LLMResponse:
    """Unified LLM request handler using a ProviderConfig object."""
    builder = RequestBuilder(config)
    
    # Warn if API key is missing (skip for local providers)
    env_api_key = builder.api_key()
    if not env_api_key and not config.provider_type.is_local:
        print(f"[WARNING: API key for {config.name} not found in environment variable '{config.api_key_env_var}']")

    headers = builder.headers()
    payload = builder.payload(history, system_prompt)

    try:
        response = _make_request_with_retry(config.url, headers=headers, payload=payload)
        data = response.json()

        # Dispatch to provider-specific handler
        if config.provider_type == ProviderType.OLLAMA:
            return _handle_ollama_response(data, config.provider_type)
        else:
            return _handle_openai_response(data, config.provider_type)

    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        text = e.response.text if e.response is not None else "no response body"
        print(f"[BRAIN HTTP ERROR: {status} {text}]")
        return _make_error_response(f"HTTP {status}")
    except json.JSONDecodeError as e:
        print(f"[BRAIN JSON ERROR: {e}]")
        return _make_error_response(f"Invalid JSON response from API: {e}")
    except Exception as e:
        print(f"[BRAIN ERROR: {e}]")
        return _make_error_response(str(e))


def _navigate_to_message(data: dict, message_key: str) -> dict | None | str:
    """Navigate to message using dot-notation path.
    
    Args:
        data: Response dictionary from API.
        message_key: Dot-notation path (e.g., "choices[0].message" or "message").
    
    Returns:
        Message dict if found, None if path doesn't exist,
        or special sentinel for empty choices.
    """
    parts = message_key.split(".")
    current = data
    for part in parts:
        if "[" in part and part.endswith("]"):
            key, idx_str = part.split("[")
            idx = int(idx_str.rstrip("]"))
            if isinstance(current, dict) and key in current:
                arr = current[key]
                # Handle empty choices array - treat as empty response (not error)
                if arr is None or (isinstance(arr, list) and len(arr) == 0):
                    return "__EMPTY_CHOICES__"
                if isinstance(arr, list) and len(arr) > idx:
                    current = arr[idx]
                else:
                    return None
            else:
                return None
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _check_truncation(data: dict, tool_calls: list) -> None:
    """Check and warn if response may be truncated (finish_reason is 'length')."""
    if "choices" in data and isinstance(data["choices"], list) and len(data["choices"]) > 0:
        choice = data["choices"][0]
        finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
        if tool_calls and finish_reason == "length":
            print("[BRAIN WARNING: Response may be truncated - finish_reason is 'length' with tool_calls]")


def _extract_message_at_path(data: dict, message_key: str, provider_type: ProviderType | str) -> LLMResponse:
    """Navigate to message and extract content + tool_calls.
    
    Args:
        data: Response dictionary from API.
        message_key: Dot-notation path to the message object.
        provider_type: Provider identifier to select appropriate tool call parser.
    """
    message = _navigate_to_message(data, message_key)
    
    # Handle empty choices - return empty response (not an error)
    if message == "__EMPTY_CHOICES__":
        return LLMResponse(text="", tool_calls=[])
    
    if message is None:
        return _make_error_response(f"Missing '{message_key}' in response")
    
    if not isinstance(message, dict):
        return _make_error_response(f"Invalid message type: {type(message).__name__}")
    
    parser = get_parser(provider_type)
    tool_calls = parser.extract_tool_calls(message)[:MAX_TOOL_CALLS]
    
    _check_truncation(data, tool_calls)
    
    return LLMResponse(
        text=_extract_text_content(message),
        tool_calls=tool_calls
    )


def _handle_openai_response(data: dict, provider_type: ProviderType | str = "openai") -> LLMResponse:
    """Handle MiniMax/OpenAI/OpenRouter style responses (OpenAI-compatible)."""
    return _extract_message_at_path(data, message_key="choices[0].message", provider_type=provider_type)


def _handle_ollama_response(data: dict, provider_type: ProviderType | str = "ollama") -> LLMResponse:
    """Handle Ollama style responses."""
    return _extract_message_at_path(data, message_key="message", provider_type=provider_type)