import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import require_auth
from app.database import get_db
from app.models import Artifact, Job
from app.upload import upload_path, source_type_from_extension
from app.queue import enqueue
from datetime import datetime, timezone

router = APIRouter(prefix="/api/upload", tags=["upload"])

CHUNK_SIZE = 1024 * 1024


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    asr_processor: str = Form("faster_whisper_large_v3"),
    diarizer_processor: str = Form("pyannote_3_1"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_auth),
):
    filename = file.filename or "upload"
    source_type = source_type_from_extension(filename)
    if not source_type:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {Path(filename).suffix}")

    artifact_id = str(uuid.uuid4())
    dest = upload_path(artifact_id, filename)

    with open(dest, "wb") as f:
        while chunk := await file.read(CHUNK_SIZE):
            f.write(chunk)

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    artifact = Artifact(
        id=artifact_id,
        filename=filename,
        source_type=source_type,
        status="processing",
        created_at=now,
        updated_at=now,
    )
    db.add(artifact)

    asr_job_id = str(uuid.uuid4())
    asr_job = Job(
        id=asr_job_id,
        artifact_id=artifact_id,
        stage="asr",
        processor=asr_processor,
        status="queued",
        created_at=now,
        updated_at=now,
    )
    db.add(asr_job)

    diarize_job_id = str(uuid.uuid4())
    diarize_job = Job(
        id=diarize_job_id,
        artifact_id=artifact_id,
        stage="diarize",
        processor=diarizer_processor,
        status="queued",
        created_at=now,
        updated_at=now,
    )
    db.add(diarize_job)

    await db.commit()

    enqueue(asr_job_id)

    return {"artifact_id": artifact_id, "asr_job_id": asr_job_id, "diarize_job_id": diarize_job_id}
