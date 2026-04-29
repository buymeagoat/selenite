from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config_store import get_config
from app.auth import verify_password, create_token, require_auth, COOKIE_NAME

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    password_hash = await get_config(db, "auth.password_hash")
    if not password_hash:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth not configured")
    if not verify_password(body.password, password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    token = create_token()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=86400,
    )
    return {"authenticated": True}


@router.post("/logout")
async def logout(response: Response, _=Depends(require_auth)):
    response.delete_cookie(key=COOKIE_NAME)
    return {"authenticated": False}


@router.get("/me")
async def me(_=Depends(require_auth)):
    return {"authenticated": True}
