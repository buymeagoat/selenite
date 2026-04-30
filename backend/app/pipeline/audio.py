import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Job, Artifact
from app.processors.registry import registry
from app.pipeline.transcript import diarized_to_markdown
from app.upload import UPLOAD_DIR

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _get_artifact(db: AsyncSession, artifact_id: str) -> Artifact:
    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    return result.scalar_one()


async def _get_diarize_job(db: AsyncSession, artifact_id: str) -> Job | None:
    result = await db.execute(
        select(Job).where(Job.artifact_id == artifact_id, Job.stage == "diarize")
    )
    return result.scalar_one_or_none()


async def run_audio_stage(job: Job, db: AsyncSession) -> None:
    artifact = await _get_artifact(db, job.artifact_id)
    audio_path = UPLOAD_DIR / job.artifact_id / artifact.filename

    if job.stage == "asr":
        await _run_asr(job, artifact, audio_path, db)
    elif job.stage == "diarize":
        await _run_diarize(job, artifact, audio_path, db)
    else:
        raise ValueError(f"Unknown audio stage: {job.stage}")


async def _run_asr(job: Job, artifact: Artifact, audio_path: Path, db: AsyncSession) -> None:
    from app.queue import enqueue

    processor = registry.get_asr(job.processor)
    if not processor:
        raise RuntimeError(f"ASR processor not found: {job.processor}")
    if not processor.available():
        raise RuntimeError(f"ASR processor not available: {job.processor}")

    logger.info(f"Starting ASR: {job.processor} on {audio_path}")
    job.progress = 10
    job.updated_at = _now()
    await db.commit()

    asr_result = await processor.transcribe(audio_path)

    job.status = "complete"
    job.progress = 100
    job.output_json = json.dumps({
        "segments": [
            {
                "text": s.text,
                "start": s.start,
                "end": s.end,
                "words": [{"word": w.word, "start": w.start, "end": w.end} for w in s.words],
            }
            for s in asr_result.segments
        ],
        "language": asr_result.language,
        "duration": asr_result.duration,
    })
    job.updated_at = _now()
    await db.commit()

    diarize_job = await _get_diarize_job(db, job.artifact_id)
    if diarize_job:
        enqueue(diarize_job.id)
    else:
        raw_text = "\n\n".join(s.text for s in asr_result.segments)
        artifact.content = raw_text
        artifact.status = "complete"
        artifact.updated_at = _now()
        await db.commit()


async def _run_diarize(job: Job, artifact: Artifact, audio_path: Path, db: AsyncSession) -> None:
    from app.processors.base import ASRResult, TranscriptSegment, WordTimestamp

    processor = registry.get_diarizer(job.processor)
    if not processor:
        raise RuntimeError(f"Diarizer not found: {job.processor}")
    if not processor.available():
        raise RuntimeError(f"Diarizer not available: {job.processor}")

    asr_job_result = await db.execute(
        select(Job).where(Job.artifact_id == job.artifact_id, Job.stage == "asr")
    )
    asr_job = asr_job_result.scalar_one_or_none()
    if not asr_job or not asr_job.output_json:
        raise RuntimeError("ASR job output not found")

    asr_data = json.loads(asr_job.output_json)
    asr_result = ASRResult(
        segments=[
            TranscriptSegment(
                text=s["text"],
                start=s["start"],
                end=s["end"],
                words=[WordTimestamp(**w) for w in s.get("words", [])],
            )
            for s in asr_data["segments"]
        ],
        language=asr_data["language"],
        duration=asr_data["duration"],
    )

    logger.info(f"Starting diarization: {job.processor}")
    job.progress = 10
    job.updated_at = _now()
    await db.commit()

    diarized = await processor.diarize(audio_path, asr_result)

    markdown = diarized_to_markdown(diarized)

    job.status = "complete"
    job.progress = 100
    job.updated_at = _now()
    await db.commit()

    artifact.content = markdown
    artifact.status = "complete"
    artifact.metadata_json = json.dumps({
        "speaker_count": diarized.speaker_count,
        "language": asr_data["language"],
        "duration": asr_data["duration"],
        "processor_chain": [asr_job.processor, job.processor],
    })
    artifact.updated_at = _now()
    await db.commit()
