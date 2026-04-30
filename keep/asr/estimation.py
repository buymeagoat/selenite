"""Processing-time estimation mixin."""

from typing import Optional

from app.config import settings
from app.models.job import Job


class EstimationMixin:
    """Helpers for estimating transcription and diarization durations."""

    def _model_speed_factor(self, model_name: str) -> float:
        """Approximate realtime factor per model size."""
        lookup = {
            "tiny": 0.5,
            "base": 0.8,
            "small": 1.0,
            "medium": 1.3,
            "large": 1.6,
            "large-v3": 1.6,
        }
        return lookup.get(model_name, 1.3)

    def _diarization_speed_factor(self, job: Job) -> float:
        """Approximate realtime factor for diarization."""
        provider = (job.diarizer_provider_used or "").lower()
        if provider == "vad":
            return 0.1
        return 0.75

    def _estimate_stage_seconds(
        self, job: Job, duration_hint: Optional[float] = None
    ) -> tuple[float, float, float]:
        """Estimate ASR/diarization seconds and total."""
        duration = duration_hint if duration_hint is not None else job.duration
        base_seconds = float(duration or settings.default_estimated_duration_seconds)
        asr_seconds = max(base_seconds * self._model_speed_factor(job.model_used or "unknown"), 1.0)
        diar_seconds = 0.0
        if job.has_speaker_labels:
            diar_seconds = max(base_seconds * self._diarization_speed_factor(job), 1.0)
        total_seconds = max(asr_seconds + diar_seconds, 1.0)
        return asr_seconds, diar_seconds, total_seconds

    def _estimate_total_seconds(self, job: Job, duration_hint: Optional[float] = None) -> int:
        """Estimate total processing time based on duration, model, and diarization."""
        _, _, total_seconds = self._estimate_stage_seconds(job, duration_hint=duration_hint)
        estimate = int(max(total_seconds, 60))
        return estimate
