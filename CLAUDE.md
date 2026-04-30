# Selenite — Claude Code Workflow

## Roles

| Agent | Responsibility |
|---|---|
| **Claude Code** | Architecture, planning, task specification, monitoring, verification, QA, user prompts |
| **Codex CLI** | Implementation — receives explicit, compact task specs from Claude Code |
| **Gemini Code Assist** | Debugging — receives issue inventories from Claude Code |

## Phase Lifecycle

1. Claude Code writes implementation plan for the phase
2. Claude Code hands off to Codex with explicit, compact task specs
3. Claude Code monitors Codex progress
4. Codex signals completion
5. Claude Code verifies: runs tests, checks output, reviews code
6. If issues found: Claude Code compiles issue inventory → hands to Gemini Code Assist for debugging
7. Once verified: phase marked complete
8. Claude Code prompts user: plan next phase or begin building next phase

## Session Start

Read `active-context.md` at the project root at the start of every session. It contains current phase, last action, next action, and open items. Do not re-read planning docs to reconstruct state — use active-context.md instead.

Update `active-context.md` whenever a phase completes, a decision is made, or state changes significantly.

## Planning Docs

All architecture and implementation docs live in `.planning/`. This directory is:
- Gitignored
- Excluded from Claude Code context (`.claudeignore`)
- Excluded from Codex context (via `.gitignore`)
- Not to be read unless explicitly requested

Do not write planning docs anywhere else. Do not reference planning docs in code comments.

## Token Management

- Do not read `.planning/` unless explicitly asked
- Do not read `keep/` during implementation — reference only when a specific file is needed
- Keep task specs to Codex compact and explicit: file path, function signature, behavior, nothing more
- Do not summarize completed work unless asked

## Project

- **Runtime machine**: OCTOPUS (192.168.1.204), WSL2 Ubuntu, RTX 3060 12GB
- **Dev access**: VS Code Remote SSH from SNAIL (192.168.1.52) → OCTOPUS WSL2
- **External URL**: https://selenite.tonykapinos.com (Cloudflare proxy)
- **Stack**: FastAPI + SQLite + async SQLAlchemy | React + Vite + TypeScript + Tailwind + Radix UI
