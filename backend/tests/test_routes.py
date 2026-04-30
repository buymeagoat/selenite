import pytest
from httpx import AsyncClient
from app.auth import hash_password
from app.config_store import set_config
from app.models import Artifact


async def _login(client: AsyncClient, db_session, password: str = "testpass"):
    await set_config(db_session, "auth.password_hash", hash_password(password))
    r = await client.post("/api/auth/login", json={"password": password})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_processors_requires_auth(client: AsyncClient):
    r = await client.get("/api/processors")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_processors_list(client: AsyncClient, db_session):
    await _login(client, db_session)
    r = await client.get("/api/processors")
    assert r.status_code == 200
    data = r.json()
    keys = {p["key"] for p in data}
    assert "faster_whisper_large_v3" in keys
    assert "pyannote_3_1" in keys
    assert "glm_ocr" in keys
    assert "ollama_gemma" in keys
    stubs = {p["key"]: p for p in data if p["key"] != "faster_whisper_large_v3"}
    for p in stubs.values():
        assert p["available"] is False


@pytest.mark.asyncio
async def test_artifacts_empty(client: AsyncClient, db_session):
    await _login(client, db_session)
    r = await client.get("/api/artifacts")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_artifact_not_found(client: AsyncClient, db_session):
    await _login(client, db_session)
    r = await client.get("/api/artifacts/nonexistent")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_config_set_and_get(client: AsyncClient, db_session):
    await _login(client, db_session)
    r = await client.put("/api/config/processor.asr.active", json={"value": "faster_whisper_large_v3"})
    assert r.status_code == 200
    r2 = await client.get("/api/config/processor.asr.active")
    assert r2.json()["value"] == "faster_whisper_large_v3"


@pytest.mark.asyncio
async def test_config_unknown_key(client: AsyncClient, db_session):
    await _login(client, db_session)
    r = await client.put("/api/config/bad.key", json={"value": "x"})
    assert r.status_code == 404
