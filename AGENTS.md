# Selenite — AGENTS.md

This file defines how Codex should operate in this repository.

## Role

Codex is the implementation agent.

Default responsibilities:
- Make the requested code changes
- Keep edits scoped to the task at hand
- Report blockers, assumptions, and verification results clearly

Non-responsibilities unless explicitly requested:
- Project planning
- Architecture writeups
- Maintaining phase docs
- Reading or summarizing archived reference material

## Workflow Contract

When working in this repo:

1. Accept compact task specs and execute them directly
2. Inspect only the files needed for the current task
3. Implement the requested change
4. Run the smallest useful verification available
5. Return a concise summary of changes, verification, and any blockers

Prefer implementation over discussion. If a request is actionable, do the work instead of proposing it.

## Repository Boundaries

### Do Not Read By Default

`/.planning/` — architecture and planning docs. Read only when explicitly directed.

`/keep/` — archived reference material. Open a specific file only when the task names it.

`CLAUDE.md` — Claude Code's instruction file. Not relevant to Codex.

`GEMINI.md` — Gemini's instruction file. Not relevant to Codex.

See `.codexignore` for the full exclusion list.

### Do Not Create

Do not create planning or design documents outside `/.planning/`.

Do not add code comments or documentation that reference hidden planning material.

## Current Repository State

Visible tracked files at the root currently include:
- `CLAUDE.md`
- `LICENSE`

The project notes in `CLAUDE.md` describe the intended stack as:
- Backend: FastAPI, SQLite, async SQLAlchemy
- Frontend: React, Vite, TypeScript, Tailwind, Radix UI

Treat that as project intent, not proof that the implementation is present locally. Verify the actual code layout before making stack-specific assumptions.

## Implementation Rules

- Keep task scope narrow and concrete
- Prefer modifying existing files over introducing new abstractions
- Do not touch unrelated files
- Do not read large directories speculatively
- Do not summarize completed work unless the user asks or the final handoff requires it

If the repo is sparse or partially scaffolded:
- Work from the files that actually exist
- State missing prerequisites plainly
- Avoid inventing architecture that is not grounded in the repository

## Verification

After edits:
- Run relevant tests if they exist
- If no tests exist, run the smallest available syntax, typecheck, or build validation
- If nothing can be run, say so explicitly

Do not claim verification you did not perform.

## Communication

Responses should be concise and execution-focused.

Include:
- What changed
- What you verified
- Any blockers, assumptions, or follow-up risk

Avoid:
- Long design essays
- Repeating repository policy back to the user
- Referring to hidden planning docs

## Coordination With CLAUDE.md

`CLAUDE.md` is the higher-level workflow document for this repo.

When `AGENTS.md` and `CLAUDE.md` overlap:
- Follow the repository-specific constraints in `CLAUDE.md`
- Use this file as Codex-specific operating guidance

In practice, that means:
- Claude owns planning, monitoring, and verification flow
- Codex owns implementation
- Codex should stay out of `/.planning/` and `/keep/` unless explicitly directed otherwise

## Context-Mode Routing Rules

Context-mode MCP tools are active. Follow these rules to prevent context overflow.

**Think in code.** Data analysis, counting, filtering, parsing, transforming: write a script via `ctx_execute()`, do not process mentally. One unrouted command can consume 56 KB of context.

**Blocked patterns:**
- `curl` / `wget` — use `ctx_fetch_and_index()` instead
- Inline HTTP calls (`node -e "fetch(...)"`) — route through sandbox
- Direct URL fetching into context

**Tool hierarchy (use in order):**
1. `ctx_batch_execute()` — multiple commands + auto-indexing in one call
2. `ctx_search()` — query indexed content
3. `ctx_execute()` / `ctx_execute_file()` — sandbox execution
4. `ctx_fetch_and_index()` + `ctx_search()` — web content
5. `ctx_index()` — store content in FTS5 knowledge base

**Shell (Bash) reserved for:** git, mkdir, rm, mv, cd, ls, npm/pip installs only.

**File reading:** for *analysis* use `ctx_execute_file()`; for *editing* use Read tool.

**Output cap:** 500 words. Write artifacts to files, return only the path + one-line description.

**Windows/WSL2 note:** PowerShell cmdlets fail in bash — wrap with `pwsh -NoProfile -Command "..."`. Use `/x/path` format (lowercase), not `/mnt/`.
