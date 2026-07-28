from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from contextlib import asynccontextmanager

from typing import Annotated, AsyncIterator

DB_USER = 'postgres'
DB_NAME = 'postgres'
DB_HOST = 'database'
# DB_HOST = 'localhost'
DB_PORT = '5432'
DB_PASSWORD = '123456'

DATABASE_URL = f'postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

engine = create_async_engine(url=DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

@asynccontextmanager
async def session_scope()-> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

async def get_session():
    async with session_scope() as session:
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
