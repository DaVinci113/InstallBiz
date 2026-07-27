# GET /api/files/names — получить случайную порцию имён файлов (от 3 до 9), ещё не отмеченных вами как скачанные.
# POST /api/files/download — скачать файлы по именам (до 3 за запрос), ответ приходит ZIP-архивом.
# POST /api/files/downloaded — отметить файлы скачанными, чтобы они больше не попадали в выдачу имён.

from sqlalchemy import select
from database.models import StoredFileModel
from database.schemas import StoredFileCreateShema, StoredFileResponseShema
from database.db import SessionDep

import logging

logger = logging.getLogger(__name__)


def start_download():
    ...


async def test_db_write(name: str, session: SessionDep):
     file = StoredFileModel(
         file_name = name,
     )
     session.add(file)
     await session.commit()
     await session.refresh(file)  # Обновляем объект, чтобы Pydantic увидел все поля
     return file

async def get_all_files(session: SessionDep):
    result = await session.execute(select(StoredFileModel))
    return result.scalars().all()


if __name__ == '__main__':
    print('asdf')