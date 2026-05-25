# Harness Project Log

## Session Persistence (2025-06-23)

### Feature: Conversation History to JSON

**Implemented**: Session files that persist conversation history to disk.

**Filename format**: `session-<YYYYMMDD>-<cwd_with_/_replaced_by_>_.json`
- Example: `session-20250623-_home_joachim_lab_prj_Harness.json`

**Implementation**:
- `_get_session_file_path()` - Generates unique session filename based on date and CWD
- `_save_session()` - Writes `conversation_history` to JSON file with error handling
- Saves after initial user/assistant exchange
- Saves after each ReAct loop iteration
- `reset()` - Removes session file on session reset

**Location**: `controller.py` - `HarnessController` class

**Error handling**: Non-blocking - prints warning if file write fails but doesn't crash