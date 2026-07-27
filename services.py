from fastapi import Request
from urllib.parse import urljoin
import aiohttp
import asyncio


# GET /api/files/names — получить случайную порцию имён файлов (от 3 до 9), ещё не отмеченных вами как скачанные.
# POST /api/files/download — скачать файлы по именам (до 3 за запрос), ответ приходит ZIP-архивом.
# POST /api/files/downloaded — отметить файлы скачанными, чтобы они больше не попадали в выдачу имён.


base_url = 'http://91.199.149.128:18001'
receive_file_names_url = urljoin(base_url,'/api/files/names')
download_files_by_names_url = urljoin(base_url,'/api/files/download')
mark_files_downloaded_url = urljoin(base_url,'/api/files/downloaded')


async def get_files_names(session: aiohttp.ClientSession)->str:
    async with session.get(receive_file_names_url) as response:
        response.raise_for_status()
        return await response.text()



async def get_mark_files():
    ...

async def get_files_download():
    ...

async def get_pipeline():
    ...

if __name__ == '__main__':
    asyncio.run(get_files_names())