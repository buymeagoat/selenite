from fastapi import FastAPI
from app.database import init_db
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
