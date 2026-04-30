import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Job, Artifact

logger = logging.getLogger(__name__)

_queue: asyncio.Queue[str] = asyncio.Queue()
_worker_task: asyncio.Task | None = None


def enqueue(job_id: str) -> None:
    _queue.put_nowait(job_id)


async def _run_job(job_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        job.status = "running"
        job.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

        try:
            from app.pipeline.audio import run_audio_stage
            await run_audio_stage(job, db)
        except Exception as e:
            logger.exception(f"Job {job_id} failed: {e}")
            job.status = "failed"
            job.error = str(e)
            job.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

            result2 = await db.execute(select(Artifact).where(Artifact.id == job.artifact_id))
            artifact = result2.scalar_one_or_none()
            if artifact:
                artifact.status = "failed"
                artifact.error = f"stage: {job.stage} — {e}"
                artifact.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

            await db.commit()


async def _worker() -> None:
    logger.info("Job queue worker started")
    while True:
        job_id = await _queue.get()
        try:
            await _run_job(job_id)
        except Exception:
            logger.exception(f"Unhandled error processing job {job_id}")
        finally:
            _queue.task_done()


def start_worker() -> None:
    global _worker_task
    _worker_task = asyncio.create_task(_worker())
    logger.info("Queue worker task created")


async def stop_worker() -> None:
    global _worker_task
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
