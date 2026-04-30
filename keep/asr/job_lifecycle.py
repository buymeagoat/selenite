"""Job lifecycle state management mixin (cancel / pause helpers)."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.system_preferences import SystemPreferences

logger = logging.getLogger(__name__)


def _coerce_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class JobLifecycleMixin:
    """Cancel, pause, and ancillary lifecycle helpers."""

    def _is_cancelled_state(self, job: Job) -> bool:
        return job.status in {"cancelled", "cancelling"}

    def _is_pause_state(self, job: Job) -> bool:
        return job.status in {"paused", "pausing"}

    async def _finalize_cancellation(self, job: Job, db: AsyncSession, context: str) -> None:
        """Finalize a cancellation by ensuring consistent state and logging."""
        started_at = _coerce_utc(job.started_at)
        if started_at:
            job.processing_seconds = int(job.processing_seconds or 0) + int(
                (datetime.now(timezone.utc) - started_at).total_seconds()
            )
        job.status = "cancelled"
        job.progress_stage = None
        job.estimated_time_left = None
        if job.completed_at is None:
            job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(f"Job {job.id} cancellation acknowledged ({context})")

    async def _finalize_pause(self, job: Job, db: AsyncSession, context: str) -> None:
        """Finalize a pause by ensuring consistent state and logging."""
        started_at = _coerce_utc(job.started_at)
        if started_at:
            job.processing_seconds = int(job.processing_seconds or 0) + int(
                (datetime.now(timezone.utc) - started_at).total_seconds()
            )
        job.status = "paused"
        job.paused_at = job.paused_at or datetime.now(timezone.utc)
        job.progress_stage = "paused"
        job.estimated_time_left = None
        await db.commit()
        logger.info("Job %s pause acknowledged (%s)", job.id, context)

    async def _abort_if_cancelled(self, job: Job, db: AsyncSession, context: str) -> bool:
        await db.refresh(job)
        if self._is_cancelled_state(job):
            await self._finalize_cancellation(job, db, context)
            return True
        return False

    async def _abort_if_pausing(self, job: Job, db: AsyncSession, context: str) -> bool:
        await db.refresh(job)
        if job.status == "pausing":
            await self._finalize_pause(job, db, context)
            return True
        if job.status == "paused":
            return True
        return False

    async def _get_system_preferences(self, db: AsyncSession) -> SystemPreferences:
        result = await db.execute(select(SystemPreferences).where(SystemPreferences.id == 1))
        prefs = result.scalar_one_or_none()
        if not prefs:
            prefs = SystemPreferences(
                id=1,
                server_time_zone="UTC",
                transcode_to_wav=True,
                enable_empty_weights=False,
            )
            db.add(prefs)
            await db.commit()
            await db.refresh(prefs)
        return prefs

    @staticmethod
    def _append_execution_notes(job: Job, notes: list[str]) -> None:
        """Append one or more notes to the job's execution_notes field."""
        if not notes:
            return
        existing = job.execution_notes or ""
        addition = "\n".join(notes)
        job.execution_notes = f"{existing}\n{addition}".strip() if existing else addition

    def _probe_duration_seconds(self, audio_path: Path) -> Optional[float]:
        """Best-effort duration probe using ffmpeg, returning None on failure."""
        try:
            import ffmpeg
        except ImportError:
            return None

        try:
            probe = ffmpeg.probe(str(audio_path))
            fmt = probe.get("format") or {}
            dur = fmt.get("duration")
            if dur is not None:
                return float(dur)
        except Exception as exc:  # best effort
            logger.warning("Could not probe duration for %s: %s", audio_path, exc)
        return None
