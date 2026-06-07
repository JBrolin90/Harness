# Harness Project

## Current Branch: bugfix/loop-detection (not yet merged to dev)

## Release 0.4.0 (2026-06-07)

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

### Bug Fixes (in dev)
- **tool_call_id not extracted**: Fixed `llm/tool_call_parser.py` to extract and pass `id` field from tool calls.
- **empty choices array**: Fixed `llm/brain.py` to handle empty choices gracefully.
- **provider recommendations path**: Fixed `llm/provider.py` to use absolute path.
- **text parsing not used for local-coder**: Fixed `task/task.py` to use `execute_tools` for text parsing.
- **JSON parser wrong format**: Fixed `extract_json_string` and `_parse_simple_tool_json` to handle `{"tool": ...}` format.
- **local-coder wrong URL**: Fixed `llm/provider.py` to use `lmde` instead of `localhost` for local-coder provider.

### Bug Fixes (merged to dev)
- **repetition detection for text-based tool calls**: Fixed `task/repetition_detector.py` to extract tool name from JSON text even when `has_tool_calls=False`. Prevents models from getting stuck in loops calling the same tool repeatedly.

### Known Issues
- `tests/test_llm_compatibility.py` has pre-existing import error (`build_system_prompt` not found in `systemprompt.py`)
- **local-coder (qwen) model hallucinations**: qwen2.5-coder may hallucinate tool names. See plan.txt for proposed `system_prompt_additions` attribute fix.

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
- ✅ Working correctly with cloud-pro (MiniMax)
- ✅ Working correctly with local-coder (qwen) for tool execution
- ⚠️ Loop detection was not catching repeated JSON tool calls (fixed in bugfix/loop-detection)

## Pending Refactoring (see plan.txt)
- Logger.py thread-safety issues (use LoggerAdapter or try/finally)
- system_prompt_additions attribute for qwen model guidance

## Documentation
- ✅ readme.md updated to reflect current `llm/` package structure