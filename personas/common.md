# Common Guidance

Shared principles for all personas in the Harness framework.

## Information Organization

- **Single Source of Truth**: Keep configuration and facts in their authoritative source (config files, architecture docs). Don't duplicate.
- **Reference Over Copy**: When a fact exists in a config file or doc, reference the path rather than copying the data.
- **Doc Purpose**: Architecture docs describe structure and intent. Dynamic or operational state goes in memory.md.
- **Memory.md**: Stores personal context, preferences, dynamic state, and working knowledge that evolves.
- **When Corrected**: Update the relevant document in place. Replace outdated info, don't just append.

## Memory System

When I learn something new or am corrected, update the appropriate file:
- Personal preferences, location, relationships → memory.md (Personal section)
- Voice/tone corrections → memory.md (Voice section)
- Task process improvements → memory.md (Process section)
- Infrastructure facts → architecture docs or config files
- People and relationships → memory.md (People section)

## Harness Integration

Personas are stored in `personas/<name>/` relative to the Harness project root.
Add ./common.md to your context by referencing it in your persona.