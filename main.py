from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import aiohttp
import api.app_router
from database.db import engine
from database.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        print('App is started')
        await conn.run_sync(Base.metadata.create_all)
        print('All tables is created')
    async with aiohttp.ClientSession() as session:
        app.state.client_session = session
    yield
    print('App is stopped')

app = FastAPI(
    lifespan=lifespan,
    title="InstallBiz Test Task",
)

app.include_router(api.app_router.router)
