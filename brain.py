"""LLM request handler - brain of the agent."""
import json
import os
import requests
from provider import ProviderConfig


def _parse_tool_call(message: dict) -> str | None:
    """Extract and serialize a tool call from a message dict.

    Handles both OpenAI and Ollama tool_call formats where arguments
    might be a dict, string, or JSON string.

    Args:
        message: A message dict that may contain tool_calls.

    Returns:
        JSON string {"name": <tool>, "arguments": <args>} or None if no tool call.
    """
    tool_calls = message.get('tool_calls')
    if not tool_calls:
        return None

    call = tool_calls[0]
    fn = call.get('function', {})

    name = fn.get('name')
    if not name:
        return None

    arguments = fn.get('arguments', '{}')
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            # If it's not valid JSON, treat as a malformed argument
            arguments = {"_raw": arguments}

    return json.dumps({"name": name, "arguments": arguments})


def _get_content(message: dict | None) -> str:
    """Safely extract content from a message dict."""
    if message is None:
        return ""
    return message.get('content', "") or ""


def call_llm(history: list, system_prompt: str, config: ProviderConfig) -> str:
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

    # Only attach tools for providers that actually support function calling
    if config.tools:
        payload["tools"] = config.tools

    try:
        response = requests.post(config.url, headers=headers, json=payload, timeout=180)
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
        return f"[BRAIN ERROR: HTTP {status}]"
    except json.JSONDecodeError as e:
        print(f"[BRAIN JSON ERROR: {e}]")
        return "[BRAIN ERROR: Invalid JSON response from API]"
    except Exception as e:
        print(f"[BRAIN ERROR: {e}]")
        return f"[BRAIN ERROR: {e}]"


def _handle_openai_style_response(data: dict) -> str:
    """Handle MiniMax/OpenAI/OpenRouter style responses."""
    # Guard: check for presence and non-emptiness of choices
    if 'choices' not in data:
        return "[BRAIN ERROR: Missing 'choices' in response]"

    choices = data['choices']
    if not choices:
        return "[BRAIN ERROR: Empty choices array]"

    message = choices[0].get('message')
    if message is None:
        return "[BRAIN ERROR: choices[0].message is None]"

    # Try tool call first
    tool_result = _parse_tool_call(message)
    if tool_result is not None:
        return tool_result

    # Fall back to text content
    return _get_content(message)


def _handle_ollama_response(data: dict) -> str:
    """Handle Ollama style responses."""
    if 'message' not in data:
        return "[BRAIN ERROR: Missing 'message' in Ollama response]"

    message = data['message']
    if message is None:
        return "[BRAIN ERROR: message is None in Ollama response]"

    # Try tool call first
    tool_result = _parse_tool_call(message)
    if tool_result is not None:
        return tool_result

    # Fall back to text content
    return _get_content(message)
