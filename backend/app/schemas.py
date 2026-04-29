from datetime import datetime
from pydantic import BaseModel


class ProcessorOut(BaseModel):
    key: str
    display_name: str
    processor_type: str
    available: bool


class ConfigOut(BaseModel):
    key: str
    value: str


class ArtifactOut(BaseModel):
    id: str
    filename: str
    source_type: str
    status: str
    content: str | None
    metadata_json: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ArtifactCreate(BaseModel):
    filename: str
    source_type: str


class JobOut(BaseModel):
    id: str
    artifact_id: str
    stage: str
    stage_task: str | None
    processor: str
    status: str
    progress: int
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
