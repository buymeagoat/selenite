from fastapi import APIRouter, Depends
from app.auth import require_auth
from app.processors.registry import registry
from app.schemas import ProcessorOut

router = APIRouter(prefix="/api/processors", tags=["processors"])


@router.get("", response_model=list[ProcessorOut])
async def list_processors(_=Depends(require_auth)):
    return [
        ProcessorOut(
            key=p.key,
            display_name=p.display_name,
            processor_type=p.processor_type,
            available=p.available,
        )
        for p in registry.list_all()
    ]
