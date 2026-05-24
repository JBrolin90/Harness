# Sue's Engineering Memory

## Framework Architecture

### Core Components
- **controller.py**: HarnessController orchestrates the ReAct loop. Single tool execution per iteration for smaller model compatibility.
- **brain.py**: call_llm() handles API calls. Supports MiniMax and Ollama providers.
- **tools.py**: execute_tool() runs !READ, !WRITE, !EDIT, !BASH, !LS. Path validation prevents directory traversal.
- **context.py**: ContextManager tracks topics and detects memory file updates to avoid redundant history.

### Design Decisions

#### Why Serial Execution?
Parallel tool execution sounds better but requires larger context windows and more complex prompt engineering. For 1.5B-7B models, serial execution with focused prompts works better. The framework supports both - serial is default.

#### Why Regex-Based Tool Detection?
Typed tool calling (like OpenAI's function calling) requires API support and larger models. Regex parsing works with any LLM that can output structured text. The delimiter format (<<<BLOCK>>>) provides clear boundaries for complex content.

#### Why persona.memory.md for persistence?
Personas manage their own memory via common.md instructions. Harness loads memory at session start and detects memory updates to avoid duplicating in conversation history. This keeps the persona in control while Harness provides infrastructure.

## Known Issues & Solutions

### Path Validation Bug (Fixed)
_validate_path() could raise UnboundLocalError if _validate_path() failed in !WRITE/!EDIT exception handlers. Solution: catch ValueError separately before main try block.

### Reflection vs Persona Memory Conflict
Earlier design had harness LLM reflection write to memory files directly. This conflicted with common.md instructions. Solution: persona manages memory via tools, harness just detects updates to avoid history redundancy.

## Best Practices

### Testing
- Mock at boundaries: patch call_llm, not internal functions
- Controller tests use enable_context=False to isolate tool testing
- Each tool command has unit tests in test_tools.py
- Context manager has dedicated test file

### Error Handling
- Path validation errors return clean error strings, not exceptions
- Tool execution wraps in try/except at execute_tool level
- LLM errors caught and returned as error strings

### Persona Development
- Start with common.md principles
- Keep persona.md focused on role and approach
- memory.md for persistent state, not static facts
- Reference ./common.md in every persona

## Python Patterns That Work

### Context Managers
```python
with patch('module.function') as mock:
    # test code
```

### Fixture Isolation
Each test class should have clean fixture setup. Avoid shared state between tests.

### Mock Side Effects
For sequential responses, use `mock_call_llm.side_effect = [resp1, resp2, resp3]`

## Git Configuration

### SSH for GitHub
Always use SSH for pushing to GitHub:
```bash
git remote set-url origin git@github.com:JBrolin90/Harness.git
```

## Future Considerations

### Dual Execution Modes
Small models (1.5B-3B): Serial execution, simple prompts
Large models (7B+): Parallel execution, complex prompts
Configurable via execution_mode on ProviderConfig

### Memory Summarization
Long conversations may need summarization to stay within context limits. Consider periodic compression of conversation_history.

### Multi-Agent Support
Current architecture is single-agent. Future could support agent collaboration with shared context.