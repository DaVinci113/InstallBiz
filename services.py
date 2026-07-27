from urllib.parse import urljoin
import aiohttp

import logging

from pydantic import with_config

logger = logging.getLogger(__name__)


# GET /api/files/names — получить случайную порцию имён файлов (от 3 до 9), ещё не отмеченных вами как скачанные.
# POST /api/files/download — скачать файлы по именам (до 3 за запрос), ответ приходит ZIP-архивом.
# POST /api/files/downloaded — отметить файлы скачанными, чтобы они больше не попадали в выдачу имён.


base_url = 'http://91.199.149.128:18001'
receive_file_names_url = urljoin(base_url,'/api/files/names')
download_files_by_names_url = urljoin(base_url,'/api/files/download')
mark_files_downloaded_url = urljoin(base_url,'/api/files/downloaded')

async def get_batch(lst, chunk_size):
    ...


async def get_files_names(session: aiohttp.ClientSession):
    try:
        async with session.get(receive_file_names_url, timeout=1) as response:
            logger.info('Получение имен')
            result = await response.json()
            return result
    except Exception:
        logger.error(response.raise_for_status())



async def get_mark_files(file_list, session: aiohttp.ClientSession)->None:
    ...

async def get_files_download(file_name, session: aiohttp.ClientSession):
    payload = {
        "file_names": [file_name]
    }
    logger.info(f'file_name:{file_name}')
    async with session.post(download_files_by_names_url, json=payload, timeout=1) as response:
        logger.info('Скачивание файлов')
        if response.status != 200:
            logger.error(await response.text())
            return

        filename = f'{file_name[:-4]}.zip'
        logger.info(f'Имя файла: {filename}')
        logger.info('Чтение файла')
        file_bytes = await response.read()

        with open(f'./data/{filename}', 'wb') as f:
            f.write(file_bytes)
            logger.info(f'файл {filename} записан')


async def get_pipeline(session: aiohttp.ClientSession):
    file_list_is_full = True
    while file_list_is_full:
        try:
            response = await get_files_names(session=session)
            file_name_list = response['file_names']
            logger.info(f'Список файлов: {file_name_list}')
            if file_name_list:
                try:
                    for file_name in file_name_list:
                        await get_files_download(
                            file_name=file_name,
                            session=session
                        )
                        break
                except Exception as ex:
                    logger.error(ex)
                    logger.error('error download')
        except Exception:
            logger.error('error get files names')

        finally:
            file_list_is_full = False
