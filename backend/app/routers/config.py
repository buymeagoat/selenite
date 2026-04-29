from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import require_auth
from app.database import get_db
from app.config_store import get_config, set_config

router = APIRouter(prefix="/api/config", tags=["config"])

ALLOWED_KEYS = {
    "processor.asr.active",
    "processor.diarizer.active",
    "processor.ocr.active",
    "processor.llm.active",
    "processor.pyannote.hf_token",
    "processor.ollama.model",
    "processor.ollama.host",
    "output.folder",
}


class ConfigUpdate(BaseModel):
    value: str


@router.get("/{key}")
async def get_config_key(key: str, db: AsyncSession = Depends(get_db), _=Depends(require_auth)):
    if key not in ALLOWED_KEYS:
        raise HTTPException(status_code=404, detail="Unknown config key")
    value = await get_config(db, key)
    return {"key": key, "value": value}


@router.put("/{key}")
async def set_config_key(key: str, body: ConfigUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_auth)):
    if key not in ALLOWED_KEYS:
        raise HTTPException(status_code=404, detail="Unknown config key")
    await set_config(db, key, body.value)
    return {"key": key, "value": body.value}
