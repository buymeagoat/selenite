import asyncio
import logging
from pathlib import Path
from app.processors.base import ASRResult, DiarizedResult, DiarizedSegment

logger = logging.getLogger(__name__)

_pipeline = None


def _load_pipeline(hf_token: str):
    global _pipeline
    if _pipeline is None:
        from pyannote.audio import Pipeline
        import torch
        logger.info("Loading pyannote speaker-diarization-3.1...")
        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token,
        )
        _pipeline.to(torch.device("cuda"))
        logger.info("pyannote pipeline loaded")
    return _pipeline


def _unload_pipeline():
    global _pipeline
    if _pipeline is not None:
        del _pipeline
        _pipeline = None
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass
        logger.info("pyannote pipeline unloaded")


def _merge_asr_diarization(asr_result: ASRResult, diarization) -> DiarizedResult:
    turns = []
    for segment, _, speaker in diarization.itertracks(yield_label=True):
        turns.append((segment.start, segment.end, speaker))

    def speaker_at(t: float) -> str:
        for start, end, speaker in turns:
            if start <= t <= end:
                return speaker
        if not turns:
            return "Speaker 1"
        nearest = min(turns, key=lambda x: min(abs(x[0] - t), abs(x[1] - t)))
        return nearest[2]

    diarized: list[DiarizedSegment] = []
    current_speaker = None
    current_words: list[str] = []
    current_start = 0.0
    current_end = 0.0

    for seg in asr_result.segments:
        if seg.words:
            for word in seg.words:
                spk = speaker_at((word.start + word.end) / 2)
                if spk != current_speaker:
                    if current_speaker and current_words:
                        diarized.append(DiarizedSegment(
                            speaker=current_speaker,
                            text=" ".join(current_words),
                            start=current_start,
                            end=current_end,
                        ))
                    current_speaker = spk
                    current_words = [word.word]
                    current_start = word.start
                    current_end = word.end
                else:
                    current_words.append(word.word)
                    current_end = word.end
        else:
            spk = speaker_at((seg.start + seg.end) / 2)
            if spk != current_speaker:
                if current_speaker and current_words:
                    diarized.append(DiarizedSegment(
                        speaker=current_speaker,
                        text=" ".join(current_words),
                        start=current_start,
                        end=current_end,
                    ))
                current_speaker = spk
                current_words = [seg.text]
                current_start = seg.start
                current_end = seg.end
            else:
                current_words.append(seg.text)
                current_end = seg.end

    if current_speaker and current_words:
        diarized.append(DiarizedSegment(
            speaker=current_speaker,
            text=" ".join(current_words),
            start=current_start,
            end=current_end,
        ))

    speakers = {seg.speaker for seg in diarized}
    return DiarizedResult(segments=diarized, speaker_count=len(speakers))


class PyannoteDiarizer:
    key = "pyannote_3_1"
    display_name = "Pyannote Speaker Diarization 3.1"

    def available(self) -> bool:
        try:
            import torch
            import pyannote.audio  # noqa
            return torch.cuda.is_available()
        except ImportError:
            return False

    async def diarize(self, audio_path: Path, asr_result: ASRResult) -> DiarizedResult:
        from app.config_store import get_config
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            hf_token = await get_config(db, "processor.pyannote.hf_token")
        if not hf_token:
            raise RuntimeError("HuggingFace token not configured. Set processor.pyannote.hf_token in Settings.")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._diarize_sync, audio_path, asr_result, hf_token)

    def _diarize_sync(self, audio_path: Path, asr_result: ASRResult, hf_token: str) -> DiarizedResult:
        pipeline = _load_pipeline(hf_token)
        try:
            diarization = pipeline(str(audio_path))
            return _merge_asr_diarization(asr_result, diarization)
        finally:
            _unload_pipeline()
