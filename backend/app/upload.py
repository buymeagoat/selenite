import os
from pathlib import Path

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4", ".webm", ".aac"}
ALLOWED_EXTENSIONS = ALLOWED_AUDIO_EXTENSIONS


def upload_path(artifact_id: str, filename: str) -> Path:
    dest = UPLOAD_DIR / artifact_id
    dest.mkdir(parents=True, exist_ok=True)
    return dest / filename


def source_type_from_extension(filename: str) -> str | None:
    ext = Path(filename).suffix.lower()
    if ext in ALLOWED_AUDIO_EXTENSIONS:
        return "audio"
    return None
