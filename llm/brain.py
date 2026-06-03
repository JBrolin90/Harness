"""LLM request handler - brain of the agent."""
import json
import os
import requests
from .provider import ProviderConfig
from .response import LLMResponse, ToolCall


MAX_TOOL_CALLS = 50

def _parse_tool_calls(message: dict) -> list[ToolCall]:
    """Extract tool calls from a message dict.

    Handles multiple tool call formats:
    - OpenAI style: message.tool_calls[i].function.name/arguments
    - Top-level function_call: message.function_call.name/arguments
    - Ollama style: message.tool_calls[i].function.name
    - Alternative field names: function_call.name, function.name

    Args:
        message: A message dict that may contain tool_calls or function_call.

    Returns:
        List of ToolCall objects (capped at MAX_TOOL_CALLS).
    """
    parsed_calls = []
    tool_call_count = 0

    # Handle top-level function_call (some providers use this)
    function_call = message.get('function_call')
    if function_call:
        name = function_call.get('name', '')
        if name:
            arguments = function_call.get('arguments', '{}')
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"_raw": arguments}
            parsed_calls.append(ToolCall(name=name, arguments=arguments))
        return parsed_calls

    # Handle tool_calls array (OpenAI / OpenRouter / MiniMax)
    tool_calls_data = message.get('tool_calls') or []

    for call in tool_calls_data:
        # Try OpenAI style: call.function.name
        fn = call.get('function', {})
        name = fn.get('name')
        
        # Fallback: try function_call.name directly
        if not name and 'function_call' in call:
            fc = call.get('function_call', {})
            name = fc.get('name') or fc.get('function', {}).get('name')
        
        if not name:
            continue

        arguments = fn.get('arguments', '{}')
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                # If it's not valid JSON, treat as a malformed argument
                arguments = {"_raw": arguments}

        parsed_calls.append(ToolCall(name=name, arguments=arguments))
        tool_call_count += 1
        if tool_call_count >= MAX_TOOL_CALLS:
            break

    return parsed_calls


def _extract_text_content(message: dict | None) -> str:
    """Safely extract text content from a message dict."""
    if message is None:
        return ""
    return message.get('content', "") or ""


def _format_tools_for_provider(tools: list, provider_type: str) -> list | None:
    """Format tools according to provider requirements.
    
    - minimax: requires {"type": "function", "function": ...} wrapping
    - openai / openrouter: use standard tool format
    - ollama: pass as-is
    
    Detects if tools are already wrapped (by controller) to avoid double-wrapping.
    Returns None if provider doesn't support tools.
    """
    if not tools:
        return None
    
    # Check if tools are already wrapped (controller does this)
    already_wrapped = any(
        isinstance(t, dict) and "type" in t and "function" in t and isinstance(t.get("function"), dict)
        for t in tools
    )
    
    if provider_type == "minimax":
        # MiniMax requires wrapping in type/function structure
        if already_wrapped:
            # Already wrapped by controller, pass through
            return tools
        return [{"type": "function", "function": t} for t in tools]
    elif provider_type == "ollama":
        # Ollama supports native tool_calls in recent versions
        return tools
    else:
        # OpenAI-compatible: use standard format
        return tools


def _make_request_with_retry(url: str, headers: dict, payload: dict, max_retries: int = 3) -> requests.Response:
    """Make HTTP request with exponential backoff retry for transient errors.
    
    Retries on:
    - HTTP 429 (rate limit) with Retry-After header support
    - HTTP 500, 502, 503, 504 (server errors)
    - Connection errors and timeouts
    
    Args:
        url: Request URL
        headers: Request headers
        payload: Request body (JSON)
        max_retries: Maximum number of retry attempts (default 3)
    
    Returns:
        requests.Response object
    
    Raises:
        Last exception if all retries exhausted
    """
    import time
    
    retryable_statuses = {429, 500, 502, 503, 504}
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=(5, 180))
            
            if response.status_code not in retryable_statuses:
                # Not a retryable error, return as-is
                response.raise_for_status()
                return response
            
            # Rate limited - check Retry-After header
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                if retry_after:
                    wait_time = int(retry_after)
                else:
                    # Exponential backoff: 1s, 2s, 4s, ...
                    wait_time = 2 ** attempt
                print(f"[BRAIN] Rate limited. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
            else:
                # Server error - exponential backoff
                wait_time = 2 ** attempt
                print(f"[BRAIN] Server error {response.status_code}. Retrying in {wait_time}s ({attempt + 1}/{max_retries})...")
            
            time.sleep(wait_time)
            last_exception = requests.HTTPError(response=response)
            
        except requests.exceptions.ConnectionError as e:
            wait_time = 2 ** attempt
            print(f"[BRAIN] Connection error. Retrying in {wait_time}s ({attempt + 1}/{max_retries})...")
            time.sleep(wait_time)
            last_exception = e
        except requests.exceptions.Timeout as e:
            wait_time = 2 ** attempt
            print(f"[BRAIN] Request timeout. Retrying in {wait_time}s ({attempt + 1}/{max_retries})...")
            time.sleep(wait_time)
            last_exception = e
        except Exception:
            # Non-retryable exception, re-raise immediately
            raise
    
    # All retries exhausted
    if last_exception is not None:
        raise last_exception
    raise RuntimeError("Request failed: max retries reached without a specific exception")


def consult_llm(history: list, system_prompt: str, config: ProviderConfig) -> LLMResponse:
    """Unified LLM request handler using a ProviderConfig object."""
    # Resolve API key from environment variable if specified
    env_api_key = os.environ.get(config.api_key_env_var, "") if config.api_key_env_var else ""
    if not env_api_key and config.provider_type != "ollama":
        print(f"[WARNING: API key for {config.name} not found in environment variable '{config.api_key_env_var}']")

    headers = {"Content-Type": "application/json"}
    
    # Only attach Authorization header if a key was resolved
    if env_api_key:
        headers["Authorization"] = f"Bearer {env_api_key}"

    messages = [{"role": "system", "content": system_prompt}]
    messages += history

    payload = {
        "model": config.model,
        "messages": messages,
        "stream": config.attributes.get("stream", False)
    }

    # Add response_format if specified in attributes
    if "response_format" in config.attributes:
        payload["response_format"] = config.attributes["response_format"]

    # Only attach tools for providers that support function calling
    formatted_tools = _format_tools_for_provider(config.tools, config.provider_type)
    if formatted_tools:
        payload["tools"] = formatted_tools

    # Add tool_choice if specified (forces specific tool or requires a tool call)
    if "tool_choice" in config.attributes:
        payload["tool_choice"] = config.attributes["tool_choice"]

    try:
        response = _make_request_with_retry(config.url, headers=headers, payload=payload)
        data = response.json()

        # Dispatch to provider-specific handler
        if config.provider_type == "ollama":
            return _handle_ollama_response(data)
        else:
            return _handle_openai_response(data)

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


def _extract_message_at_path(data: dict, message_key: str = "choices[0].message") -> LLMResponse:
    """Navigate to message using dot-notation path and extract content + tool_calls.
    
    Args:
        data: Response dictionary from API.
        message_key: Dot-notation path to the message object (e.g., "choices[0].message" or "message").
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
    
    tool_calls = _parse_tool_calls(message)
    
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


def _handle_openai_response(data: dict) -> LLMResponse:
    """Handle MiniMax/OpenAI/OpenRouter style responses (OpenAI-compatible)."""
    return _extract_message_at_path(data, message_key="choices[0].message")


def _handle_ollama_response(data: dict) -> LLMResponse:
    """Handle Ollama style responses."""
    return _extract_message_at_path(data, message_key="message")
