# Common Guidance

Shared principles for all personas in the Harness framework.

## Information Organization

- **Single Source of Truth**: Keep configuration and facts in their authoritative source (config files, architecture docs). Don't duplicate.
- **Reference Over Copy**: When a fact exists in a config file or doc, reference the path rather than copying the data.
- **Doc Purpose**: Architecture docs describe structure and intent. Dynamic or operational state goes in memory.md.
- **project.md**: Located in the Current Working Directory (CWD). Use this file to store and maintain project-specific facts, technical architecture, and progress. This is the shared source of truth for the project context.
- **Memory.md**: Stores personal context, preferences, dynamic state, and working knowledge that evolves.
- **When Corrected**: Update the relevant document in place. Replace outdated info, don't just append.

## File Modification Permissions

- **Immutable Files**: Do NOT modify `common.md`, `persona.md`, or `AGENT.md` unless explicitly instructed by Joachim to do so. These are framework and persona definitions, not scratchpads.
- **Authoritative Sources**: Never delete or truncate configuration files (e.g., YAML, JSON, .conf) under the guise of "memory cleanup." Cleanup only applies to `memory.md` and `project.md`.
## Memory System

When I learn something new or am corrected, update the appropriate file:
- Personal preferences, location, relationships → memory.md (Personal section)
- Voice/tone corrections → memory.md (Voice section)
- Task process improvements → memory.md (Process section)
- Infrastructure facts → architecture docs or config files
- People and relationships → memory.md (People section)

### Data Ingestion Policy

- **No Mirroring**: Do not copy data from external tools, APIs (e.g., Home Assistant), or other local files into your `memory.md`. 
- **Reference Logic**: Instead of storing values, store the *method* to retrieve them (e.g., "Check `!BASH ha state get...` for light status") or the file path where the data lives.
- **Summarization**: If a project-related fact is discovered, move it to `project.md` in the CWD, not your personal memory.

## Harness Integration

Personas are stored in `personas/<name>/` relative to the Harness project root.
Add ./common.md to your context by referencing it in your persona.