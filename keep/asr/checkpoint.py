"""Chunked transcription with checkpoint persistence mixin."""

import json
import logging
import math
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.job import Job
from app.services.asr.constants import CHECKPOINT_VERSION, DEFAULT_CHUNK_SECONDS

logger = logging.getLogger(__name__)


class CheckpointMixin:
    """Checkpoint-based chunked transcription and media helpers."""

    def _checkpoint_root(self, job_id: str) -> Path:
        return Path(settings.transcript_storage_path) / job_id

    def _checkpoint_path(self, job_id: str) -> Path:
        return self._checkpoint_root(job_id) / "checkpoint.json"

    def _chunk_dir(self, job_id: str) -> Path:
        return self._checkpoint_root(job_id) / "chunks"

    def _load_checkpoint(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception as exc:
            logger.warning("Failed to read checkpoint %s: %s", path, exc)
        return None

    def _write_checkpoint(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _build_checkpoint(
        self,
        job: Job,
        *,
        audio_path: str,
        model_name: str,
        language: Optional[str],
        chunk_seconds: int,
        total_duration: float,
    ) -> Dict[str, Any]:
        return {
            "version": CHECKPOINT_VERSION,
            "job_id": job.id,
            "audio_path": audio_path,
            "model_name": model_name,
            "language": language,
            "chunk_seconds": chunk_seconds,
            "total_duration": total_duration,
            "next_index": 0,
            "segments": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _render_chunk(
        self, audio_path: str, chunk_path: Path, *, start: float, duration: float
    ) -> None:
        try:
            import ffmpeg  # type: ignore
        except ImportError as exc:
            raise RuntimeError("ffmpeg-python not installed") from exc

        chunk_path.parent.mkdir(parents=True, exist_ok=True)
        stream = ffmpeg.input(str(audio_path), ss=start, t=duration)
        out = ffmpeg.output(stream, str(chunk_path), format="wav", acodec="pcm_s16le")
        ffmpeg.run(out, overwrite_output=True, quiet=True)

    def _normalize_custom_vocabulary(self, raw: Optional[str]) -> Optional[str]:
        """Normalize custom vocabulary text into a concise prompt string."""
        if not raw:
            return None
        terms: list[str] = []
        seen: set[str] = set()
        for token in raw.replace("\r", "\n").replace(";", "\n").replace(",", "\n").split("\n"):
            term = token.strip()
            if not term:
                continue
            normalized = term.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            terms.append(term)
            if len(terms) >= 100:
                break
        if not terms:
            return None
        return "Custom vocabulary: " + ", ".join(terms)

    def _transcode_to_wav(self, src: Path, job_id: str) -> Path:
        """Transcode a source audio/video file to WAV for downstream processing."""
        try:
            import ffmpeg  # type: ignore
        except ImportError as exc:
            raise RuntimeError("ffmpeg-python not installed") from exc

        dst = Path(settings.media_storage_path) / f"{src.stem}-{job_id}-pcm.wav"
        dst.parent.mkdir(parents=True, exist_ok=True)
        stream = ffmpeg.input(str(src))
        out = ffmpeg.output(stream, str(dst), format="wav", acodec="pcm_s16le")
        ffmpeg.run(out, overwrite_output=True, quiet=True)
        return dst

    async def _transcribe_with_checkpoints(
        self,
        job: Job,
        db: AsyncSession,
        *,
        audio_path: str,
        model_name: str,
        language: Optional[str],
        initial_prompt: Optional[str],
        enable_timestamps: bool,
        model_obj: Any,
    ) -> Optional[Dict[str, Any]]:
        checkpoint_path = self._checkpoint_path(job.id)
        checkpoint = self._load_checkpoint(checkpoint_path)

        total_duration = None
        if checkpoint:
            total_duration = checkpoint.get("total_duration")
        if not total_duration:
            total_duration = self._probe_duration_seconds(Path(audio_path)) or job.duration
        if not total_duration:
            total_duration = float(settings.default_estimated_duration_seconds)

        chunk_seconds = (
            int(checkpoint.get("chunk_seconds", DEFAULT_CHUNK_SECONDS))
            if checkpoint
            else DEFAULT_CHUNK_SECONDS
        )
        if not checkpoint:
            checkpoint = self._build_checkpoint(
                job,
                audio_path=audio_path,
                model_name=model_name,
                language=language,
                chunk_seconds=chunk_seconds,
                total_duration=float(total_duration),
            )
        checkpoint.setdefault("segments", [])
        checkpoint.setdefault("next_index", 0)
        checkpoint["audio_path"] = audio_path
        checkpoint["model_name"] = model_name
        if language:
            checkpoint["language"] = language

        job.checkpoint_path = str(checkpoint_path)
        await db.commit()

        total_chunks = max(1, int(math.ceil(float(total_duration) / chunk_seconds)))
        next_index = int(checkpoint.get("next_index") or 0)
        segments: list[Dict[str, Any]] = checkpoint["segments"]
        if next_index >= total_chunks:
            logger.info(
                "Job %s checkpoint already complete (chunk %s of %s); proceeding to finalization",
                job.id,
                next_index,
                total_chunks,
            )
        elif next_index > 0:
            logger.info(
                "Job %s resuming transcription from checkpoint chunk %s of %s",
                job.id,
                next_index,
                total_chunks,
            )
        else:
            logger.info("Job %s starting transcription from chunk 0 of %s", job.id, total_chunks)

        for index in range(next_index, total_chunks):
            if await self._abort_if_cancelled(job, db, f"checkpoint chunk {index}"):
                return None
            if await self._abort_if_pausing(job, db, f"checkpoint chunk {index}"):
                checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._write_checkpoint(checkpoint_path, checkpoint)
                return None

            start = index * chunk_seconds
            duration = max(0.0, min(chunk_seconds, float(total_duration) - start))
            chunk_path = self._chunk_dir(job.id) / f"chunk-{index:04d}.wav"
            if not chunk_path.exists():
                try:
                    self._render_chunk(audio_path, chunk_path, start=start, duration=duration)
                except Exception as exc:
                    logger.warning(
                        "Chunk render failed for job %s (index %s): %s. Falling back to full-file transcription.",
                        job.id,
                        index,
                        exc,
                    )
                    transcript_result = await self.transcribe_audio(
                        audio_path=audio_path,
                        model_name=model_name,
                        language=language,
                        initial_prompt=initial_prompt,
                        enable_timestamps=enable_timestamps,
                        enable_speaker_detection=False,
                        model_obj=model_obj,
                    )
                    if checkpoint_path.exists():
                        with suppress(Exception):
                            checkpoint_path.unlink()
                    job.checkpoint_path = None
                    await db.commit()
                    return transcript_result

            chunk_result = await self.transcribe_audio(
                audio_path=str(chunk_path),
                model_name=model_name,
                language=language,
                initial_prompt=initial_prompt,
                enable_timestamps=enable_timestamps,
                enable_speaker_detection=False,
                model_obj=model_obj,
            )

            offset = start
            for seg in chunk_result.get("segments", []):
                segments.append(
                    {
                        "id": seg.get("id"),
                        "start": float(seg.get("start", 0.0)) + offset,
                        "end": float(seg.get("end", 0.0)) + offset,
                        "text": seg.get("text", ""),
                        "speaker": seg.get("speaker"),
                    }
                )

            if not checkpoint.get("language"):
                checkpoint["language"] = chunk_result.get("language")

            checkpoint["segments"] = segments
            checkpoint["next_index"] = index + 1
            checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write_checkpoint(checkpoint_path, checkpoint)

            asr_seconds, _, total_seconds = self._estimate_stage_seconds(
                job, duration_hint=total_duration
            )
            asr_weight = asr_seconds / total_seconds if total_seconds else 1.0
            progress_ratio = (index + 1) / total_chunks
            estimated_progress = int(progress_ratio * asr_weight * 100)
            job.progress_percent = max(int(job.progress_percent or 0), estimated_progress)
            job.progress_stage = "transcribing"
            job.estimated_time_left = max(int((total_chunks - index - 1) * chunk_seconds), 0)
            job.updated_at = datetime.now(timezone.utc)
            await db.commit()

        normalized_segments = self._normalize_segments(segments)
        formatted_text = self._format_full_text(
            normalized_segments,
            include_timestamps=enable_timestamps,
            include_speakers=False,
        )
        transcript_result = {
            "text": formatted_text,
            "segments": normalized_segments,
            "language": checkpoint.get("language") or "unknown",
            "duration": float(total_duration),
        }
        return transcript_result
