# Harness

A lightweight, modular ReAct-style autonomous agent framework. It supports multiple LLM providers (OpenAI, Ollama, MiniMax, OpenRouter) and features a multi-stage tool dispatch pipeline that handles JSON, XML, and code block formats.

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Setup](#setup)
- [Usage](#usage)
- [Tools](#tools)
- [Adding New Tools](#adding-new-tools)
- [Configuration](#configuration)
- [Memory System](#memory-system)
- [Testing](#testing)
- [Project Structure](#project-structure)

---

## Features

- **Multi-Provider Support** — Seamlessly switch between local models (Ollama) and cloud APIs (MiniMax, OpenRouter). Provider configs are stored in `providers.json`.
- **Auto-Registering Tools** — Subclass `BaseTool` and the tool is automatically discovered and passed to the LLM.
- **Multi-Format Tool Parsing** — `tool_dispatch.py` handles 7 formats: JSON code blocks, bare JSON, simple `{"tool"/"args"}` JSON, bash/sh code blocks, colon-XML, `<tool_call>...</tool_call>` XML, and plain XML.
- **Explicit Result Types** — `ToolResult` (truthy, continues loop) and `SystemError` (falsy, stops loop) make the ReAct loop behavior unambiguous.
- **Path Sandboxing** — File operations are validated to stay within the working directory.
- **Configuration System** — `config.py` searches predefined directories (`~/.config/harness`, `/etc/harness`, `.`) for config files, loaded at startup.
- **Long-Term Memory** — Agent can store, update, and retrieve facts across sessions via `memory.md`.
- **Modular Design** — `brain.py` handles LLM communication, `tool_dispatch.py` parses and executes tools, `controller.py` orchestrates the loop with full conversation history.

---

## Architecture

```
User
 └─ bob.py (CLI entry point)
     └─ HarnessController (controller.py)
         ├─ _preload_system_prompt()    → Load config at startup
         ├─ brain.py                    → LLM API call + provider dispatch
         │   ├─ _handle_openai_style_response  (MiniMax / OpenAI / OpenRouter)
         │   └─ _handle_ollama_response        (Ollama)
         │
         └─ tool_dispatch.py            → 7-parser pipeline → _safe_dispatch
             └─ tools/
                 ├─ base_tool.py           → BaseTool ABC + ToolsManager metaclass
                 ├─ standard_tools.py      → read_file, write_file, edit_file, list_files
                 ├─ bash_tool.py           → bash (whitelist + interactive approval)
                 ├─ memory_tool.py         → memory add/update/delete/read
                 ├─ config_reader_tool.py  → read config files via config.py
                 └─ modelName_tool.py     → get_model_name
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
| `memory` | Add/update/delete memory items (action: add/update/delete, section, item, old_item) |
| `memory_read` | Read all current memory entries |
| `config_reader` | Read a config file from predefined directories |
| `get_model_name` | Returns the current LLM model name |

**Security:**
- **Path sandboxing** — All file operations validated to stay within `os.getcwd()`.
- **Bash whitelist** — Safe commands (`ls`, `cat`, `grep`, `find`, `pwd`, `head`, `tail`, `wc`, `stat`, `diff`) execute without confirmation. Non-whitelisted commands require TTY approval.

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

## Configuration

The `config.py` module searches for files in this order of priority:

1. `~/.config/harness/` (user config)
2. `/etc/harness/` (system config)
3. `.` (current working directory)

Files loaded at startup:
- `AGENT.py` — Project-specific instructions for the agent
- `memory_instructions.md` — Instructions for the memory system

---

## Memory System

The agent maintains long-term memory in `memory.md` (project-level, currently in cwd). Memory is organized into sections:

| Section | Purpose |
|---------|---------|
| Personal | User preferences, facts, relationships |
| Voice | Communication style, tone preferences |
| Process | Workflow preferences, task handling patterns |
| Active Projects | Current work, key files, status |
| Preferences | Specific preference values |
| Knowledge Base | Concepts and user's understanding/notes |

The agent uses `memory`, `memory_update`, and `memory_delete` tools to manage memory. See `memory_instructions.md` for detailed guidelines.

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
- `test_memory.py` — Memory class functionality
- `test_memory_tool.py` — Memory tool add/update/delete/read operations
- `test_systemprompt.py` — System prompt builder
- `test_tools.py` — Tool definitions and path validation

---

## Project Structure

```
Harness/
├── AGENT.py                  # Directory-specific instructions (auto-ingested)
├── agent.py                  # Agent config loader (loads AGENT.py via config.py)
├── config.py                 # Config file loader (searches predefined dirs)
├── memory.py                 # Memory class for long-term storage
├── memory_instructions.md    # Memory system guidelines for the agent
├── memory.md                 # Memory storage file
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
├── test_memory.py
├── test_memory_tool.py
├── test_systemprompt.py
├── test_tool_dispatch.py
├── test_tools.py
│
├── tools/
│   ├── __init__.py           # Auto-imports all tools to trigger registration
│   ├── base_tool.py          # BaseTool ABC + ToolsManager metaclass + dispatch
│   ├── standard_tools.py     # ReadFileTool, WriteFileTool, EditFileTool, ListFilesTool
│   ├── bash_tool.py          # BashTool (whitelist + interactive approval)
│   ├── memory_tool.py        # MemoryTool + MemoryReadTool
│   ├── config_reader_tool.py # ConfigReaderTool
│   └── modelName_tool.py     # GetModelNameTool
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

**`config.py`** — `load`
```python
content = config.load("AGENT.py")  # returns file contents or ""
```

Searches `~/.config/harness`, `/etc/harness`, and `.` in order.

**`memory.py`** — `Memory`
```python
memory = Memory()                    # defaults to cwd/memory.md
memory.add(section, item)            # add item to section
memory.update(section, old, new)     # update item
memory.remove(section, item)         # delete item
memory.get(section)                  # get all items in section
memory.find(query)                   # search across sections
memory.get_all()                     # get all memory as dict
memory.has_content()                 # check if memory has any content
```

**`provider.py`** — `ProviderManager`
```python
pm = ProviderManager()
pm.list_providers()           # ['cloud-pro', 'local-coder', ...]
pm.get_provider("cloud-pro")  # ProviderConfig instance
pm.add_provider(config)       # add custom provider at runtime
```
