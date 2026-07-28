from pathlib import Path
from fastapi import FastAPI
from contextlib import asynccontextmanager
import aiohttp
import api.app_router

from fastapi.staticfiles import StaticFiles

from database.db import engine
from database.models import Base


import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        logger.info('App is started')
        await conn.run_sync(Base.metadata.create_all)
        logger.info('All tables is created')
    async with aiohttp.ClientSession() as session:
        app.state.http_session = session
        logger.info("HTTP сессия создана")
        yield
    await app.state.http_session.close()
    logger.info("HTTP сессия закрыта")
    logger.info('App is stopped')


app = FastAPI(
    lifespan=lifespan,
    title="InstallBiz Test Task",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(api.app_router.router)
