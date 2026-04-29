from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.auth import require_auth
from app.database import get_db
from app.models import Artifact
from app.schemas import ArtifactOut, ArtifactCreate

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.get("", response_model=list[ArtifactOut])
async def list_artifacts(db: AsyncSession = Depends(get_db), _=Depends(require_auth)):
    result = await db.execute(select(Artifact).order_by(Artifact.created_at.desc()))
    return result.scalars().all()


@router.get("/{artifact_id}", response_model=ArtifactOut)
async def get_artifact(artifact_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_auth)):
    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


@router.delete("/{artifact_id}", status_code=204)
async def delete_artifact(artifact_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_auth)):
    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    await db.delete(artifact)
    await db.commit()
