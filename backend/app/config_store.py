from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Config


async def get_config(db: AsyncSession, key: str) -> str | None:
    result = await db.execute(select(Config).where(Config.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else None


async def set_config(db: AsyncSession, key: str, value: str) -> None:
    result = await db.execute(select(Config).where(Config.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(Config(key=key, value=value))
    await db.commit()
