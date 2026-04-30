# Active Context

_Last updated: 2026-04-30_

## Purpose

Session handoff document. Read this at the start of every session. Do not re-read all planning docs — use this instead.

---

## Current Phase

**Phase 3 — LLM Post-processing. Ready to begin.**

Phase 2 complete. Full audio pipeline running on OCTOPUS. 27 backend tests passing. Frontend built (50 modules, 0 TS errors). Upload → ASR → Diarization → Markdown pipeline wired end-to-end.

---

## Last Session (2026-04-30)

- Implemented all Phase 2 tasks (2.0–2.11) via subagent-driven development
- Pre-flight: installed torch 2.5.1+cu121, ffmpeg, numpy, pyannote.audio 3.3.2, faster-whisper 1.2.1
- Key deviations from plan:
  - `pyannote.audio>=3.0` cannot install via normal pip (requires `lightning` package unavailable); installed with `--no-deps` + manual deps (pytorch-lightning, einops, torchaudio, semver, tensorboardX, speechbrain, omegaconf, pytorch_metric_learning)
  - `pyannote.audio==1.1.2` installs by default; must use `--no-deps` + upgrade for 3.x
  - `useAuth.ts` → renamed to `useAuth.tsx` (JSX in .ts file fails tsc)
- Smoke test confirmed: login works, upload creates artifact + queued jobs, ASR job picked up by queue (model downloading on first run)

---

## Next Action

**Execute Phase 3: LLM Post-processing.**

Phase 3 scope (plan not yet written):
- LLM post-processing step after diarization (summarization, action items, etc.)
- Ollama integration (gemma-4-e4b-it via Windows host at 172.31.192.1:11434)
- Settings page — set LLM config, HF token, etc.
- Artifact detail enhancements (show LLM outputs)

### First session actions
1. Read active-context.md
2. Write Phase 3 plan to `.planning/plans/`
3. Execute via subagent-driven development

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

Background processes via SSH need `</dev/null` to avoid hanging:
```bash
nohup python run.py >/tmp/selenite.log 2>&1 </dev/null &
```

---

## Phase 2 Completion Summary

- [x] 2.0 Pre-flight — torch 2.5.1+cu121, ffmpeg, numpy installed on OCTOPUS
- [x] 2.1 Extend processor protocols — ASRResult, DiarizedResult, transcribe/diarize
- [x] 2.2 Job queue — asyncio single-worker queue, start/stop in lifespan
- [x] 2.3 Upload endpoint — POST /api/upload, multipart, artifact + 2 jobs created
- [x] 2.4 SSE stream — GET /api/jobs/stream, 1s poll, change-tracking
- [x] 2.5 FasterWhisperProcessor — CUDA, load/unload, executor
- [x] 2.6 PyannoteDiarizer — pyannote.audio 3.3.2, HF token from config
- [x] 2.7 Audio pipeline — ASR → enqueue diarize → merge → markdown
- [x] 2.8 Upload UI — drag-drop, processor selection, submit → /queue
- [x] 2.9 Queue UI — SSE EventSource, StageNode visualization
- [x] 2.10 Library + ArtifactDetail — grid, markdown preview, delete
- [x] 2.11 Build + smoke — 50 modules, 0 TS errors, upload → processing verified

**Test count:** 27 backend tests, all passing
**Frontend build:** 181KB JS, 1KB CSS, 50 modules, 0 TS errors

---

## OCTOPUS Environment Notes

- **Python**: 3.12 (Ubuntu 24.04 default)
- **Node**: 20.20.2 via nvm — must source `$NVM_DIR/nvm.sh` in SSH sessions
- **GPU PATH**: add `/usr/lib/wsl/lib` to PATH before using nvidia-smi
- **Ollama host**: `172.31.192.1:11434` — WSL2 gateway IP, changes on WSL restart
- **Windows home**: `C:\Users\akapi` (not `akapinos`)
- **venv**: `~/selenite/backend/.venv`
- **Frontend dist**: `~/selenite/frontend/dist`
- **torch**: 2.5.1+cu121 (CUDA available)
- **pyannote.audio**: 3.3.2 (installed --no-deps; `lightning` package unavailable, use pytorch-lightning)
- **faster-whisper**: 1.2.1
- **First model run**: whisper large-v3 (~3GB) + pyannote (~1GB) will download on first job

---

## Architecture

```
SNAIL (192.168.1.52)
  ├── VS Code + Claude Code
  └── SSH → OCTOPUS WSL2

OCTOPUS (192.168.1.204)
  ├── WSL2 Ubuntu
  │   ├── Selenite backend (FastAPI, port 8000, 0.0.0.0)
  │   ├── faster-whisper 1.2.1 + pyannote 3.3.2 (CUDA via WSL2 passthrough)
  │   └── Git repo: ~/selenite
  └── Windows (host)
      └── Ollama (Windows native) — gemma-4-e4b-it at 172.31.192.1:11434

LAN access:  http://192.168.1.204:8000
External:    https://selenite.tonykapinos.com (Cloudflare)
```

---

## Open Items

- [ ] HuggingFace token — must be set in config (`processor.pyannote.hf_token`) before pyannote works
- [ ] First model download — whisper large-v3 (~3GB) + pyannote (~1GB), requires internet on OCTOPUS
- [ ] Settings page — not yet implemented (can set HF token via API directly for now)
- [ ] Cloudflare tunnel / port-forward config for external access
- [ ] SNAIL local LLM — decide before needed (not blocking Phase 3)
- [ ] jose library uses `datetime.utcnow()` internally (DeprecationWarning in tests) — upstream issue

---

## Phase Completion Log

| Phase | Status | Date |
|---|---|---|
| Planning & spec | Complete | 2026-04-15 |
| Model/constraint update | Complete | 2026-04-24 |
| Phase 0: Env setup | Complete | 2026-04-29 |
| Phase 1: Core scaffold | Complete | 2026-04-30 |
| Phase 2: Audio pipeline | Complete | 2026-04-30 |
| Phase 3: LLM post-processing | Not started | — |
| Phase 4: PDF/OCR | Not started | — |
| Phase 5: Chat export parsing | Not started | — |
