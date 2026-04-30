import asyncio
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from app.auth import require_auth
from app.database import AsyncSessionLocal
from app.models import Job

router = APIRouter(prefix="/api/jobs", tags=["stream"])


@router.get("/stream")
async def stream_jobs(_=Depends(require_auth)):
    async def event_generator():
        seen: dict[str, str] = {}
        while True:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Job).order_by(Job.created_at.desc()).limit(50)
                )
                jobs = result.scalars().all()

            updates = []
            for job in jobs:
                key = f"{job.id}:{job.status}:{job.progress}"
                if seen.get(job.id) != key:
                    seen[job.id] = key
                    updates.append({
                        "id": job.id,
                        "artifact_id": job.artifact_id,
                        "stage": job.stage,
                        "processor": job.processor,
                        "status": job.status,
                        "progress": job.progress,
                        "error": job.error,
                    })

            if updates:
                yield f"data: {json.dumps(updates)}\n\n"

            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
