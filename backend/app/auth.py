import os
from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import Depends, HTTPException, Cookie, status
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt
from jose import JWTError, jwt
from app.database import get_db
from app.config_store import get_config

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
COOKIE_NAME = "selenite_session"
TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token() -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": "user", "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub") == "user"
    except JWTError:
        return False


async def require_auth(
    selenite_session: Annotated[str | None, Cookie()] = None,
    db: AsyncSession = Depends(get_db),
) -> None:
    if not selenite_session or not decode_token(selenite_session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    password_hash = await get_config(db, "auth.password_hash")
    if not password_hash:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth not configured")
