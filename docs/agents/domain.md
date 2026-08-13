# Domain Docs

How engineering skills should consume this repository's domain documentation when exploring the codebase.

## Before exploring, read these

- `CONTEXT.md` at the repository root.
- `docs/adr/` for decisions relevant to the area being changed.

If any of these files do not exist, proceed silently. Do not suggest creating them up front; create them only when the domain vocabulary or an architectural decision needs to be recorded.

## File structure

This repository uses a single-context layout:

```text
/
├── CONTEXT.md
├── docs/
│   └── adr/
└── src/
```

## Use the glossary's vocabulary

When naming a domain concept in an issue title, a refactor proposal, a hypothesis, or a test, use the term defined in `CONTEXT.md`. If the relevant concept is missing, note the gap for domain modeling rather than casually introducing a competing synonym.

## Flag ADR conflicts

When a proposed change conflicts with an existing ADR, surface the conflict explicitly instead of silently overriding the decision.
