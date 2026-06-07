# Harness Project

## Current Branch: main (dev is up-to-date)

## Release0.4.0 (2026-06-07)

### Branches Merged
- `dev-Laptop` → bugfixes and improvements
- `dev-Desktop` → heavy refactoring (via `refactor/brain-py-improvements`)

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

### Bug Fixes
- **tool_call_id not extracted**: Fixed `llm/tool_call_parser.py` to extract and pass `id` field from tool calls. MiniMax requires this for tool result messages.
- **empty choices array**: Fixed `llm/brain.py` to handle empty choices gracefully instead of returning error.
- **provider recommendations path**: Fixed `llm/provider.py` to use absolute path for `provider-recommendations.json` instead of relative path.
- **text parsing not used for local-coder**: Fixed `task/task.py` to use `execute_tools` (dispatch_with_text_parsing) instead of checking `response.has_tool_calls` directly. This enables text-based tool calls for providers like local-coder (qwen).
- **JSON parser wrong format**: Fixed `extract_json_string` and `_parse_simple_tool_json` in `tool_dispatch.py` to handle `{"tool": "name", "field": value}` format. Qwen models output this format where remaining fields become arguments.

### Known Issues
- `tests/test_llm_compatibility.py` has pre-existing import error (`build_system_prompt` not found in `systemprompt.py`)
- **local-coder (qwen) model hallucinations**: qwen2.5-coder may hallucinate tool names like `tool_response`. This is a model behavior issue, not a code bug. Prompt engineering or model fine-tuning would be needed to resolve it. See plan.txt for proposed `system_prompt_additions` attribute fix.

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
- 220 tests passing (excluding `test_llm_compatibility.py`)

## Bob Status
- ✅ Working correctly with cloud-pro (MiniMax) after `tool_call_id` fix
- ✅ Working correctly with local-coder (qwen) after text parsing fix
- Bob can review code and provide detailed feedback

## Pending Refactoring (see plan.txt)
- Logger.py thread-safety issues (use LoggerAdapter or try/finally)

## Documentation
- ✅ readme.md updated to reflect current `llm/` package structure
