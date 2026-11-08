# Architecture Decision Records

One file per decision, numbered, never edited after acceptance — supersede instead. This replaces
the narrative decision log the memory bank used to hold: same information, minus the session
history.

| # | Decision | Status |
|---|---|---|
| [0001](0001-rewrite-plugin-first.md) | Rewrite plugin-first instead of script-first | accepted |
| [0002](0002-drop-ai-scaffolding.md) | Drop the AI-added backup, watchstate and cron scaffolding | accepted |

## Template

```md
# NNNN — Title

- **Status:** proposed | accepted | superseded by NNNN
- **Date:** YYYY-MM-DD
- **Supersedes:** —

## Context
What forced a decision. Facts with proof, not narrative.

## Decision
The choice, in one paragraph, stated so it can be violated.

## Consequences
What gets easier, what gets harder, what we are knowingly giving up.
```
