import math

import aiohttp
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import SessionDep
from database.schemas import (
    FilePageResponse,
    StoredFileResponseShema,
    CalcRequest,
    CalcResponse,
    FileStats,
)
from database.services import (
    list_files_paginated,
    get_files_content,
    count_files,
)
from downloader import download_manager

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory="templates")


async def get_http_session(request: Request) -> aiohttp.ClientSession:
    return request.app.state.http_session


# ============ HTML-страницы ============

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def download_page(request: Request):
    """Страница скачивания."""
    return templates.TemplateResponse(request=request, name="index.html")


@router.get("/files", response_class=HTMLResponse, include_in_schema=False)
async def files_page(request: Request):
    """Страница скачанных файлов и расчётов."""
    return templates.TemplateResponse(request=request, name="files.html")


# ============ Скачивание (фоновая задача) ============

@router.get("/download/status", tags=["Скачивание"])
async def download_status():
    """Статус фоновой задачи скачивания для polling UI."""
    return download_manager.status()


@router.post("/download/start", status_code=202, tags=["Скачивание"])
async def download_start(request: Request):
    """Запустить скачивание каталога (фоновая задача). Идемпотентно."""
    session: aiohttp.ClientSession = request.app.state.http_session
    started = download_manager.start(session)
    return {"started": started, **download_manager.status()}


# ============ Список файлов (пагинация) ============

@router.get(
    "/files/list",
    response_model=FilePageResponse,
    summary="Постраничный список файлов",
    tags=["Файлы"],
)
async def files_list(
    session: SessionDep,
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    items, total = await list_files_paginated(session, order=order, page=page, size=size)
    pages = max(1, math.ceil(total / size))
    return FilePageResponse(
        items=[StoredFileResponseShema.model_validate(it) for it in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


# ============ Расчёт статистики по цифрам ============

def _count_digits(text: str) -> dict[str, int]:
    counts = {str(d): 0 for d in range(10)}
    for ch in text:
        if "0" <= ch <= "9":
            counts[ch] += 1
    return counts


@router.post(
    "/files/calc",
    response_model=CalcResponse,
    summary="Посчитать статистику по цифрам для выбранных файлов",
    tags=["Файлы"],
)
async def files_calc(body: CalcRequest, session: SessionDep):
    rows = await get_files_content(session, ids=body.ids, all_files=body.all)
    overall = {str(d): 0 for d in range(10)}
    per_file: list[FileStats] = []
    for file_name, content in rows:
        counts = _count_digits(content)
        for k, v in counts.items():
            overall[k] += v
        per_file.append(FileStats(file_name=file_name, counts=counts))
    # По файлам — от большего объёма к меньшему (для читаемости оставим порядок по имени).
    return CalcResponse(overall=overall, per_file=per_file, total_files=len(per_file))
