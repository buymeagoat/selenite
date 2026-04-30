# Active Context

_Last updated: 2026-04-30_

## Purpose

Session handoff document. Read this at the start of every session. Do not re-read all planning docs — use this instead.

---

## Current Phase

**Phase 2 — Audio Pipeline. Ready to begin.**

Phase 1 complete. Backend + frontend shell running on OCTOPUS. All 20 tests passing. Next: implement ASR + diarization pipeline.

---

## Last Session (2026-04-30)

- Implemented all Phase 1 tasks (1.1–1.10) via subagent-driven development
- Key deviations from plan: passlib replaced with direct bcrypt (passlib/bcrypt 4.x incompatible), stubs registered explicitly in test fixture (lifespan doesn't run in ASGITransport tests)
- Fixed: `datetime.utcnow()` → `datetime.now(timezone.utc).replace(tzinfo=None)` (Python 3.12 deprecation)
- Fixed: `.gitignore` updated to exclude `__pycache__/` and `keep/`
- Smoke test confirmed: 401 unauth, login/me working, 9 processors all unavailable

---

## Next Action

**Execute Phase 2: Audio Pipeline.**

Phase 2 scope (plan not yet written — Claude Code writes plan first):
- File upload endpoint (multipart, store to disk)
- Job queue (asyncio-based, VRAM sequential)
- ASR processor: faster-whisper-large-v3 (CUDA)
- Diarization processor: pyannote/speaker-diarization-3.1 (CUDA)
- Transcript merge + formatting
- Upload page UI (file picker, processor selection, progress polling)

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

nvm must be sourced for npm commands:
```bash
export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh"
```

---

## Phase 1 Completion Summary

- [x] 1.1 Python deps — requirements.txt, requirements-dev.txt
- [x] 1.2 DB models — database.py, models.py, alembic migration
- [x] 1.3 Auth — bcrypt (direct, not passlib) + JWT HttpOnly cookie, 8 tests
- [x] 1.4 Processor registry — base.py, registry.py, stubs.py, 4 tests
- [x] 1.5 API routes — processors, config, artifacts, jobs, 6 route tests
- [x] 1.6 Backend entry — run.py (uvicorn 0.0.0.0:8000)
- [x] 1.7 Frontend foundation — Vite 5, Tailwind 3, theme tokens, fonts
- [x] 1.8 Auth flow — API client, useAuth, Login page, ProtectedRoute
- [x] 1.9 Shell — NavRail, routing, page stubs (Upload/Queue/Library/Settings)
- [x] 1.10 Build + smoke — frontend built (46 modules), all 20 tests pass, API verified

**Test count:** 20 backend tests, all passing
**Frontend build:** 172KB JS, 1KB CSS, 0 TS errors
**DB password:** `selenite` (set in config table on OCTOPUS)

---

## OCTOPUS Environment Notes

- **Python**: 3.12 (Ubuntu 24.04 default)
- **Node**: 20.20.2 via nvm — must source `$NVM_DIR/nvm.sh` in SSH sessions
- **GPU PATH**: add `/usr/lib/wsl/lib` to PATH before using nvidia-smi
- **Ollama host**: `172.31.192.1:11434` — WSL2 gateway IP, changes on WSL restart
- **Windows home**: `C:\Users\akapi` (not `akapinos`)
- **venv**: `~/selenite/backend/.venv`
- **Frontend dist**: `~/selenite/frontend/dist`

---

## Architecture

```
SNAIL (192.168.1.52)
  ├── VS Code + Claude Code
  └── SSH → OCTOPUS WSL2

OCTOPUS (192.168.1.204)
  ├── WSL2 Ubuntu
  │   ├── Selenite backend (FastAPI, port 8000, 0.0.0.0)
  │   ├── WhisperX + pyannote (CUDA via WSL2 passthrough) — Phase 2
  │   └── Git repo: ~/selenite
  └── Windows (host)
      └── Ollama (Windows native) — gemma-4-e4b-it

LAN access:  http://192.168.1.204:8000
External:    https://selenite.tonykapinos.com (Cloudflare)
```

---

## Open Items

- [ ] Cloudflare tunnel / port-forward config for external access
- [ ] Evaluate MiMo-V2.5-ASR: integrated ASR+diarizer vs. standalone — clarify before Phase 2 implementation
- [ ] SNAIL local LLM — decide before needed (not blocking Phase 2)
- [ ] jose library uses `datetime.utcnow()` internally (DeprecationWarning in tests) — not blocking, upstream issue

---

## Phase Completion Log

| Phase | Status | Date |
|---|---|---|
| Planning & spec | Complete | 2026-04-15 |
| Model/constraint update | Complete | 2026-04-24 |
| Phase 0: Env setup | Complete | 2026-04-29 |
| Phase 1: Core scaffold | Complete | 2026-04-30 |
| Phase 2: Audio pipeline | Not started | — |
| Phase 3: LLM post-processing | Not started | — |
| Phase 4: PDF/OCR | Not started | — |
| Phase 5: Chat export parsing | Not started | — |
