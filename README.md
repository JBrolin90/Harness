# Harness Agent Framework

A lightweight Python framework for building autonomous agents with tool-based file system and shell access.

## Overview

Harness follows a modular Brain/Hands/Controller architecture:

- **Brain** (`brain.py`) - LLM communication layer
- **Hands** (`tools.py`) - Tool execution (file ops, bash)
- **Controller** (`controller.py`) - Orchestration and ReAct loop

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up API key (for cloud models)
export MINIMAX_API_KEY="your-key-here"

# Run the agent
python3 bob.py

# Or specify a provider explicitly
python3 bob.py --provider local-coder

# Or use a different persona
python3 bob.py --persona custom
```

## Configuration

Edit `providers.json` or modify defaults in `provider.py`:

| Provider | Type | Model |
|----------|------|-------|
| cloud-pro | minimax | MiniMax-M2.7 |
| local-coder | ollama | qwen2.5-coder:7b |

## Personas

Personas define how the agent behaves and communicates. They are stored in the `personas/` directory:

```
personas/
├── common.md           # Shared principles (all personas reference this)
├── default/            # Default Bob, Software Architect
├── Diane/              # Executive Assistant
├── Hazel/              # Home Assistant Expert
├── Sue/                # Minimal persona
└── sysadmin/           # System Administrator
```

### Available Personas

| Persona | Name | Description |
|---------|------|-------------|
| default | Bob | Software and Architecture Expert |
| Diane | Diane | Executive Assistant (address as "Carl") |
| Hazel | Hazel | Home Assistant expert with memory |
| Sue | Sue | Minimal, quiet persona |
| sysadmin | Alan | System administrator for home lab |

### Creating Custom Personas

1. Create a directory: `personas/<name>/`
2. Add a `persona.md` file
3. Optionally add `memory.md` for persistent context
4. Run with `--persona <name>`

Example `personas/myrole/persona.md`:
```markdown
# Custom Persona

You are a security expert.
Add ./common.md to your context.

Your approach:
- Warn about risks before executing commands
- Prefer read-only operations
```

## Available Tools

| Command | Description |
|---------|-------------|
| `!READ /path` | Read file contents |
| `!WRITE /path <<<WRITE_BLOCK>>>content<<<` | Create/update file |
| `!EDIT /path <<<SEARCH_BLOCK>>>old<<<REPLACE_BLOCK>>>new<<<` | Edit file |
| `!BASH command` | Execute shell command (whitelisted or with approval) |
| `!LS /path` | List directory contents |

## Project Structure

```
.
├── personas/           # Persona definitions
├── bob.py              # CLI entry point
├── controller.py       # HarnessController class + ReAct loop
├── brain.py            # LLM API integration
├── tools.py            # Tool execution (READ, WRITE, EDIT, BASH, LS)
├── provider.py         # LLM provider configuration
├── AGENT.py            # AGENT.md directory-specific instructions
├── terminal_history.py # readline history support
├── test_*.py           # Test suite
└── requirements.txt    # Dependencies
```

## Testing

```bash
python3 -m pytest        # Run all tests
python3 -m pytest -v     # Verbose output
```

## Architecture Notes

- **Serial execution**: Currently one tool per LLM response (for smaller model compatibility)
- **Path validation**: Tools are restricted to current working directory
- **Bash security**: Whitelist for safe commands; human-in-the-loop gate for others
- **Persona system**: Customize via system prompt or local `AGENT.md` file

## Extending

To add new tools:
1. Add tool instruction to `get_tools_instructions()` in `tools.py`
2. Add regex pattern to `regex_map` in `controller.py`
3. Add execution logic to `execute_tool()` in `tools.py`
4. Add tests