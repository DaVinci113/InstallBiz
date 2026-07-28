# Сервисный слой БД: работа со скачанными файлами.

from typing import Optional

from sqlalchemy import select, func, delete
from database.models import StoredFileModel
from database.db import SessionDep

import logging

logger = logging.getLogger(__name__)


async def upsert_file(file_name: str, content: str, session: SessionDep) -> StoredFileModel:
    """Сохранить файл. Если уже был (по уникальному file_name) — не дублируем,
    обновляем content и downloaded_at. Возвращает актуальную строку."""
    existing = await session.scalar(
        select(StoredFileModel).where(StoredFileModel.file_name == file_name)
    )
    if existing is not None:
        existing.content = content
        # downloaded_at обновится через onupdate/server_default неявно? Нет — выставим явно.
        return existing

    file = StoredFileModel(file_name=file_name, content=content)
    session.add(file)
    await session.commit()
    await session.refresh(file)
    return file


async def list_files_paginated(
    session: SessionDep,
    order: str = "desc",
    page: int = 1,
    size: int = 20,
) -> tuple[list[StoredFileModel], int]:
    """Постраничный список файлов с сортировкой по времени скачивания.
    order: 'desc' (новые сверху) или 'asc'. Возвращает (items, total)."""
    order_col = (
        StoredFileModel.downloaded_at.desc()
        if order != "asc"
        else StoredFileModel.downloaded_at.asc()
    )
    total = await session.scalar(select(func.count(StoredFileModel.id))) or 0

    page = max(page, 1)
    size = max(min(size, 200), 1)
    offset = (page - 1) * size

    stmt = (
        select(StoredFileModel)
        .order_by(order_col, StoredFileModel.id.desc())
        .offset(offset)
        .limit(size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), int(total)


async def get_files_content(
    session: SessionDep,
    ids: Optional[list[int]] = None,
    all_files: bool = False,
) -> list[tuple[str, str]]:
    """Достать (file_name, content) для расчёта статистики.
    Если all_files=True — все файлы; иначе — по списку ids."""
    stmt = select(StoredFileModel.file_name, StoredFileModel.content)
    if not all_files:
        if not ids:
            return []
        stmt = stmt.where(StoredFileModel.id.in_(ids))
    result = await session.execute(stmt.order_by(StoredFileModel.downloaded_at.desc()))
    return [(name, content) for name, content in result.all()]


async def count_files(session: SessionDep) -> int:
    return int(await session.scalar(select(func.count(StoredFileModel.id))) or 0)


async def get_all_ids(session: SessionDep) -> list[int]:
    """Все id файлов (для отметки «выбрать все» в UI)."""
    result = await session.execute(select(StoredFileModel.id).order_by(StoredFileModel.id))
    return [row[0] for row in result.all()]


async def clear_files(session: SessionDep) -> int:
    """Полная очистка таблицы (для отладки/перескачивания)."""
    result = await session.execute(delete(StoredFileModel))
    await session.commit()
    return int(result.rowcount or 0)
