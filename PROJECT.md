# Harness Project

## Current Branch: bugfix/text-tool-call-detection (testing)

## Release 0.4.0 (2026-06-07)

### Critical Design Decision: Text Parsing vs Structured Tool Calls

**DO NOT enable text parsing for large cloud models (MiniMax, OpenAI, OpenRouter).**

**Why**: Large cloud models properly use structured `tool_calls` via the API. If they accidentally output text that looks like a tool call, it is NOT the model's intention to execute it — it's just text. Enabling text parsing for these models would cause false tool executions.

**Small local models (qwen, llama variants)**: These models do NOT properly use structured tool calling. They output tool calls as text (JSON, bash blocks, etc.). The `text_parse_*` attributes enable detection and execution of these text-based tool calls.

**How it works**:
- `text_parse_json_codeblock`, `text_parse_json_raw`, `text_parse_bash`, etc. → enable `dispatch_with_text_parsing`
- No text parsing attributes → use `dispatch` (structured tool calls only)

**Provider configuration**:
- `cloud-pro` (MiniMax): NO text parsing enabled → uses `dispatch` only
- `local-coder` (qwen): text parsing enabled → uses `dispatch_with_text_parsing`

### What's Included

**From dev-Laptop:**
- `logger.py` + `test_logger.py` — structured logging system
- `tool_call_id` tracking for MiniMax compatibility
- `529` in retryable statuses
- Logging calls in `tool_dispatch.py`

**From dev-Desktop / refactor/brain-py-improvements:**
- `llm/` package with SRP-separated modules:
  - `llm/brain.py` — main LLM handler
  - `llm/request_builder.py` — builds API requests
  - `llm/retry_handler.py` — handles retries
  - `llm/tool_call_parser.py` — parses tool calls
  - `llm/response.py` — response types
  - `llm/provider.py` — provider config with `ProviderType` enum

### Bug Fixes (in dev)
- **tool_call_id not extracted**: Fixed `llm/tool_call_parser.py` to extract and pass `id` field from tool calls.
- **empty choices array**: Fixed `llm/brain.py` to handle empty choices gracefully.
- **provider recommendations path**: Fixed `llm/provider.py` to use absolute path.
- **text parsing not used for local-coder**: Fixed `task/task.py` to use `execute_tools` for text parsing.
- **JSON parser wrong format**: Fixed `extract_json_string` and `_parse_simple_tool_json` to handle `{"tool": ...}` format.
- **local-coder wrong URL**: Fixed `llm/provider.py` to use `lmde` instead of `localhost`.
- **_parse_simple_tool_json missing arguments key**: Fixed to handle `{"tool": ..., "arguments": {...}}` format (not just `"args"`).
- **logging for dispatch engine selection**: Added logging in `ToolManager.select_dispatch_engine()` using `logger` module.
- **JSON in text without code fences**: Added bracket-counting approach in `_find_json_in_text()` to find JSON objects embedded in text with newlines/indentation. Handles multiline formatted JSON like `{\n    "name": "read_file",\n    "arguments": {...}\n}`.
- **repetition detection false positive for text-based tool calls**: Fixed `conversation_history.py` `add_tool_result()` to accept `has_tool_calls` parameter and `repetition_detector.py` `check_after_tool_result()` to not compare text when `had_tool_call` status changes between calls. Also fixed `_compute_signature_from_text()` to use bracket-counting for nested JSON.
- **repetition check before tool execution**: Fixed `task/task.py` to check for repetition BEFORE executing the tool (not after). This prevents the same tool from being executed twice when model repeats the same tool call. Added `skip_check` parameter to `add_tool_result()` to avoid double-recording in the repetition detector.

### Known Issues
- `tests/test_llm_compatibility.py` has pre-existing import error (`build_system_prompt` not found in `systemprompt.py`)
- **local-coder (qwen) model hallucinations**: qwen2.5-coder may hallucinate tool names. See plan.txt for proposed `system_prompt_additions` attribute fix.
- **Model echoing JSON after tool execution**: After executing a text-based tool call, the model may echo the same JSON back. The repetition detector catches this and breaks the loop, but the result is the JSON text, not the tool execution result. This is a model behavior issue.

### Directory Structure
```
llm/
├── brain.py
├── provider.py
├── request_builder.py
├── response.py
├── retry_handler.py
└── tool_call_parser.py
```

## Test Status
- 230 tests passing (excluding `test_llm_compatibility.py`)
- 10 new integration tests in `TestTextBasedToolCalls` class
- 2 new tests for repetition detection bug (`test_repeated_text_tool_call_only_executes_once`, `test_repeated_tool_call_returns_proper_response`)

## Bob Status
- ✅ Working correctly with cloud-pro (MiniMax) - structured tool calls only
- ✅ Working correctly with local-coder (qwen) - text parsing enabled

## Pending Refactoring (see plan.txt)
- Logger.py thread-safety issues (use LoggerAdapter or try/finally)
- system_prompt_additions attribute for qwen model guidance

## Documentation
- ✅ readme.md updated to reflect current `llm/` package structure