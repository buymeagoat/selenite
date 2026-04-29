import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import init_db
from app.processors.stubs import register_all_stubs
from app.routers import auth as auth_router
from app.routers import processors as processors_router
from app.routers import config as config_router
from app.routers import artifacts as artifacts_router
from app.routers import jobs as jobs_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    register_all_stubs()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(auth_router.router)
app.include_router(processors_router.router)
app.include_router(config_router.router)
app.include_router(artifacts_router.router)
app.include_router(jobs_router.router)

FRONTEND_DIST = os.getenv("FRONTEND_DIST", "../frontend/dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=f"{FRONTEND_DIST}/assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        return FileResponse(f"{FRONTEND_DIST}/index.html")
