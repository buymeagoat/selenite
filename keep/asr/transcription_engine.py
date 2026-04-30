"""Multi-engine transcription dispatch mixin."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class TranscriptionEngineMixin:
    """Dispatch transcription to the correct ASR backend."""

    async def transcribe_audio(
        self,
        audio_path: str,
        model_name: str,
        language: Optional[str] = None,
        initial_prompt: Optional[str] = None,
        enable_timestamps: bool = True,
        enable_speaker_detection: bool = False,
        *,
        model_obj: Any = None,
    ) -> Dict[str, Any]:
        """Transcribe an audio/video file using Whisper.

        Args:
            audio_path: Path to audio/video file
            model_name: Whisper model to use
            language: Language code (e.g., 'en', 'es') or None for auto-detect
            enable_timestamps: Include word-level timestamps
            enable_speaker_detection: Enable speaker diarization (requires pyannote)
            model_obj: Optional pre-loaded whisper model (bypasses internal load)

        Returns:
            Dictionary with transcription results.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Starting transcription: {audio_path} with model {model_name}")

        try:
            backend = model_obj or await self.load_model(model_name)
            provider = "whisper"
            if isinstance(backend, dict):
                provider = backend.get("provider", provider)

            if provider == "whisper":
                model = backend.get("model", backend) if isinstance(backend, dict) else backend
                transcribe_options = {
                    "language": language if language and language != "auto" else None,
                    "task": "transcribe",
                    "verbose": False,
                }
                if initial_prompt:
                    transcribe_options["initial_prompt"] = initial_prompt
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: model.transcribe(audio_path, **transcribe_options)
                )
            elif provider == "faster-whisper":
                model = backend["model"] if isinstance(backend, dict) else backend
                loop = asyncio.get_event_loop()

                def _run_faster():
                    segments_iter, info = model.transcribe(
                        audio_path,
                        language=language if language and language != "auto" else None,
                        initial_prompt=initial_prompt,
                    )
                    segments = [
                        {"id": idx, "start": seg.start, "end": seg.end, "text": seg.text}
                        for idx, seg in enumerate(segments_iter)
                    ]
                    return {
                        "text": " ".join(
                            (seg.get("text") or "").strip() for seg in segments
                        ).strip(),
                        "segments": segments,
                        "language": getattr(info, "language", language or "unknown"),
                        "duration": segments[-1]["end"] if segments else 0,
                    }

                result = await loop.run_in_executor(None, _run_faster)
            elif provider == "transformers":
                asr_pipeline = backend["pipeline"]
                loop = asyncio.get_event_loop()
                raw = await loop.run_in_executor(
                    None, lambda: asr_pipeline(audio_path, return_timestamps=True)
                )
                chunks = raw.get("chunks") or []
                segments = []
                for idx, chunk in enumerate(chunks):
                    start, end = chunk.get("timestamp") or (None, None)
                    segments.append(
                        {
                            "id": idx,
                            "start": float(start) if start is not None else 0.0,
                            "end": float(end) if end is not None else 0.0,
                            "text": chunk.get("text", ""),
                        }
                    )
                result = {
                    "text": raw.get("text", ""),
                    "segments": segments,
                    "language": language or "unknown",
                    "duration": segments[-1]["end"] if segments else 0,
                }
            elif provider == "openai-api":
                api_url = os.getenv("EXTERNAL_ASR_API_URL", "").strip()
                api_key = os.getenv("EXTERNAL_ASR_API_KEY", "").strip()
                timeout_seconds = int(os.getenv("EXTERNAL_ASR_TIMEOUT_SECONDS", "120"))
                if not api_url or not api_key:
                    raise RuntimeError(
                        "External ASR provider is not configured (EXTERNAL_ASR_API_URL + EXTERNAL_ASR_API_KEY)."
                    )
                selected_model = (
                    backend.get("model_name") if isinstance(backend, dict) else model_name
                ) or model_name
                with open(audio_path, "rb") as handle:
                    files = {"file": (Path(audio_path).name, handle, "application/octet-stream")}
                    data = {"model": selected_model, "response_format": "verbose_json"}
                    if language and language != "auto":
                        data["language"] = language
                    if initial_prompt:
                        data["prompt"] = initial_prompt
                    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                        response = await client.post(
                            api_url.rstrip("/"),
                            headers={"Authorization": f"Bearer {api_key}"},
                            data=data,
                            files=files,
                        )
                response.raise_for_status()
                payload = response.json()
                result = {
                    "text": payload.get("text", ""),
                    "segments": payload.get("segments", []),
                    "language": payload.get("language", language or "unknown"),
                    "duration": payload.get("duration", 0),
                }
            else:
                raise RuntimeError(f"Unsupported ASR provider backend: {provider}")

            normalized_segments = self._normalize_segments(result.get("segments", []))
            formatted_text = self._format_full_text(
                normalized_segments,
                include_timestamps=enable_timestamps,
                include_speakers=enable_speaker_detection,
            )
            transcript_result = {
                "text": formatted_text or result["text"].strip(),
                "segments": normalized_segments,
                "language": result.get("language", "unknown"),
                "duration": result.get("duration", 0.0),
            }

            logger.info(
                f"Transcription complete: {len(transcript_result['segments'])} segments, "
                f"{transcript_result['duration']:.1f}s duration"
            )

            return transcript_result

        except Exception as exc:
            logger.error(f"Transcription failed for {audio_path}: {exc}")
            raise RuntimeError(f"Transcription failed: {str(exc)}") from exc
