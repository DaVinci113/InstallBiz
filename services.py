# Низкоуровневый клиент к API раздачи файлов.
# GET  /api/files/names     — порция имён (3–9); пустой список = каталог скачан.
# POST /api/files/download  — скачать по именам (до 3), ответ — ZIP-архив.
# POST /api/files/downloaded — отметить файлы скачанными.
# Идентификация по IP; можно передать свой X-Candidate-Id.
# Ограничения: 429 (Too Many Requests) и 403 (бан на 30 мин) с заголовком Retry-After.

from urllib.parse import urljoin
from pathlib import Path
import io
import asyncio
import logging
import zipfile
import time

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "http://91.199.149.128:18001"
NAMES_URL = urljoin(BASE_URL, "/api/files/names")
DOWNLOAD_URL = urljoin(BASE_URL, "/api/files/download")
MARKED_URL = urljoin(BASE_URL, "/api/files/downloaded")

CANDIDATE_ID = "installbiz-zcode"  # фиксируем свой id, чтобы прогресс был предсказуем

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Между запросами держим небольшую паузу, чтобы не ловить 429 / бан.
THROTTLE_SECONDS = 0.9


class Blocked(Exception):
    """403 — клиент заблокирован на ~30 минут."""

    def __init__(self, retry_after: float, detail: str = ""):
        self.retry_after = retry_after
        self.detail = detail
        super().__init__(f"Blocked, retry_after={retry_after}: {detail}")


class Throttled(Exception):
    """429 — превышена частота, нужно подождать и повторить."""

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Throttled, retry_after={retry_after}")


async def _throttle():
    if THROTTLE_SECONDS > 0:
        await asyncio.sleep(THROTTLE_SECONDS)


def _parse_retry_after(response: aiohttp.ClientResponse) -> float:
    val = response.headers.get("Retry-After")
    if not val:
        return 5.0
    try:
        return float(val)
    except ValueError:
        # По стандарту может быть HTTP-date, но здесь — целые секунды.
        return 5.0


async def _check_rate_limit(response: aiohttp.ClientResponse):
    """Если ответ 429/403 — поднять соответствующее исключение."""
    if response.status == 429:
        raise Throttled(_parse_retry_after(response))
    if response.status == 403:
        detail = ""
        try:
            detail = (await response.text())[:300]
        except Exception:
            pass
        raise Blocked(_parse_retry_after(response), detail)


async def fetch_names(session: aiohttp.ClientSession) -> list[str]:
    """GET /api/files/names → list[str]."""
    await _throttle()
    async with session.get(
        NAMES_URL,
        headers={"X-Candidate-Id": CANDIDATE_ID},
        timeout=aiohttp.ClientTimeout(total=15),
    ) as response:
        await _check_rate_limit(response)
        if response.status != 200:
            text = await response.text()
            logger.error("fetch_names: %s %s", response.status, text[:300])
            raise RuntimeError(f"fetch_names HTTP {response.status}: {text[:200]}")
        data = await response.json()
        names = data.get("file_names", [])
        logger.info("Получено имён: %d", len(names))
        return list(names)


async def download_files(session: aiohttp.ClientSession, names: list[str]) -> dict[str, str]:
    """POST /api/files/download (≤3 имени) → {file_name: content}.
    Архив временно пишется в data/, распаковывается, текст читается, затем удаляется."""
    if not names:
        return {}
    await _throttle()
    payload = {"file_names": names}
    async with session.post(
        DOWNLOAD_URL,
        json=payload,
        headers={"X-Candidate-Id": CANDIDATE_ID},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as response:
        await _check_rate_limit(response)
        if response.status != 200:
            text = await response.text()
            logger.error("download_files: %s %s", response.status, text[:300])
            raise RuntimeError(f"download_files HTTP {response.status}: {text[:200]}")

        zip_bytes = await response.read()

    # Временно сохраняем архив на диск.
    tmp_path = DATA_DIR / f"_dl_{time.time_ns()}.zip"
    result: dict[str, str] = {}
    try:
        tmp_path.write_bytes(zip_bytes)
        with zipfile.ZipFile(tmp_path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                fname = Path(info.filename).name
                with zf.open(info) as f:
                    content = f.read().decode("utf-8", errors="replace").strip()
                result[fname] = content
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    logger.info("Распаковано файлов: %d", len(result))
    return result


async def mark_downloaded(session: aiohttp.ClientSession, names: list[str]) -> tuple[int, int]:
    """POST /api/files/downloaded → (marked_now, already_marked)."""
    if not names:
        return (0, 0)
    await _throttle()
    payload = {"file_names": names}
    async with session.post(
        MARKED_URL,
        json=payload,
        headers={"X-Candidate-Id": CANDIDATE_ID},
        timeout=aiohttp.ClientTimeout(total=15),
    ) as response:
        await _check_rate_limit(response)
        if response.status != 200:
            text = await response.text()
            logger.error("mark_downloaded: %s %s", response.status, text[:300])
            raise RuntimeError(f"mark_downloaded HTTP {response.status}: {text[:200]}")
        data = await response.json()
        marked_now = int(data.get("marked_now", 0))
        already = int(data.get("already_marked", 0))
        logger.info("Отмечено скачанными: %d (уже было %d)", marked_now, already)
        return marked_now, already
