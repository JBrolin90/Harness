# Harness

A lightweight, modular ReAct-style autonomous agent framework. It supports multiple LLM providers (OpenAI, Ollama, MiniMax, OpenRouter) and features structured native tool calling with optional text-based fallback parsing for smaller models.

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Setup](#setup)
- [Usage](#usage)
- [Provider Configuration](#provider-configuration)
- [Tools](#tools)
- [Adding New Tools](#adding-new-tools)
- [Testing](#testing)
- [Project Structure](#project-structure)

---

## Features

### Multi-Provider Support
Seamlessly switch between local models (Ollama) and cloud APIs (MiniMax, OpenRouter). Provider configs are stored in `providers.json` with attributes for fine-grained control.

### Debug Logging
Configurable debug logging to file (`harness_debug.log`) without polluting stdout. Enable via `--debug` flag or `HARNESS_DEBUG` environment variable. Includes timestamp, module name, and log level.

### Structured Native Tool Calling
Large/cloud models (MiniMax-M2.7, gemma4:e4b) use the API's native `tool_calls` structure — the model outputs structured JSON, not text to be parsed. This is the preferred mode for models that support it.

### Optional Text Parsing Fallback
Smaller models (qwen2.5-coder variants) that don't properly use structured tool calls can parse tool calls from text formats. Enable via `text_parse_*` attributes in provider config.

### Multi-Format Parsers (7 formats)
When text parsing is enabled, `dispatch_with_text_parsing()` handles:
1. `json-codeblock` — JSON inside ```json ... ```
2. `json-raw` — Bare JSON object `{...}`
3. `simple-json` — `{"tool": ..., "args": {...}}`
4. `bash-block` — ```bash ... ``` or ```sh ... ```
5. `tool_call-xml` — `<tool_call>...</tool_call>` with `<arg_key>/<arg_value>`
6. `colon-xml` — `<tool>:{...}</tool>`
7. `plain-xml` — `<tool>value</tool>`

### Provider Recommendations
`provider-recommendations.json` provides baseline attributes for each provider — text parsing flags, small model guidance, etc.

### Explicit Result Types
- `ToolResult` (truthy) — tool executed, loop continues
- `SystemError` (falsy) — error, loop stops  
- `NoToolFound` (falsy) — no tool call found, loop stops

Result types implement `__bool__` for clean ReAct loop checks.

### Multi-Tool Call Detection
When a response contains multiple tool calls, the system returns `SystemError` requiring user confirmation before proceeding.

### Small Model Guidance Control
System prompt includes extra guidance (response format, code review instructions) for smaller models. Control via `enable_small_model_guidance` attribute.

### Auto-Registering Tools
Subclass `BaseTool` and the tool is automatically discovered and passed to the LLM.

### Path Sandboxing
File operations validated to stay within working directory.

### Context Awareness
Automatically ingests `AGENT.py` and `memory_instructions.md` for project-specific instructions.

---

## Architecture

```
User
 └─ bob.py (CLI entry point)
     └─ HarnessController (controller.py)
         ├─ brain.py (LLM API calls)
         │   ├─ _handle_response (unified for OpenAI/Ollama)
         │   └─ call_llm (unified request handler)
         │
         ├─ tool_dispatch.py
         │   ├─ dispatch() — structured tool_calls only (cloud models)
         │   ├─ dispatch_with_text_parsing() — text parsing fallback (small models)
         │   ├─ _parse_xml_tool_call, _parse_colon_json_format, _parse_plain_tool_call
         │   ├─ extract_json_string, _parse_json_raw, parse_bash_command, _parse_simple_tool_json
         │   └─ _execute_call, _check_multi_tool_call
         │
         └─ systemprompt.py (dynamic prompt builder)
             └─ build_system_prompt(memory, provider_type, attributes)

ProviderManager (provider.py)
 ├─ Default providers: cloud-pro (MiniMax), local-coder (qwen2.5-coder:7b)
 └─ User providers: loaded from providers.json

tools/
 ├─ base_tool.py (BaseTool ABC + ToolsManager metaclass)
 ├─ standard_tools.py (read_file, write_file, edit_file, list_files)
 ├─ bash_tool.py (bash with whitelist + interactive approval)
 └─ modelName_tool.py (get_model_name)
```

---

## Setup

**1. Install dependencies:**

```bash
pip install -r requirements.txt
```

Requirements: `requests`, `pytest`.

**2. Configure API keys:**

```bash
export MINIMAX_API_KEY="your-key-here"
export OPENROUTER_API_KEY="your-key-here"
# Ollama models use OLLAMA_DUMMY_KEY (placeholder, not used)
```

**3. Run:**

```bash
python bob.py --provider cloud-pro          # MiniMax-M2.7 (structured tool calls)
python bob.py --provider local-coder        # qwen2.5-coder:7b (text parsing enabled)
python bob.py --provider gemma4-4b-ollama   # gemma4:e4b (structured tool calls)
```

---

## Usage

### CLI

```bash
python bob.py                           # defaults to cloud-pro
python bob.py --provider local-coder     # Ollama qwen2.5-coder:7b
python bob.py --provider gemma4-4b-ollama
python bob.py --debug                    # Enable debug logging to harness_debug.log
HARNESS_DEBUG=1 python bob.py           # Enable via environment variable
HARNESS_DEBUG_LOG=/tmp/my.log python bob.py  # Custom log file path
```

### Programmatic

```python
from controller import init, run_task

init(provider_name="cloud-pro")
response = run_task("Read the contents of setup.py")
```

### Direct Controller

```python
from controller import HarnessController

ctrl = HarnessController(provider_name="ollama")
result = ctrl.run_task("List files in the current directory")
ctrl.reset()  # clear conversation history
```

---

## Provider Configuration

### Default Providers (built-in)

| Provider | Model | Tool Call Mode | Notes |
|----------|-------|---------------|-------|
| `cloud-pro` | MiniMax-M2.7 | Structured (`dispatch()`) | Cloud model, no text parsing |
| `local-coder` | qwen2.5-coder:7b | Text parsing (`dispatch_with_text_parsing()`) | Has `text_parse_json_codeblock`, `text_parse_json_raw` |

### Provider Attributes

Fine-grained control via `attributes` dict:

```json
{
  "name": "my-provider",
  "provider_type": "ollama",
  "url": "http://localhost:11434/api/chat",
  "model": "qwen2.5-coder:14b",
  "api_key_env_var": "OLLAMA_DUMMY_KEY",
  "attributes": {
    "enable_small_model_guidance": true,
    "text_parse_json_codeblock": true,
    "text_parse_json_raw": true,
    "text_parse_bash": true
  }
}
```

**Attribute flags:**

| Attribute | Purpose |
|-----------|---------|
| `enable_small_model_guidance` | Include extra system prompt guidance (response format, code review instructions) |
| `text_parse_json_codeblock` | Parse ```json ... ``` as tool call |
| `text_parse_json_raw` | Parse bare `{...}` JSON as tool call |
| `text_parse_bash` | Parse ```bash ... ``` as bash command |
| `text_parse_xml` | Parse `<tool_call>...</tool_call>` XML |
| `text_parse_colon_xml` | Parse `<tool>:{...}</tool>` |
| `text_parse_plain_xml` | Parse `<tool>value</tool>` |

### Provider Recommendations

`provider-recommendations.json` contains baseline recommendations for all providers. Attributes from this file are automatically applied to built-in providers (`cloud-pro`, `local-coder`).

User providers in `providers.json` do not automatically inherit these — apply manually or via `ProviderManager.update_provider()`.

---

## Tools

Tools are auto-registered via the `ToolsManager` metaclass — just import the module and the registry updates automatically.

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents (sandboxed to working directory) |
| `write_file` | Create or overwrite files |
| `edit_file` | Replace exact text in files (`search`/`replace`) |
| `list_files` | List directory contents |
| `bash` | Execute bash commands (whitelist or interactive approval) |
| `get_model_name` | Returns the current LLM model name |

### Security

- **Path sandboxing** — All file operations validated to stay within `os.getcwd()`.
- **Bash whitelist** — Safe commands (`ls`, `cat`, `grep`, `find`, `pwd`, `head`, `tail`, `wc`, `sort`, `uniq`, `mkdir`, `cp` without `-t`/`--target-directory`, `mv` without `-t`/`--target-directory`, `rm` only with `-r` or `-f`) execute without confirmation. Non-whitelisted commands require TTY approval.

---

## Adding New Tools

Create a class in `tools/` inheriting from `BaseTool`. It will be auto-registered and made available to the LLM.

```python
from tools.base_tool import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    parameters = {
        "type": "object",
        "properties": {"arg1": {"type": "string"}},
        "required": ["arg1"]
    }

    def execute(self, arg1: str) -> str:
        return f"Processed: {arg1}"
```

The tool is automatically:
- Registered in `BaseTool._registry` via `ToolsManager` metaclass
- Included in `get_all_instructions()` for the LLM system prompt
- Available for dispatch via `BaseTool.dispatch(name, arguments)`

---

## Testing

```bash
# Run all tests
python3 -m pytest -v

# Run specific test file
python3 -m pytest test_tool_dispatch.py -v

# Run integration test for MiniMax issue
python3 -m pytest test_minimax_review_integration.py -v

# LLM compatibility test (requires API keys)
python3 test_llm_compatibility.py
```

### Test Files

| File | Coverage |
|------|----------|
| `test_bob.py` | CLI entry point |
| `test_controller.py` | Controller logic, tool engine selection |
| `test_brain.py` | LLM response parsing, API call handling |
| `test_tool_dispatch.py` | All parsers, parameter normalization, result types |
| `test_minimax_review_integration.py` | MiniMax ` ```bash\n...\n``` ` issue |
| `test_systemprompt.py` | Dynamic system prompt building |
| `test_memory.py`, `test_memory_tool.py` | Memory system |
| `test_tools.py` | Tool definitions and path validation |

---

## Project Structure

```
Harness/
├── AGENT.md                       # Directory-specific instructions (auto-ingested)
├── AGENT.py                       # Alternative agent config
├── bob.py                         # CLI entry point
├── brain.py                       # LLM API handler (unified call_llm)
│                                  # - _handle_response (unified OpenAI/Ollama)
│                                  # - _format_tools_for_provider (MiniMax wrapping)
│                                  # - _parse_tool_calls (handles multiple formats)
│                                  # - MAX_TOOL_CALLS cap (50)
├── controller.py                  # HarnessController (ReAct loop orchestrator)
│                                  # - Auto-selects dispatch vs dispatch_with_text_parsing
│                                  # - Passes provider_type + attributes to build_system_prompt
├── provider.py                    # ProviderConfig + ProviderManager
│                                  # - _load_recommendations() from provider-recommendations.json
├── providers.json                 # User-defined provider configs
├── provider-recommendations.json  # Recommended attributes per provider
├── systemprompt.py                # Dynamic system prompt builder
│                                  # - enable_small_model_guidance control
├── terminal_history.py            # Readline history upgrade
├── tool_dispatch.py               # Tool call dispatcher
│   ├── dispatch()                 # Structured tool_calls only (cloud models)
│   ├── dispatch_with_text_parsing()  # Text parsing fallback (small models)
│   ├── _TEXT_PARSERS              # Ordered parser list with rationale docs
│   ├── _check_multi_tool_call()   # Multi-tool call detection
│   └── _execute_call()            # Exception handling (TypeError, KeyError, ValueError, general)
├── response.py                    # LLMResponse, ToolCall, ToolResult, SystemError, NoToolFound
│
├── tests/                         # Test utilities
├── test_*.py                      # Test files
│
├── tools/
│   ├── __init__.py               # Auto-imports trigger registration
│   ├── base_tool.py              # BaseTool ABC + ToolsManager metaclass + dispatch
│   ├── standard_tools.py         # read_file, write_file, edit_file, list_files
│   ├── bash_tool.py              # BashTool (whitelist + interactive approval)
│   ├── modelName_tool.py          # get_model_name
│   ├── memory_tool.py            # Memory operations
│   └── core_config.py            # set_current_provider helper
│
├── memory.md                       # Project-specific instructions (auto-ingested)
├── logger.py                       # Debug logging module
│                                  # - setup_debug_logging() for file output
│                                  # - debug/info/warning/error convenience functions
│                                  # - HARNESS_DEBUG and HARNESS_DEBUG_LOG env vars
├── requirements.txt
└── README.md
```

---

## Module Reference

### `controller.py` — `HarnessController`

```python
ctrl = HarnessController(provider_name="cloud-pro")
result = ctrl.run_task(prompt, max_iterations=25)  # returns final LLM response text
ctrl.reset()  # clear conversation history

# Access provider and tools
ctrl.current_provider  # ProviderConfig
ctrl.tool_engine       # dispatch() or dispatch_with_text_parsing()
ctrl.memory            # Memory instance
```

### `brain.py` — `call_llm`

```python
response = call_llm(history, system_prompt, config)  # config: ProviderConfig
# Returns: LLMResponse(text, tool_calls, error)
```

Handles both OpenAI-style APIs and Ollama with unified `_handle_response()`. Malformed responses return explicit `[BRAIN ERROR: ...]` in the error field.

### `tool_dispatch.py`

```python
# For structured tool calls (cloud models)
result = dispatch(response)  # LLMResponse with tool_calls
# Returns: ToolResult | SystemError | NoToolFound

# For text-based tool calls (small models)
result = dispatch_with_text_parsing(response)
# Returns: ToolResult | SystemError | NoToolFound
```

**Result types:**

```python
ToolResult(tool_name, output)  # truthy, loop continues
SystemError(message)           # falsy, loop stops
NoToolFound()                  # falsy, loop stops
```

All implement `__bool__` and `__str__` for clean ReAct loop integration.

### `provider.py` — `ProviderManager`

```python
pm = ProviderManager()
pm.list_providers()              # ['cloud-pro', 'local-coder', ...]
pm.get_provider("cloud-pro")    # ProviderConfig instance
pm.add_provider(config)          # add custom provider
pm.update_provider("name", attributes={"text_parse_json_codeblock": true})  # update in-memory
```

Built-in providers (`cloud-pro`, `local-coder`) load attributes from `provider-recommendations.json` at startup.

### `systemprompt.py` — `build_system_prompt`

```python
prompt = build_system_prompt(memory, provider_type="ollama", attributes={"enable_small_model_guidance": True})
# Returns: str system prompt
```

Includes small model guidance (response format, code review instructions) only when `enable_small_model_guidance` is `True` in attributes.