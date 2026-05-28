# Harness - AI Agent Framework

Harness is a modular AI agent framework that provides a ReAct (Reasoning + Acting) loop for interfacing with Large Language Models (LLMs). It supports multiple LLM providers, tool-based interactions, and conversation management.

## Overview

Harness enables AI agents to:
- **Connect to multiple LLM providers** (MiniMax, OpenRouter, Ollama)
- **Execute tools** (file operations, bash commands) in a secure sandbox
- **Maintain conversation context** across multiple turns
- **Parse tool calls** from various LLM response formats (JSON, XML, code blocks)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                          User                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    bob.py (CLI)                             │
│                Entry point for user interaction             │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              HarnessController (controller.py)              │
│  - Manages conversation history                             │
│  - Orchestrates the ReAct loop                              │
│  - Routes LLM calls and tool executions                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
┌─────────────────┐     ┌─────────────────────────────────┐
│  brain.py       │     │        tool_dispatch.py         │
│  - LLM API call │     │   - Parses tool calls from      │
│  - Handles both │     │     LLM responses (JSON/XML/    │
│    OpenAI-style │     │     code blocks)                │
│    and Ollama   │     │   - Dispatches to tool handlers │
│    formats      │     └────────────────┬────────────────┘
└─────────────────┘                      │
                                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    tools/                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ base_tool.py│  │standard_tools│ │ bash_tool.py│          │
│  │ - ABC       │  │ - read_file │  │ - bash      │          │
│  │ - Registry  │  │ - write_file│  │             │          │
│  │ - Dispatch  │  │ - edit_file │  └─────────────┘          │
│  └─────────────┘  │ - list_files│                           │
│                   └─────────────┘                           │
└─────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    provider.py                              │
│  - ProviderConfig (dataclass)                               │
│  - ProviderManager (loads/stores provider configs)          │
│  - providers.json (user-added providers)                    │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### `controller.py` - HarnessController
The main orchestrator class managing the agent loop:

```python
from controller import HarnessController

ctrl = HarnessController(provider_name="cloud-pro")
response = ctrl.run_task("Your prompt here")
```

**Key methods:**
- `run_task(prompt)` - Execute a task with the given prompt, returns final response
- `reset()` - Clear conversation history to start fresh

### `brain.py` - LLM Interface
Handles unified communication with LLM providers:

```python
from brain import call_llm

response = call_llm(history, system_prompt, config)
```

Supports both OpenAI-style APIs (MiniMax, OpenRouter) and Ollama local models.

### `tool_dispatch.py` - Tool Call Parser
Parses tool calls from LLM responses in multiple formats:

1. **JSON in code blocks** - ` ```json {"name": "...", "arguments": {...}} ``` `
2. **Raw JSON** - `{"name": "...", "arguments": {...}}`
3. **XML format** - `<tool_call>read_file<arg_key>path</arg_key><arg_value>file.txt</arg_value></tool_call>`
4. **Colon format** - `<tool_name>name:{args}/>`
5. **Simple XML** - `<read_file>path</read_file>`
6. **Bash in code blocks** - ` ```bash ls -la ``` `

### `provider.py` - Provider Management
Manages LLM provider configurations:

```python
from provider import ProviderManager

pm = ProviderManager()
providers = pm.list_providers()  # ['cloud-pro', 'local-coder', ...]
config = pm.get_provider("cloud-pro")
```

**Default Providers:**
- `cloud-pro` - MiniMax API (`MINIMAX_API_KEY`)
- `local-coder` - Ollama at localhost (`OLLAMA_DUMMY_KEY`)

**User Providers** (in `providers.json`):
- Various OpenRouter models (Poolside, DeepSeek, Gemma, Qwen)
- Local Ollama models (Qwen2.5-coder variants, Llama3.2, DeepSeek-Coder, Gemma4)

## Tools System

### `tools/base_tool.py` - Base Tool Architecture
Uses `ToolsManager` metaclass for auto-registration:

```python
from tools.base_tool import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "Description of what it does"
    parameters = {
        "type": "object",
        "properties": {"arg1": {"type": "string"}},
        "required": ["arg1"]
    }
    
    def execute(self, arg1: str) -> str:
        return f"Executed with {arg1}"
```

### Available Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents (sandboxed to working directory) |
| `write_file` | Create or overwrite files |
| `edit_file` | Replace exact text in files |
| `list_files` | List directory contents |
| `bash` | Execute bash commands (whitelist or user-approved) |
| `get_model_name` | Get current LLM model name |

### Security Features

- **Path validation** - All file operations validated to stay within working directory
- **Bash whitelist** - Safe commands (`ls`, `cat`, `grep`, etc.) execute without prompt
- **Interactive approval** - Non-whitelisted commands require user confirmation via TTY

## Usage

### CLI Entry Point

```bash
# Use default provider (cloud-pro)
python bob.py

# Use specific provider
python bob.py --provider local-coder
```

### Programmatic Usage

```python
from controller import init, run_task

# Initialize
init(provider_name="cloud-pro")

# Run tasks
response = run_task("Hello, what can you do?")
response = run_task("Read the contents of setup.py")
```

### Module-Level Functions

```python
from controller import HarnessController

# Direct instantiation for more control
ctrl = HarnessController(provider_name="ollama")
ctrl.run_task("List files in current directory")
ctrl.reset()  # Clear history
```

## Configuration

### Environment Variables

Set API keys before running:

```bash
export MINIMAX_API_KEY="your-key-here"
export OPENROUTER_API_KEY="your-key-here"
```

### Adding Providers

Edit `providers.json` or use `ProviderManager.add_provider()`:

```python
from provider import ProviderConfig, ProviderManager

config = ProviderConfig(
    name="my-provider",
    provider_type="openai",
    url="https://api.example.com/v1/chat/completions",
    model="my-model",
    api_key_env_var="MY_API_KEY",
    attributes={"stream": False}
)

pm = ProviderManager()
pm.add_provider(config)
```

## Testing

Run tests with pytest:

```bash
pytest -v
```

**Test files:**
- `test_bob.py` - CLI entry point tests
- `test_controller.py` - Controller logic tests
- `test_tools.py` - Tool definitions and path validation
- `test_tool_dispatch.py` - Tool call parsing tests

## Dependencies

```
requests>=2.28.0
pytest>=7.0.0
```

Install with:
```bash
pip install -r requirements.txt
```

## Project Structure

```
Harness/
├── AGENT.py              # Directory-specific instructions ingestion
├── bob.py                # CLI entry point
├── brain.py              # LLM API handler
├── controller.py         # Main agent controller (HarnessController)
├── provider.py           # Provider configuration management
├── providers.json        # User-defined provider configs
├── systemprompt.py       # Dynamic system prompt builder
├── terminal_history.py   # Readline history upgrade
├── tool_dispatch.py      # Tool call parser and dispatcher
├── requirements.txt     # Dependencies
├── test_*.py            # Unit tests
└── tools/
    ├── __init__.py
    ├── base_tool.py      # BaseTool ABC and ToolsManager metaclass
    ├── bash_tool.py      # Bash execution tool
    ├── core_config.py    # Provider config access for tools
    ├── modelName_tool.py # Model name introspection tool
    └── standard_tools.py # File manipulation tools
```

## License

See project repository for license information.