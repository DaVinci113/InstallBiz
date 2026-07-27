import aiohttp
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database.schemas import StoredFileResponseShema, StoredFileCreateShema
from database.db import SessionDep
from database.services import test_db_write, get_all_files
from services import get_files_names, get_files_download, get_pipeline

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


templates = Jinja2Templates(directory="templates")

async def get_http_session(request: Request)->aiohttp.ClientSession:
    return request.app.state.http_session

@router.get("/index", response_class=HTMLResponse)
async def index_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )

@router.get("/files/list",
            response_model=list[StoredFileResponseShema],
            summary="Список всех файлов",
            tags=["MAIN"],
            )
async def all_files_view(session: SessionDep):
    result = await get_all_files(session=session)
    return result

@router.post("/files/test_write",
             response_model=StoredFileResponseShema,
             status_code=201,
             tags=["ТЕСТОВЫЙ"],
             )
async def test_write(name: StoredFileCreateShema, session: SessionDep):
    try:
        result = await test_db_write(name.file_name, session=session)
        return result
    except Exception as ex:
        print(ex)

@router.get("/files/names", tags=["MAIN"])
async def get_filenames_list(request: Request, session: aiohttp.ClientSession=Depends(get_http_session)):
    response = await get_files_names(session=session)
    logger.info(response)
    return response

@router.post("/files/pipeline", tags=["MAIN"])
async def download_pipeline(request: Request, session: aiohttp.ClientSession=Depends(get_http_session)):
    await get_pipeline(session=session)
