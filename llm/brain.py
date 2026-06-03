"""LLM request handler - brain of the agent."""
import json
import requests

from .provider import ProviderConfig
from .request_builder import RequestBuilder
from .tool_call_parser import get_parser, parse_arguments, TopLevelFunctionCallParser, OpenAIStyleParser, OllamaParser, MultiFormatParser
from .retry_handler import RetryHandler
from .response import LLMResponse, ToolCall


def _parse_tool_calls(message: dict) -> list[ToolCall]:
    """Parse tool calls using MultiFormatParser (backward compatible)."""
    return MultiFormatParser().extract_tool_calls(message)


def _format_tools_for_provider(tools: list, provider_type: str) -> list | None:
    """Format tools according to provider requirements (delegates to RequestBuilder)."""
    from .request_builder import RequestBuilder
    config = type('Config', (), {'provider_type': provider_type, 'tools': tools})()
    builder = RequestBuilder(config)
    return builder._format_tools_for_provider(tools)


MAX_TOOL_CALLS = 50


def _extract_text_content(message: dict | None) -> str:
    """Safely extract text content from a message dict."""
    if message is None:
        return ""
    return message.get('content', "") or ""


def _make_request_with_retry(url: str, headers: dict, payload: dict, max_retries: int = 3) -> requests.Response:
    """Make HTTP request with exponential backoff retry (delegates to RetryHandler)."""
    return RetryHandler(max_retries=max_retries).execute(url, headers, payload)


def consult_llm(history: list, system_prompt: str, config: ProviderConfig) -> LLMResponse:
    """Unified LLM request handler using a ProviderConfig object."""
    builder = RequestBuilder(config)
    
    # Warn if API key is missing (skip for ollama which doesn't need one)
    env_api_key = builder.api_key()
    if not env_api_key and config.provider_type != "ollama":
        print(f"[WARNING: API key for {config.name} not found in environment variable '{config.api_key_env_var}']")

    headers = builder.headers()
    payload = builder.payload(history, system_prompt)

    try:
        response = _make_request_with_retry(config.url, headers=headers, payload=payload)
        data = response.json()

        # Dispatch to provider-specific handler
        if config.provider_type == "ollama":
            return _handle_ollama_response(data, config.provider_type)
        else:
            return _handle_openai_response(data, config.provider_type)

    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        text = e.response.text if e.response is not None else "no response body"
        print(f"[BRAIN HTTP ERROR: {status} {text}]")
        return LLMResponse(error=f"[BRAIN ERROR: HTTP {status}]")
    except json.JSONDecodeError as e:
        print(f"[BRAIN JSON ERROR: {e}]")
        return LLMResponse(error="[BRAIN ERROR: Invalid JSON response from API]")
    except Exception as e:
        print(f"[BRAIN ERROR: {e}]")
        return LLMResponse(error=f"[BRAIN ERROR: {e}]")


def _extract_message_at_path(data: dict, message_key: str, provider_type: str) -> LLMResponse:
    """Navigate to message using dot-notation path and extract content + tool_calls.
    
    Args:
        data: Response dictionary from API.
        message_key: Dot-notation path to the message object (e.g., "choices[0].message" or "message").
        provider_type: Provider identifier to select appropriate tool call parser.
    """
    # Navigate to message using dot notation
    parts = message_key.split(".")
    message = data
    for part in parts:
        # Handle list indexing like choices[0]
        if "[" in part and part.endswith("]"):
            key, idx_str = part.split("[")
            idx = int(idx_str.rstrip("]"))
            if isinstance(message, dict) and key in message and isinstance(message[key], list) and len(message[key]) > idx:
                message = message[key][idx]
            else:
                return LLMResponse(error=f"[BRAIN ERROR: Missing '{message_key}' in response]")
        elif isinstance(message, dict) and part in message:
            message = message[part]
        else:
            return LLMResponse(error=f"[BRAIN ERROR: Missing '{message_key}' in response]")
    
    if message is None:
        return LLMResponse(error=f"[BRAIN ERROR: {message_key} is None]")
    
    parser = get_parser(provider_type)
    tool_calls = parser.extract_tool_calls(message)[:MAX_TOOL_CALLS]
    
    # Validate finish_reason if available (check for truncation with tool calls)
    finish_reason = None
    if "choices" in data and isinstance(data["choices"], list) and len(data["choices"]) > 0:
        choice = data["choices"][0]
        finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
        if tool_calls and finish_reason == "length":
            print("[BRAIN WARNING: Response may be truncated - finish_reason is 'length' with tool_calls]")
    
    return LLMResponse(
        text=_extract_text_content(message),
        tool_calls=tool_calls
    )


def _handle_openai_response(data: dict, provider_type: str = "openai") -> LLMResponse:
    """Handle MiniMax/OpenAI/OpenRouter style responses (OpenAI-compatible)."""
    return _extract_message_at_path(data, message_key="choices[0].message", provider_type=provider_type)


def _handle_ollama_response(data: dict, provider_type: str = "ollama") -> LLMResponse:
    """Handle Ollama style responses."""
    return _extract_message_at_path(data, message_key="message", provider_type=provider_type)