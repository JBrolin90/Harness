# Harness

A lightweight, modular ReAct-style autonomous agent framework. It supports multiple LLM providers (OpenAI, Ollama, MiniMax, OpenRouter) and features a multi-stage tool dispatch pipeline that handles JSON, XML, and code block formats.

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Setup](#setup)
- [Usage](#usage)
- [Tools](#tools)
- [Adding New Tools](#adding-new-tools)
- [Testing](#testing)
- [Project Structure](#project-structure)

---

## Features

- **Multi-Provider Support** — Seamlessly switch between local models (Ollama) and cloud APIs (MiniMax, OpenRouter). Provider configs are stored in `providers.json`.
- **Auto-Registering Tools** — Subclass `BaseTool` and the tool is automatically discovered and passed to the LLM.
- **Multi-Format Tool Parsing** — `tool_dispatch.py` handles 7 formats: JSON code blocks, bare JSON, simple `{"tool"/"args"}` JSON, bash/sh code blocks, colon-XML, `<tool_call>...</tool_call>` XML, and plain XML.
- **Explicit Result Types** — `ToolResult` (truthy, continues loop) and `SystemError` (falsy, stops loop) make the ReAct loop behavior unambiguous.
- **Path Sandboxing** — File operations are validated to stay within the working directory.
- **Context Awareness** — Automatically ingests `AGENT.py` from the current directory for project-specific instructions.
- **Modular Design** — `brain.py` handles LLM communication, `tool_dispatch.py` parses and executes tools, `controller.py` orchestrates the loop with full conversation history.

---

## Architecture

```
User
 └─ bob.py (CLI entry point)
     └─ HarnessController (controller.py)
         ├─ brain.py                      → LLM API call + provider dispatch
         │   ├─ _handle_openai_style_response  (MiniMax / OpenAI / OpenRouter)
         │   └─ _handle_ollama_response        (Ollama)
         │
         └─ tool_dispatch.py               → 7-parser pipeline → _safe_dispatch
             └─ tools/
                 ├─ base_tool.py           → BaseTool ABC + ToolsManager metaclass
                 ├─ standard_tools.py      → read_file, write_file, edit_file, list_files
                 ├─ bash_tool.py           → bash (whitelist + interactive approval)
                 └─ modelName_tool.py      → get_model_name
```

---

## Setup

**1. Install dependencies:**

```bash
pip install -r requirements.txt
```

Requirements: `requests`, `pytest`.

**2. Configure providers:**

Edit `providers.json` to add API keys, model preferences, and URLs. Each provider maps an environment variable to an API key.

```bash
export MINIMAX_API_KEY="your-key-here"
export OPENROUTER_API_KEY="your-key-here"
```

**Default providers:**
- `cloud-pro` — MiniMax API
- `local-coder` — Ollama at localhost

**User providers** (pre-configured in `providers.json`):
- Various OpenRouter models (Poolside, DeepSeek, Gemma, Qwen)
- Local Ollama models (Qwen2.5-coder variants, Llama3.2, DeepSeek-Coder, Gemma4)

**3. Run:**

```bash
python bob.py --provider cloud-pro
```

---

## Usage

### CLI

```bash
python bob.py                    # defaults to cloud-pro
python bob.py --provider local-coder
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
ctrl.run_task("List files in the current directory")
ctrl.reset()  # clear conversation history
```

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

**Security:**
- **Path sandboxing** — All file operations validated to stay within `os.getcwd()`.
- **Bash whitelist** — Safe commands (`ls`, `cat`, `grep`, `find`, `pwd`, `head`, `tail`, `wc`, `sort`, `uniq`, `mkdir`, `cp` with no `-t`/`--target-directory`, `mv` with no `-t`/`--target-directory`, `rm` only with `-r` or `-f`) execute without confirmation. Non-whitelisted commands require TTY approval.

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

---

## Testing

```bash
python3 -m pytest -v
```

Test files:
- `test_bob.py` — CLI entry point
- `test_controller.py` — Controller logic and module-level functions
- `test_brain.py` — LLM response parsing and API call handling
- `test_tool_dispatch.py` — All 7 parser functions, parameter normalization, result types
- `test_tools.py` — Tool definitions and path validation

---

## Project Structure

```
Harness/
├── AGENT.py                  # Directory-specific instructions (auto-ingested)
├── bob.py                    # CLI entry point
├── brain.py                  # LLM API handler (unified call_llm)
├── controller.py             # HarnessController (ReAct loop orchestrator)
├── provider.py               # ProviderConfig + ProviderManager
├── providers.json            # User-defined provider configs
├── systemprompt.py           # Dynamic system prompt builder
├── terminal_history.py       # Readline history upgrade
├── tool_dispatch.py          # Tool call parser + dispatcher + result types
│
├── test_bob.py
├── test_brain.py
├── test_controller.py
├── test_tool_dispatch.py
├── test_tools.py
│
├── tools/
│   ├── __init__.py           # Auto-imports all tools to trigger registration
│   ├── base_tool.py          # BaseTool ABC + ToolsManager metaclass + dispatch
│   ├── standard_tools.py     # ReadFileTool, WriteFileTool, EditFileTool, ListFilesTool
│   ├── bash_tool.py          # BashTool (whitelist + interactive approval)
│   ├── modelName_tool.py     # GetModelNameTool
│   └── core_config.py        # set_current_provider helper for tools
│
├── requirements.txt
└── README.md
```

---

## Module Reference

**`controller.py`** — `HarnessController`
```python
ctrl = HarnessController(provider_name="cloud-pro")
ctrl.run_task(prompt, max_iterations=10)  # returns final LLM response
ctrl.reset()                              # clear conversation history
```

**`brain.py`** — `call_llm`
```python
response = call_llm(history, system_prompt, config)  # config: ProviderConfig
```

Handles both OpenAI-style APIs and Ollama. Malformed API responses return explicit `[BRAIN ERROR: ...]` strings rather than silently falling back to empty strings.

**`tool_dispatch.py`** — `tool_dispatch`
```python
result = tool_dispatch(response_text)
# Returns: ToolResult(tool_name, output)  → truthy, loop continues
#          SystemError(message)            → falsy, loop stops
#          None                            → no tool call found, loop stops
```

`ToolResult` and `SystemError` implement `__bool__` for clean truthy/falsy checks in the controller loop, and `__str__` for string output.

**`provider.py`** — `ProviderManager`
```python
pm = ProviderManager()
pm.list_providers()           # ['cloud-pro', 'local-coder', ...]
pm.get_provider("cloud-pro")  # ProviderConfig instance
pm.add_provider(config)       # add custom provider at runtime
```
