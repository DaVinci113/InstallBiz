from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncSession

from database.schemas import StoredFileResponseShema, StoredFileCreateShema
from database.db import SessionDep
from database.services import test_db_write, get_all_files
from services import get_files_names

router = APIRouter()

@router.get("/index", tags=["ТЕСТОВЫЙ"])
def index_page(request: Request):
    return {"status": "ok"}

@router.post("/files/download", summary="Начать загрузку")
def index_page(request: Request):
    ...

@router.get("/files/list",
            response_model=list[StoredFileResponseShema],
            summary="Список всех файлов",
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

@router.get("/files/names")
async def get_filenames_list(request: Request):
    session = request.app.state.client_session
    response = await get_files_names(session=session)
    return response



