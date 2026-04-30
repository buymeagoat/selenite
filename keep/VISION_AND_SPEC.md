# Selenite — Vision & Spec

*Written 2026-04-13. Hand this document to a fresh Claude session to resume without re-explaining context.*

---

## What This Is

A personal, single-user, self-hosted ingestion appliance. Its one job is to take messy real-world information in all its forms and convert it into clean, structured markdown documents that can be used in other tools (Obsidian, AnythingLLM, Open WebUI, NotebookLM, etc.).

This is **not** a RAG system. It is **not** a chat interface. It is **not** a knowledge graph. It is the pipeline that feeds those systems. It does one thing well: in → processed → out.

---

## Why It Exists

The tools that handle RAG, AI chat, and knowledge organization (NotebookLM, Open WebUI, AnythingLLM, Obsidian) are good and freely available. What they cannot do is ingest messy raw source material cleanly:

- Audio files need transcription and speaker diarization
- Scanned PDFs and images need vision-based OCR
- LLM chat exports (ChatGPT, Claude) need format-specific parsers
- All of this needs to happen locally, for free, with no cloud dependency

This tool fills that gap. Everything else is delegated to existing tools.

---

## The User

Single user. The person running the server is the only user. There is no multi-user system, no roles, no admin panel separate from user settings. Authentication is a single password on the door. Configuration is a single settings panel.

---

## Core Workflow

1. User drops a file into the interface (or pastes text, or dictates audio)
2. System detects the input type and routes it to the correct processor
3. Processor runs locally on the GPU, produces a clean markdown document
4. Document appears in the library with auto-generated metadata
5. User can tag, sort, preview, and export the document
6. User takes the document to whatever tool they use for AI work

That's the entire product.

---

## Input Types & Processors

### Audio files → diarized transcript
- **Output:** Markdown with speaker-labeled turns (Speaker 1:, Speaker 2:, etc.)
- **Hardware:** Local GPU (RTX 3060 12GB VRAM)

**ASR models (user-selectable at job time):**
| Model | Notes |
|---|---|
| `openai/whisper-large-v3` | Highest accuracy baseline |
| `openai/whisper-large-v3-turbo` | Faster, slightly lower accuracy |
| `Systran/faster-whisper-large-v3` | CTranslate2 backend, fastest Whisper variant |
| `nvidia/parakeet-tdt-0.6b-v3` | NVIDIA NeMo, strong English, 0.6B params |

**Diarization models (user-selectable at job time):**
| Model | Notes |
|---|---|
| `pyannote/speaker-diarization-3.1` | Gold standard, requires HuggingFace token + terms accept |
| `XiaomiMiMo/MiMo-V2.5-ASR` | Integrated ASR+diarization, evaluate fit |

Default pair: `faster-whisper-large-v3` + `pyannote/speaker-diarization-3.1` (best speed/accuracy balance).
All models run locally. pyannote requires one-time HuggingFace account + terms accept (no cost).

### PDFs (digital/selectable text) → markdown
- **Processor:** MinerU2.5 (1.2B, local GPU)
- **Output:** Clean markdown preserving structure, tables, headings
- **Notes:** MinerU2.5 leads the OmniDocBench v1.6 benchmark at 95.75. Purpose-built for PDF-to-markdown. Runs via Transformers or vLLM.

### PDFs (scanned) and images with text → markdown
- **Processor:** MinerU2.5 or GLM-OCR (0.9B, local GPU)
- **Output:** Extracted text as markdown
- **Notes:** Both fit easily in 12GB. GLM-OCR has the easiest setup (official SDK + Ollama/vLLM/Transformers). Handwriting and severely degraded scans remain imperfect — flag these for manual review rather than failing silently.

### LLM chat exports → individual conversation documents
- **Processor:** Local parser script (no LLM needed)
- **Formats supported:**
  - ChatGPT: zip archive containing `conversations.json`
  - Claude: JSON export
- **Output:** One markdown file per conversation, with speaker-labeled turns
- **Reference:** `ai-chat-md-export` library (Python, MIT) handles both formats
- **Notes:** These are deterministic format parsers. No model needed. Fast.

### Text paste → artifact
- Direct save. User pastes text, gives it a name, it becomes a markdown document in the library.

### Voice dictation → artifact
- **Processor:** WhisperX (same model stack as audio, shorter input)
- User clicks a record button in the UI, speaks, releases. Transcript saved as markdown.

---

## What Happens After Processing

Each processed artifact gets:
- A markdown file (the content)
- Metadata: source filename, input type, processor used, date created, word count
- Status: pending / processing / complete / failed
- Zero or more tags (user-applied)

The user can:
- Preview the markdown in-app
- Edit the markdown directly in-app (simple text editor, not rich text)
- Apply/remove tags
- Export the file (download as .md)
- Delete the artifact

That's the full feature surface. Nothing more.

---

## What This Is NOT

- Not a RAG/chat system (use Open WebUI or AnythingLLM for that)
- Not a knowledge graph (use Obsidian for that)
- Not a multi-user application
- Not a cloud service
- Not a subscription product
- Not a replacement for NotebookLM (it feeds NotebookLM)

Any feature request that doesn't serve "convert messy input to clean markdown" is out of scope.

---

## Technology Stack

Carry over from Selenite-dev. No reason to change.

- **Backend:** FastAPI + SQLite + async SQLAlchemy (aiosqlite)
- **Frontend:** React + Vite + TypeScript + Tailwind CSS + Radix UI
- **Job queue:** Simple async background task queue (no Celery/Redis needed at this scale)
- **ML models:** Run via Python subprocess or direct library calls from the backend

---

## Database Schema

Simple. Five tables total.

```sql
artifacts (
  id            TEXT PRIMARY KEY,       -- UUID
  filename      TEXT NOT NULL,          -- original filename or "paste" / "dictation"
  source_type   TEXT NOT NULL,          -- audio | pdf | image | chat_export | text | dictation
  status        TEXT NOT NULL,          -- pending | processing | complete | failed
  content       TEXT,                   -- the markdown output
  metadata_json TEXT,                   -- JSON blob: word_count, duration, speakers, etc.
  error         TEXT,                   -- error message if failed
  created_at    DATETIME NOT NULL,
  updated_at    DATETIME NOT NULL
)

jobs (
  id            TEXT PRIMARY KEY,       -- UUID
  artifact_id   TEXT NOT NULL REFERENCES artifacts(id),
  processor     TEXT NOT NULL,          -- whisperx | mineru | glm_ocr | chat_parser | direct
  status        TEXT NOT NULL,          -- queued | running | complete | failed
  progress      INTEGER DEFAULT 0,      -- 0-100
  error         TEXT,
  created_at    DATETIME NOT NULL,
  updated_at    DATETIME NOT NULL
)

tags (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL UNIQUE,
  color         TEXT NOT NULL DEFAULT '#6B7280'
)

artifact_tags (
  artifact_id   TEXT NOT NULL REFERENCES artifacts(id),
  tag_id        INTEGER NOT NULL REFERENCES tags(id),
  PRIMARY KEY (artifact_id, tag_id)
)

config (
  key           TEXT PRIMARY KEY,
  value         TEXT NOT NULL
)
```

---

## Configuration (config table keys)

```
auth.password_hash          — bcrypt hash of the single user password
processor.whisperx.model    — whisper model name (default: large-v3)
processor.whisperx.device   — cuda | cpu
processor.pyannote.token    — HuggingFace token for pyannote community-1
processor.mineru.device     — cuda | cpu
processor.glm_ocr.device    — cuda | cpu
output.folder               — absolute path to export folder (optional)
```

---

## Frontend: Four Areas

### 1. Upload Panel
- Drag-and-drop zone accepting all supported file types
- "Paste text" button → opens a modal with a textarea and name field
- "Dictate" button → activates microphone, records, submits on release
- File type is auto-detected; user is shown what processor will be used

### 2. Processing Queue
- Live list of jobs currently running or recently queued
- Shows: filename, processor, progress bar, status
- Auto-refreshes (polling or websocket)
- Errors shown inline with the failed job

### 3. Library
- Grid or list of completed artifacts
- Filter by: source type, tag, date range, text search
- Sort by: date created, name, word count
- Each card shows: filename, type icon, date, tags, word count
- Click → opens artifact detail view

### 4. Artifact Detail View
- Preview the markdown (rendered)
- Toggle to edit the raw markdown (simple textarea or CodeMirror)
- Tag management (add/remove tags)
- Metadata display (source type, processor, date, word count, duration for audio)
- Export button (download .md file)
- Delete button

### 5. Settings Panel (accessible via nav)
- Password change
- Model configuration (Whisper model, device selection)
- HuggingFace token (for pyannote)
- Output folder path
- Status indicators showing which models are loaded/available

---

## Code to Carry Forward

The `asr/` and `adapters/` directories from Selenite-dev are in the `keep/` folder alongside this document.

### `asr/` — Use as reference, rewrite cleanly
The Whisper/diarization pipeline logic is sound. The job lifecycle, progress tracking, model loader, and formatting modules are all worth studying. However, they were built for Selenite's old architecture (Celery jobs, complex content models). Rewrite them for the new simpler architecture rather than copying directly.

### `adapters/` — Use selectively
- `text_file.py` — straightforward, port directly
- `subtitle_file.py` — useful reference for timed transcript handling
- `llm_conversation.py` — reference for chat export parsing patterns
- `audio_transcript.py` — reference only; replace with WhisperX integration
- `document_ocr.py` — reference only; replace with MinerU2.5/GLM-OCR
- `web_page.py` — not needed in the new system (out of scope)
- `email_file.py` — not needed in the new system (out of scope)

---

## Processing Stack Summary

| Input | Processor | Model Size | VRAM |
|---|---|---|---|
| Audio → transcript | Faster-Whisper large-v3 + pyannote-3.1 (default) | ~1.5B + 0.6GB | ~10–12GB |
| PDF (digital) → markdown | MinerU2.5 | 1.2B | ~3GB |
| PDF (scanned) → markdown | MinerU2.5 or GLM-OCR | 0.9–1.2B | ~3GB |
| Image → markdown | GLM-OCR or MinerU2.5 | 0.9–1.2B | ~3GB |
| Chat export → markdown | Parser script | None | None |
| Text paste | Direct save | None | None |
| Dictation → markdown | WhisperX | Same as audio | ~10GB |

All local. All free. All run on a 12GB VRAM GPU.

---

## What Success Looks Like

User opens the app. Drags in an audio file. Sees it appear in the queue as "Processing — WhisperX." A few minutes later it moves to the library as a clean diarized transcript. User clicks it, reads it, adds a tag, downloads it. Takes it to Open WebUI or NotebookLM. Done.

That interaction — from file drop to usable markdown — is the entire product. Everything in the implementation should serve that moment.

---

## History & Context

This system replaces Selenite-dev, a two-year project that grew from an ASR tool into an overcomplicated platform with workspaces, collections, admin panels, cloud storage, and a RAG chat system. None of those features served the core workflow. The new system strips everything back to what was always the actual value: clean, local ingestion of personal data into structured documents.

Selenite-dev is archived. Its ingestion adapter code and ASR pipeline are in the `keep/` folder as reference.
