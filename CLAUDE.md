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

## Token Conservation — ENFORCED

These rules are mandatory. No exceptions unless user explicitly overrides.

### No Subagents for Implementation
- Do not spawn subagents to write code. Subagents cost 2x tokens minimum (full context re-sent each call).
- Subagents allowed only for: read-only codebase exploration (Explore agent), never for writing files.

### File Reading
- Read only files you will directly edit or that contain a symbol you must import.
- Never speculatively read directories or related files "for context."
- Never re-read a file already read in the same session unless its content changed.

### Terminal / SSH Output
- Never pipe full command output into context. Use targeted grep or `tail -n 20`.
- Never dump full pytest output. Capture pass/fail counts + failed test names only.
- Never dump full build logs. Capture error lines only (`| grep -E 'error|Error|ERROR'`).

### Task Execution
- Batch all tasks from a phase into one prompt. Never send one task per message.
- Run verification once at end of phase, not after each file edit.
- No mid-phase re-reads of `active-context.md` or planning docs.

### Planning
- Phase plan = task list only: file path + function signature + behavior. No prose, no rationale.
- `active-context.md` must stay under 150 lines. Strip completed phase details after each phase closes.
- Do not read `.planning/` unless explicitly asked.
- Do not read `keep/` during implementation — reference only when a specific file is named.

### Task Specs to Codex
- Compact and explicit: file path, function signature, behavior. Nothing more.
- Do not summarize completed work unless asked.

## Project

- **Runtime machine**: OCTOPUS (192.168.1.204), WSL2 Ubuntu, RTX 3060 12GB
- **Dev access**: VS Code Remote SSH (`octopus-wsl`) — files edited and run **directly on OCTOPUS**. No SNAIL intermediary.
- **SSH host**: `octopus-wsl` (defined in `C:\Users\akapi\.ssh\config`)
- **Project path on OCTOPUS**: `/home/akapinos/selenite`
- **External URL**: https://selenite.tonykapinos.com (Cloudflare proxy)
- **Stack**: FastAPI + SQLite + async SQLAlchemy | React + Vite + TypeScript + Tailwind + Radix UI

### Workflow
1. Edit files directly on OCTOPUS via VS Code Remote SSH
2. Run/test directly in VS Code terminal (already on OCTOPUS)
3. Commit + push to GitHub when phase is stable (backup/history only)

### SSH Pattern (for commands outside VS Code)
```bash
ssh octopus-wsl '<command>'
```

Background processes:
```bash
ssh octopus-wsl 'nohup python run.py >/tmp/selenite.log 2>&1 </dev/null &'
```

nvm must be sourced for npm commands:
```bash
ssh octopus-wsl 'export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh" && npm run build'
```
