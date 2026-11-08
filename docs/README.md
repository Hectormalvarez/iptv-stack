# Documentation

Engineering docs for the iptv-stack rebuild. Terse and factual: **no session logs, no
narrative history**. Decisions live in `../adr/`, current state lives in `plan.md`.

| Doc | Answers |
|---|---|
| [platform.md](platform.md) | What Dispatcharr 0.30.0 already gives us — REST API, plugin system, event bus, plugin store |
| [architecture.md](architecture.md) | What we are building, and where each kind of code is allowed to live |
| [inventory.md](inventory.md) | What exists today: line counts, disposition, old → new mapping |
| [invariants.md](invariants.md) | Provider / EPG / client facts that survive any rewrite |
| [plan.md](plan.md) | Phases, exit criteria, live status, rollback |
| [../adr/](../adr/) | One file per decision, with the reason — not just the change |

## Rules

1. One fact, one place. Link instead of repeating.
2. Any claim about provider or platform behaviour carries its proof: the command, the
   `file:line`, or the API response that shows it.
3. No credentials, tokens, or provider URLs containing user/pass — in any doc, ever.
4. A new decision → a new ADR. `plan.md` status is the only section expected to change weekly.
5. When code and docs disagree, the code is wrong or the doc gets fixed. There is no third state.

## Legacy docs (frozen, do not extend)

- `docs/reference.md` — the 1,296-line session-era deep dive. Still the operational runbook
  until Phase 5; its durable facts are being lifted into `invariants.md`.
- `memory-bank/` — narrative session + decision log from the pre-rewrite codebase.

Both are preserved by the `legacy/pre-rewrite-2026-11-07` tag and are deleted in Phase 5,
once `invariants.md` is confirmed to carry everything worth keeping.
