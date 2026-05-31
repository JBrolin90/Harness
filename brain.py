"""LLM request handler - brain of the agent."""
import json
import os
import requests
from provider import ProviderConfig
from response import LLMResponse, ToolCall


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
        List of ToolCall objects.
    """
    parsed_calls = []

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

    return parsed_calls


def _get_content(message: dict | None) -> str:
    """Safely extract content from a message dict."""
    if message is None:
        return ""
    return message.get('content', "") or ""


def _format_tools_for_provider(tools: list, provider_type: str) -> list | None:
    """Format tools according to provider requirements.
    
    - minimax: requires {"type": "function", "function": ...} wrapping
    - openai / openrouter: use standard tool format
    - ollama: skip tools if provider doesn't support them
    
    Returns None if provider doesn't support tools.
    """
    if not tools:
        return None
    
    if provider_type == "minimax":
        # MiniMax requires wrapping in type/function structure
        return [{"type": "function", "function": t} for t in tools]
    elif provider_type == "ollama":
        # Ollama supports native tool_calls in recent versions
        # Return as-is, let the provider handle it
        return tools
    else:
        # OpenAI-compatible: use standard format
        return tools


def call_llm(history: list, system_prompt: str, config: ProviderConfig) -> LLMResponse:
    """Unified LLM request handler using a ProviderConfig object."""
    # Resolve API key from environment variable if specified
    resolved_api_key = os.environ.get(config.api_key_env_var, "") if config.api_key_env_var else ""
    if not resolved_api_key and config.provider_type != "ollama":
        print(f"[WARNING: API key for {config.name} not found in environment variable '{config.api_key_env_var}']")

    headers = {"Content-Type": "application/json"}
    
    # Only attach Authorization header if a key was resolved
    if resolved_api_key:
        headers["Authorization"] = f"Bearer {resolved_api_key}"

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

    try:
        response = requests.post(config.url, headers=headers, json=payload, timeout=(5, 180))
        response.raise_for_status()
        data = response.json()

        # Dispatch to provider-specific handler
        if config.provider_type == "ollama":
            return _handle_ollama_response(data)
        else:
            return _handle_openai_style_response(data)

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


def _handle_openai_style_response(data: dict) -> LLMResponse:
    """Handle MiniMax/OpenAI/OpenRouter style responses."""
    # Guard: check for presence and non-emptiness of choices
    if 'choices' not in data:
        return LLMResponse(error="[BRAIN ERROR: Missing 'choices' in response]")

    choices = data['choices']
    if not choices:
        return LLMResponse(error="[BRAIN ERROR: Empty choices array]")

    message = choices[0].get('message')
    if message is None:
        return LLMResponse(error="[BRAIN ERROR: choices[0].message is None]")

    return LLMResponse(
        text=_get_content(message),
        tool_calls=_parse_tool_calls(message)
    )


def _handle_ollama_response(data: dict) -> LLMResponse:
    """Handle Ollama style responses."""
    if 'message' not in data:
        return LLMResponse(error="[BRAIN ERROR: Missing 'message' in Ollama response]")

    message = data['message']
    if message is None:
        return LLMResponse(error="[BRAIN ERROR: message is None in Ollama response]")

    return LLMResponse(
        text=_get_content(message),
        tool_calls=_parse_tool_calls(message)
    )
