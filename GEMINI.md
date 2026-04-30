# Selenite — Gemini CLI Workflow

## Role

You are **Gemini Code Assist** (Gemini CLI) in this project.
Your primary responsibility is **Debugging**.
You receive issue inventories from Claude Code (or the user) and resolve them.

## Workflow

1. You will receive an issue inventory or specific debugging tasks after Claude Code verifies Codex's implementation.
2. Investigate the issues outlined in the inventory.
3. Apply targeted, surgical fixes to resolve the identified bugs or test failures.
4. Run tests or validations to verify your fixes.
5. Signal completion once the issues in the inventory are resolved.
6. Do not modify the broader architecture, write implementation plans, or begin building new phases—those are responsibilities of Claude Code and Codex.

## Token Conservation — ENFORCED

These rules are mandatory and override default behavior.

### File Reading
- Read only files directly involved in the bug. Do not read "related" files speculatively.
- Never re-read a file already read in the same session unless its content changed.
- For analysis (counting, parsing, searching a file): script it via `ctx_execute_file()`, do not read into context.

### Terminal Output
- Never pipe full command output into context.
- Pytest: targeted output only — `pytest -q 2>&1 | tail -20`.
- Build/lint: error lines only — `| grep -E 'error|Error|ERROR'`.

### Context Restrictions
- **Do not read `.planning/`** unless explicitly asked.
- **Do not read `keep/`** during debugging — only open when a specific file is named.
- **Do not read `CLAUDE.md` or `AGENTS.md`** — other agents' files, not relevant.
- See `.geminiignore` for the full exclusion list.

### Output
- Return: files changed, fix applied, test result. Nothing else.
- No summaries of completed work unless asked.
- Output cap: 500 words. Write artifacts to files, return path + one-line description.

## Project Environment & Stack

- **Runtime machine**: OCTOPUS (192.168.1.204), WSL2 Ubuntu, RTX 3060 12GB
- **Dev access**: VS Code Remote SSH (`octopus-wsl`) — files edited and run **directly on OCTOPUS**
- **Project path**: `/home/akapinos/selenite`
- **External URL**: https://selenite.tonykapinos.com (Cloudflare proxy)
- **Stack**: FastAPI + SQLite + async SQLAlchemy | React + Vite + TypeScript + Tailwind + Radix UI

## Context-Mode Routing Rules

Context-mode MCP tools are active. Follow these rules to prevent context overflow.

**Think in code.** Analysis tasks (counting, filtering, parsing, transforming) must be programmed via `mcp__context-mode__ctx_execute()`, not computed mentally. One script replaces ten tool calls and saves 100x context.

**Blocked patterns:**
- `curl` / `wget` — use `ctx_fetch_and_index()` instead
- Inline HTTP calls — route through sandbox
- Direct web fetching into context

**Tool hierarchy (use in order):**
1. `ctx_batch_execute()` — primary tool for multiple simultaneous results
2. `ctx_search()` — query previously indexed content
3. `ctx_execute()` — run code/shell in sandbox
4. `ctx_fetch_and_index()` — web retrieval with indexing
5. `ctx_index()` — store content for later search

**Shell reserved for:** git, mkdir, file operations, package installs only.

**File reading for analysis:** use `ctx_execute_file()` instead of `read_file`.

**Large search results:** execute grep in sandbox, return summaries only.

**Output cap:** 500 words. Write artifacts to files, return path + one-line description only.
