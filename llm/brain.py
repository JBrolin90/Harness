"""LLM request handler - orchestration layer."""
import json
import requests

from .provider import ProviderConfig, ProviderType
from .request_builder import RequestBuilder
from .tool_call_parser import get_parser
from .retry_handler import RetryHandler
from .response import LLMResponse, ToolCall
from .message_nav import navigate_to_message, is_empty_choices


# Error formatting constants
ERROR_PREFIX = "[BRAIN ERROR: "
ERROR_SUFFIX = "]"

# Tool call limits to prevent runaway responses
MAX_TOOL_CALLS: int = 50

# Provider to message key mapping
_MESSAGE_KEYS: dict[ProviderType, str] = {
    ProviderType.OLLAMA: "message",
}


def _make_error_response(message: str) -> LLMResponse:
    """Create a properly formatted error LLMResponse."""
    return LLMResponse(error=f"{ERROR_PREFIX}{message}{ERROR_SUFFIX}")


def _extract_text_content(message: dict | str | None) -> str:
    """Safely extract text content from a message dict."""
    if message is None or isinstance(message, str):
        return ""
    return message.get('content', "") or ""


def _make_request_with_retry(url: str, headers: dict, payload: dict) -> requests.Response:
    """Make HTTP request with exponential backoff retry."""
    return RetryHandler().execute(url, headers, payload)


def _get_message_key(provider_type: ProviderType) -> str:
    """Get the dot-notation path to the message object for this provider."""
    return _MESSAGE_KEYS.get(provider_type, "choices[0].message")


def _handle_response(data: dict, provider_type: ProviderType) -> LLMResponse:
    """Handle LLM response, extracting text and tool calls.
    
    Args:
        data: Response dictionary from API.
        provider_type: Provider to select appropriate tool call parser.
    
    Returns:
        LLMResponse with text and/or tool calls, or error response.
    """
    message_key = _get_message_key(provider_type)
    message = navigate_to_message(data, message_key)
    
    # Handle empty choices - return empty response (not an error)
    if is_empty_choices(message):
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


def _check_truncation(data: dict, tool_calls: list[ToolCall]) -> None:
    """Check and warn if response may be truncated (finish_reason is 'length')."""
    if "choices" in data and isinstance(data["choices"], list) and len(data["choices"]) > 0:
        choice = data["choices"][0]
        finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
        if tool_calls and finish_reason == "length":
            print("[BRAIN WARNING: Response may be truncated - finish_reason is 'length' with tool_calls]")


def consult_llm(history: list, system_prompt: str, config: ProviderConfig) -> LLMResponse:
    """Unified LLM request handler using a ProviderConfig object.
    
    Orchestrates the request/response cycle by delegating to specialized components:
    - RequestBuilder for HTTP construction
    - RetryHandler for HTTP execution
    - Provider-specific response handler for parsing
    
    Args:
        history: List of conversation messages.
        system_prompt: System prompt to prepend.
        config: Provider configuration with URL, model, tools, etc.
    
    Returns:
        LLMResponse containing text and/or tool calls, or error response.
    """
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
        return _handle_response(data, config.provider_type)

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