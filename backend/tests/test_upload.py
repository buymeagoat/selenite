import pytest
from httpx import AsyncClient
from app.auth import hash_password
from app.config_store import set_config


async def _login(client, db_session):
    await set_config(db_session, "auth.password_hash", hash_password("testpass"))
    r = await client.post("/api/auth/login", json={"password": "testpass"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_upload_requires_auth(client: AsyncClient):
    r = await client.post("/api/upload", files={"file": ("test.mp3", b"fake", "audio/mpeg")})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_upload_unsupported_type(client: AsyncClient, db_session):
    await _login(client, db_session)
    r = await client.post(
        "/api/upload",
        data={"asr_processor": "faster_whisper_large_v3", "diarizer_processor": "pyannote_3_1"},
        files={"file": ("test.pdf", b"fake", "application/pdf")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_upload_audio_creates_artifact_and_jobs(client: AsyncClient, db_session, tmp_path, monkeypatch):
    import app.upload as upload_mod
    monkeypatch.setattr(upload_mod, "UPLOAD_DIR", tmp_path)

    await _login(client, db_session)
    r = await client.post(
        "/api/upload",
        data={"asr_processor": "faster_whisper_large_v3", "diarizer_processor": "pyannote_3_1"},
        files={"file": ("test.mp3", b"fake audio data", "audio/mpeg")},
    )
    assert r.status_code == 200
    body = r.json()
    assert "artifact_id" in body
    assert "asr_job_id" in body
    assert "diarize_job_id" in body

    ra = await client.get(f"/api/artifacts/{body['artifact_id']}")
    assert ra.status_code == 200
    assert ra.json()["status"] == "processing"
    assert ra.json()["source_type"] == "audio"
