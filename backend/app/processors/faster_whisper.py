import asyncio
import logging
from pathlib import Path
from app.processors.base import ASRResult, TranscriptSegment, WordTimestamp

logger = logging.getLogger(__name__)

MODEL_SIZE = "large-v3"
_model = None


def _load_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading faster-whisper large-v3 on CUDA...")
        _model = WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")
        logger.info("faster-whisper loaded")
    return _model


def _unload_model():
    global _model
    if _model is not None:
        del _model
        _model = None
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass
        logger.info("faster-whisper unloaded")


class FasterWhisperProcessor:
    key = "faster_whisper_large_v3"
    display_name = "Faster Whisper Large v3"

    def available(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    async def transcribe(self, audio_path: Path) -> ASRResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, audio_path)

    def _transcribe_sync(self, audio_path: Path) -> ASRResult:
        model = _load_model()
        try:
            segments_gen, info = model.transcribe(
                str(audio_path),
                word_timestamps=True,
                vad_filter=True,
            )
            segments = []
            for seg in segments_gen:
                words = [
                    WordTimestamp(word=w.word.strip(), start=w.start, end=w.end)
                    for w in (seg.words or [])
                ]
                segments.append(TranscriptSegment(
                    text=seg.text.strip(),
                    start=seg.start,
                    end=seg.end,
                    words=words,
                ))
            return ASRResult(
                segments=segments,
                language=info.language,
                duration=info.duration,
            )
        finally:
            _unload_model()
