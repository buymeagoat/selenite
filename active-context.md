# Active Context

_Last updated: 2026-04-29_

## Purpose

Session handoff document. Read this at the start of every session. Do not re-read all planning docs — use this instead.

---

## Current Phase

**Phase 1 — Core Scaffold. Ready to begin.**

Phase 0 complete. OCTOPUS WSL2 environment fully configured. Next: hand Phase 1 to Codex.

---

## Last Session (2026-04-24)

- Re-evaluated Selenite scope against TonyOS requirements
- Confirmed: build Selenite as TonyOS processing layer (same system, extended scope)
- Updated constraint charter: OCTOPUS is always-available infrastructure
- Updated ASR and diarization model list (see below)
- Updated Ollama model to `gemma-4-e4b-it`
- Created this document

---

## Next Action

**Execute Phase 1.** Claude Code implements directly (not Codex). Read the full plan first:

```
.planning/plans/2026-04-15-phase0-phase1.md
```

This file is claudeignored by default — explicitly request it at session start. It contains complete code for every task.

### Workflow
1. Write files on SNAIL (`d:/Dev/projects/selenite/`)
2. Push to GitHub
3. SSH pull on OCTOPUS + run tests

### SSH Pattern (all OCTOPUS commands)
```bash
ASKPASS=$(mktemp /tmp/askpass.XXXXXX.sh)
printf '#!/bin/bash\necho "Bobaisagreatcat77$"\n' > "$ASKPASS"
chmod +x "$ASKPASS"
SSH_ASKPASS="$ASKPASS" SSH_ASKPASS_REQUIRE=force ssh -i ~/.ssh/id_ed25519_failover -p 2222 -o StrictHostKeyChecking=no akapinos@192.168.1.204 '<command>' 2>&1
rm -f "$ASKPASS"
```

### Phase 1 Task List
- [x] **1.1** Python deps — `backend/requirements.txt`, `requirements-dev.txt`
- [x] **1.2** DB models — `database.py`, `models.py`, `alembic/`, migration
- [x] **1.3** Auth — `auth.py` (bcrypt + JWT HttpOnly cookie), tests
- [x] **1.4** Processor registry — `processors/base.py`, `registry.py`, `stubs.py`
- [x] **1.5** API routers — `routers/` (processors, config, artifacts, jobs), `schemas.py` — 20/20 tests passing
- [ ] **1.6** Backend entry — `run.py` (uvicorn, 0.0.0.0:8000)
- [ ] **1.7** Frontend foundation — `package.json`, Vite, Tailwind, theme tokens, fonts
- [ ] **1.8** Auth flow — API client, `useAuth`, Login page, ProtectedRoute
- [ ] **1.9** Shell — NavRail, routing, page stubs (Upload/Queue/Library/Settings)
- [ ] **1.10** Build + smoke test — `npm run build`, FastAPI serves static, end-to-end login

### Python version note
Ubuntu 24.04 ships Python 3.12. Plan references 3.11 — use `python3.12` and `python3.12 -m venv .venv` everywhere.

## Phase 0 Completion Summary

- [x] WSL2 SSH on port 2222 — working
- [x] SNAIL SSH config (`octopus-wsl` host alias)
- [x] .wslconfig — 30GB RAM, 4 processors
- [x] GPU verified — RTX 3060 12GB, nvidia-smi at `/usr/lib/wsl/lib/nvidia-smi`
- [x] Python 3.12.3 + venv installed
- [x] Node 20.20.2 + nvm installed
- [x] git configured, repo cloned at `~/selenite`
- [x] Ollama reachable from WSL2 at `172.31.192.1:11434` — `gemma4-e4b:latest` available
- [x] `.env` written on OCTOPUS with SECRET_KEY, OLLAMA_HOST, etc.
- [x] `.env.example` committed + pushed to GitHub
- [x] Directory scaffold created (`backend/app/`, `frontend/src/`, etc.)

## OCTOPUS Environment Notes

- **Python**: 3.12 (Ubuntu 24.04 default — 3.11 not in repos)
- **GPU PATH**: add `/usr/lib/wsl/lib` to PATH before using nvidia-smi
- **Ollama host**: `172.31.192.1:11434` — WSL2 gateway IP, changes on WSL restart. May need dynamic resolution: `$(ip route show | grep default | awk '{print $3}')`
- **Windows home**: `C:\Users\akapi` (not `akapinos`)
- **sudo**: works with same password as SSH key

---

## Architecture

Selenite runs entirely on OCTOPUS. Nothing runs on SNAIL except the development toolchain.

```
SNAIL (192.168.1.52)
  ├── VS Code + Claude Code
  ├── Codex CLI / Gemini CLI
  └── SSH → OCTOPUS WSL2

OCTOPUS (192.168.1.204)
  ├── WSL2 Ubuntu
  │   ├── Selenite backend (FastAPI, port 8000, 0.0.0.0)
  │   ├── WhisperX + pyannote (CUDA via WSL2 passthrough)
  │   ├── MinerU2.5 / GLM-OCR
  │   └── Git repo: ~/selenite
  └── Windows (host)
      └── Ollama (Windows native) — gemma-4-e4b-it
          Callable from WSL2 at host gateway IP or localhost

LAN access:  http://192.168.1.204:8000
External:    https://selenite.tonykapinos.com (Cloudflare)
```

---

## Remote Access: Claude Code → OCTOPUS

SSH setup is Task 0.1 of the plan. Once complete, Claude Code runs OCTOPUS commands via:

```bash
ssh -p 2222 <wsl_username>@192.168.1.204 "<command>"
```

Example:
```bash
ssh -p 2222 akapinos@192.168.1.204 "cd ~/selenite/backend && source .venv/bin/activate && python -m pytest tests/ -v"
```

Claude Code never relays commands through the user. It SSHes directly.

---

## Current Model Decisions

| Role | Model | Host |
|---|---|---|
| Primary local LLM | `gemma-4-e4b-it` | OCTOPUS, Ollama (Windows) |
| SNAIL local LLM | TBD lightweight (Deepseek candidate) | SNAIL, Ollama — experimentation only |
| ASR default | `faster-whisper-large-v3` | OCTOPUS WSL2, CUDA |
| ASR options | `whisper-large-v3`, `whisper-large-v3-turbo`, `nvidia/parakeet-tdt-0.6b-v3` | OCTOPUS WSL2 |
| Diarization default | `pyannote/speaker-diarization-3.1` | OCTOPUS WSL2, CUDA |
| Diarization option | `XiaomiMiMo/MiMo-V2.5-ASR` | OCTOPUS WSL2 |
| OCR | `MinerU2.5` / `GLM-OCR` | OCTOPUS WSL2 |

---

## Key Files

| File | Purpose |
|---|---|
| `active-context.md` | This file — session handoff |
| `keep/VISION_AND_SPEC.md` | Product spec — what Selenite is and does |
| `.planning/plans/2026-04-15-phase0-phase1.md` | Implementation plan — task-by-task |
| `.planning/specs/constraint-charter.md` | Hard constraints and operating boundaries |
| `.planning/specs/2026-04-15-selenite-design.md` | Full system design (read only if needed) |

Planning docs are gitignored and claudeignored. Request them explicitly if needed.

---

## Open Items

- [x] WSL2 username on OCTOPUS — `akapinos`
- [ ] Cloudflare tunnel / port-forward config for external access — plan in Phase 0 or 0.5
- [ ] Evaluate MiMo-V2.5-ASR: integrated ASR+diarization vs. standalone diarizer — clarify before Phase 2
- [ ] SNAIL local LLM model — decide before it's needed (not blocking Phase 0/1)

---

## Phase Completion Log

| Phase | Status | Date |
|---|---|---|
| Planning & spec | Complete | 2026-04-15 |
| Model/constraint update | Complete | 2026-04-24 |
| Phase 0: Env setup | Complete | 2026-04-29 |
| Phase 1: Core scaffold | In progress (1.1–1.5 done) | 2026-04-29 |
| Phase 2: Audio pipeline | Not started | — |
| Phase 3: LLM post-processing | Not started | — |
| Phase 4: PDF/OCR | Not started | — |
| Phase 5: Chat export parsing | Not started | — |
