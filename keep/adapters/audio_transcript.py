"""AudioTranscriptAdapter - registration-only.

Audio transcription is handled by the ASR worker pipeline, not via the
adapter ingest() protocol. This adapter exists solely so that
adapter_type='audio_transcript' is a registered, discoverable type that
the frontend can enumerate via GET /content/adapters.

The ingest() method is intentionally not implemented in this phase.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class AudioTranscriptAdapter:
    """Adapter registration for audio transcript content items.

    Created by the bridge hook in process_job.py, not via ImportAdapter.ingest().
    """

    source_type = "audio_transcript"
    display_name = "Audio Transcript"
    accepted_mimes: list[str] = ["audio/*", "video/*"]
    accepted_extensions: list[str] = [
        "mp3",
        "mp4",
        "wav",
        "m4a",
        "ogg",
        "flac",
        "webm",
        "mkv",
        "avi",
        "mov",
    ]
    supported_export_formats: list[str] = ["txt", "srt", "vtt", "json"]

    def accepts(self, mime: str, extension: str) -> bool:
        ext = extension.lower().lstrip(".")
        return ext in self.accepted_extensions

    async def ingest(
        self,
        source_path: str | None = None,
        *,
        options: dict[str, Any] | None = None,
        db: AsyncSession | None = None,
        user_id: int | None = None,
        storage: Any | None = None,
    ) -> None:  # type: ignore[override]
        raise NotImplementedError(
            "AudioTranscriptAdapter does not support direct ingest. "
            "Audio content is created via the ASR job pipeline."
        )
