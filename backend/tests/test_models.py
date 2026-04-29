import pytest
from sqlalchemy import select
from app.models import Artifact, Job, Tag, Config


@pytest.mark.asyncio
async def test_artifact_create(db_session):
    artifact = Artifact(filename="test.mp3", source_type="audio")
    db_session.add(artifact)
    await db_session.commit()
    await db_session.refresh(artifact)
    assert artifact.id is not None
    assert artifact.status == "pending"
    assert artifact.created_at is not None


@pytest.mark.asyncio
async def test_config_create(db_session):
    cfg = Config(key="auth.password_hash", value="$2b$12$fakehash")
    db_session.add(cfg)
    await db_session.commit()
    result = await db_session.execute(select(Config).where(Config.key == "auth.password_hash"))
    found = result.scalar_one()
    assert found.value == "$2b$12$fakehash"
