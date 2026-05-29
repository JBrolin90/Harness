# Long-Term Memory Instructions

## Core Principles

- **Single Source of Truth**: Keep configuration and facts in their authoritative source (config files, architecture docs). Don't duplicate.
- **Reference Over Copy**: When a fact exists in a config file or doc, reference the path rather than copying the data.
- **Doc Purpose**: Architecture docs describe structure and intent. Dynamic or operational state goes in memory.
- **When Corrected**: Update the relevant document in place. Replace outdated info, don't just append.

## What to Store

- **User Preferences**: Coding style, tools, frameworks, working hours, communication style
- **Project Context**: Current project structure, key decisions and their rationale, recurring issues and solutions
- **Personal Knowledge**: User's domain expertise, technical skills level, learning goals
- **Session Summaries**: Important outcomes, unresolved issues, follow-up items

## When to Use Memory

- **On session start**: Check if relevant context exists before asking basic questions
- **When context is ambiguous**: Use stored preferences to resolve uncertainty
- **When user references past content**: Retrieve and confirm understanding
- **Before suggesting common solutions**: Match against known user preferences

## Maintenance Rules

When I learn something new or am corrected, update the appropriate section:
- Personal preferences, location, relationships → Personal section
- Voice/tone corrections → Voice section
- Task process improvements → Process section
- Infrastructure facts → architecture docs or config files
- People and relationships → People section

**Additional maintenance**:
- Keep current: Update immediately when preferences or context change
- Be concise: Store facts as bullet points, not essays
- Verify periodically: Ask "Is this still accurate?" for key facts

## Storage Format

```markdown
## Personal
- [personal facts, preferences, relationships]

## Voice
- [communication style, tone preferences]

## Process
- [workflow preferences, task handling patterns]

## Active Projects
- project-name: [brief description, key files, current status]

## Preferences
- [preference]: [value]

## Knowledge Base
- [concept]: [user's understanding/notes]
```