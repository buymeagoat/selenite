import pytest
from httpx import AsyncClient
from app.auth import hash_password, verify_password, create_token, decode_token
from app.config_store import set_config


def test_hash_and_verify():
    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed)
    assert not verify_password("wrong", hashed)


def test_token_roundtrip():
    token = create_token()
    assert decode_token(token)


def test_invalid_token():
    assert not decode_token("garbage")


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db_session):
    await set_config(db_session, "auth.password_hash", hash_password("testpass"))
    response = await client.post("/api/auth/login", json={"password": "testpass"})
    assert response.status_code == 200
    assert "selenite_session" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db_session):
    await set_config(db_session, "auth.password_hash", hash_password("testpass"))
    response = await client.post("/api/auth/login", json={"password": "wrong"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_not_configured(client: AsyncClient):
    response = await client.post("/api/auth/login", json={"password": "anything"})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_cookie(client: AsyncClient, db_session):
    await set_config(db_session, "auth.password_hash", hash_password("testpass"))
    login = await client.post("/api/auth/login", json={"password": "testpass"})
    assert login.status_code == 200
    response = await client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json() == {"authenticated": True}
