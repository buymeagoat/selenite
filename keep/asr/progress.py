"""Progress drain, simulation, and concurrency slot management mixin."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.job import Job
from app.models.transcript import Transcript
from app.services.cloud_storage import mirror_file_to_cloud

logger = logging.getLogger(__name__)


def _coerce_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class ProgressMixin:
    """Background progress updaters, test simulation, and slot management."""

    async def _drain_progress_during_transcription(
        self, job_id: str, *, cap_percent: int = 95, interval: float = 2.0
    ) -> None:
        """Advance progress based on elapsed time versus estimated total."""
        try:
            while True:
                await asyncio.sleep(interval)
                async with AsyncSessionLocal() as session:
                    job_obj = await session.get(Job, job_id)
                    if not job_obj or job_obj.status != "processing" or not job_obj.started_at:
                        return

                    est_total = (
                        job_obj.estimated_total_seconds
                        or settings.default_estimated_duration_seconds
                    )
                    started_at = _coerce_utc(job_obj.started_at)
                    if started_at is None:
                        return
                    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
                    if elapsed > est_total:
                        # Expand estimate if we're running long to avoid pinning at 95%
                        est_total = int(elapsed * 1.25)
                        job_obj.estimated_total_seconds = est_total

                    progress = int((elapsed / est_total) * 100)
                    progress = max(progress, int(job_obj.progress_percent or 0))
                    progress = min(progress, cap_percent)
                    job_obj.progress_percent = progress

                    remaining = max(int(est_total - elapsed), 0)
                    job_obj.estimated_time_left = remaining if progress < 100 else None
                    job_obj.updated_at = datetime.now(timezone.utc)
                    await session.commit()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # Best-effort, don't fail transcription for this
            logger.warning("Progress updater failed for job %s: %s", job_id, exc)

    async def _drain_progress_during_diarization(
        self,
        job_id: str,
        *,
        start_percent: int,
        end_percent: int,
        expected_seconds: float,
        interval: float = 2.0,
    ) -> None:
        """Advance progress during diarization using a time-based heuristic."""
        try:
            diar_start = datetime.now(timezone.utc)
            while True:
                await asyncio.sleep(interval)
                async with AsyncSessionLocal() as session:
                    job_obj = await session.get(Job, job_id)
                    if (
                        not job_obj
                        or job_obj.status != "processing"
                        or job_obj.progress_stage != "diarizing"
                    ):
                        return
                    elapsed = (datetime.now(timezone.utc) - diar_start).total_seconds()
                    denom = expected_seconds or 1.0
                    if elapsed > denom:
                        denom = elapsed * 1.25
                    ratio = min(max(elapsed / denom, 0.0), 1.0)
                    target = int(start_percent + ((end_percent - start_percent) * ratio))
                    job_obj.progress_percent = max(int(job_obj.progress_percent or 0), target)
                    job_obj.updated_at = datetime.now(timezone.utc)
                    await session.commit()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # Best-effort, don't fail transcription for this
            logger.warning("Diarization progress updater failed for job %s: %s", job_id, exc)

    async def _simulate_transcription(self, job: Job, db: AsyncSession) -> None:
        """Fast path for tests to avoid loading large Whisper models."""
        transcript_text = f"Simulated transcript for {job.original_filename}"
        segments = [
            {
                "id": 0,
                "start": 0.0,
                "end": float(job.duration or 10.0),
                "text": transcript_text,
                "speaker": "Speaker 1" if job.has_speaker_labels else None,
            }
        ]
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        job.progress_percent = 0
        job.progress_stage = "loading_model"
        job.estimated_total_seconds = job.estimated_total_seconds or 180
        job.estimated_time_left = job.estimated_total_seconds
        await db.commit()

        await asyncio.sleep(0.2)

        job.progress_percent = 50
        job.progress_stage = "transcribing"
        job.estimated_time_left = 30
        job.updated_at = datetime.now(timezone.utc)
        await db.commit()

        await asyncio.sleep(0.2)

        job.progress_percent = 95
        job.progress_stage = "finalizing"
        job.estimated_time_left = 5
        job.updated_at = datetime.now(timezone.utc)
        await db.commit()

        await asyncio.sleep(0.2)

        transcript_path = Path(settings.transcript_storage_path) / f"{job.id}.txt"
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        formatted_text = self._format_full_text(
            segments,
            include_timestamps=bool(job.has_timestamps),
            include_speakers=bool(job.has_speaker_labels),
        )
        transcript_path.write_text(formatted_text or transcript_text, encoding="utf-8")
        metadata_path = transcript_path.with_suffix(".json")
        metadata = {
            "text": formatted_text or transcript_text,
            "segments": segments,
            "language": job.language_detected or "en",
            "duration": job.duration or 10.0,
            "options": {
                "has_timestamps": bool(job.has_timestamps),
                "has_speaker_labels": bool(job.has_speaker_labels),
            },
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        mirror_file_to_cloud(transcript_path)
        mirror_file_to_cloud(metadata_path)

        transcript_db = Transcript(
            job_id=job.id,
            format="txt",
            file_path=str(transcript_path),
            file_size=len(transcript_text.encode("utf-8")),
        )
        db.add(transcript_db)

        started_at = _coerce_utc(job.started_at)
        if started_at:
            job.processing_seconds = int(job.processing_seconds or 0) + int(
                (datetime.now(timezone.utc) - started_at).total_seconds()
            )
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.progress_percent = 100
        job.progress_stage = None
        job.estimated_time_left = None
        job.duration = job.duration or 60.0
        job.language_detected = job.language_detected or "en"
        job.speaker_count = job.speaker_count or 1
        job.transcript_path = str(transcript_path)
        job.updated_at = datetime.now(timezone.utc)

        await db.commit()

    async def _wait_for_processing_slot(self, db: AsyncSession) -> None:
        """Ensure processing job count stays within configured limit (testing helper)."""
        max_jobs = settings.max_concurrent_jobs
        if max_jobs <= 0:
            return
        while True:
            result = await db.execute(
                select(func.count()).select_from(Job).where(Job.status == "processing")
            )
            count = result.scalar_one() or 0
            if count < max_jobs:
                return
            await asyncio.sleep(0.02)
