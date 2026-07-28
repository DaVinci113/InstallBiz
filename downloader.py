# Фоновая задача скачивания всего каталога + состояние для polling UI.

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import aiohttp

import services
from database.db import session_scope
from database.services import upsert_file

logger = logging.getLogger(__name__)

NSK = ZoneInfo("Asia/Novosibirsk")  # UTC+7

# Сколько раз подряд пытаться пережить transient-ошибки.
MAX_RETRIES = 5
# Пауза между циклами «имена → батчи → mark», чтобы не дёргать API лишний раз.
CYCLE_PAUSE = 1.0


class DownloadManager:
    """Синглтон-состояние фоновой задачи скачивания."""

    def __init__(self) -> None:
        self.state: str = "idle"  # idle | running | throttled | blocked | done | error
        self.started_at_ts: Optional[float] = None
        self.started_at_nsk: Optional[str] = None
        self.received: int = 0      # сколько имён суммарно получено
        self.downloaded: int = 0    # сколько файлов сохранено в БД
        self.marked: int = 0        # сколько файлов отмечено скачанными
        self.cycles: int = 0        # сколько раз ходили за именами
        self.message: Optional[str] = None
        self.blocked_until_ts: Optional[float] = None
        self.blocked_until_nsk: Optional[str] = None
        self.retry_in: Optional[float] = None
        self.last_error: Optional[str] = None
        self._task: Optional[asyncio.Task] = None

    # ---- публичный API ----

    def start(self, session: aiohttp.ClientSession) -> bool:
        """Запустить скачивание, если оно не идёт. Возвращает True, если запустили."""
        if self._task is not None and not self._task.done():
            return False
        self._reset_state()
        self._task = asyncio.create_task(self._run(session))
        return True

    def status(self) -> dict:
        retry_in = None
        if self.state in ("throttled", "blocked") and self.blocked_until_ts:
            retry_in = max(0.0, self.blocked_until_ts - time.time())
        return {
            "state": self.state,
            "started_at_ts": self.started_at_ts,
            "started_at_nsk": self.started_at_nsk,
            "received": self.received,
            "downloaded": self.downloaded,
            "marked": self.marked,
            "cycles": self.cycles,
            "message": self.message,
            "blocked_until_nsk": self.blocked_until_nsk,
            "retry_in": round(retry_in, 1) if retry_in is not None else None,
            "last_error": self.last_error,
        }

    # ---- внутреннее ----

    def _reset_state(self) -> None:
        now = time.time()
        self.state = "running"
        self.started_at_ts = now
        self.started_at_nsk = datetime.fromtimestamp(now, NSK).strftime("%d.%m.%Y %H:%M:%S (НСК)")
        self.received = 0
        self.downloaded = 0
        self.marked = 0
        self.cycles = 0
        self.message = "Запуск скачивания…"
        self.blocked_until_ts = None
        self.blocked_until_nsk = None
        self.retry_in = None
        self.last_error = None

    async def _run(self, session: aiohttp.ClientSession) -> None:
        try:
            await self._loop(session)
            if self.state != "error":
                self.state = "done"
                self.message = "Каталог скачан полностью."
        except asyncio.CancelledError:
            self.state = "idle"
            self.message = "Скачивание отменено."
            raise
        except services.Blocked as ex:
            self._set_blocked(ex.retry_after, ex.detail)
        except Exception as ex:  # noqa: BLE001
            logger.exception("Скачивание упало")
            self.state = "error"
            self.last_error = f"{type(ex).__name__}: {ex}"
            self.message = "Ошибка скачивания."

    async def _loop(self, session: aiohttp.ClientSession) -> None:
        while True:
            # 1) получить имена
            self.message = "Запрашиваю имена файлов…"
            names = await self._fetch_with_retry(session)
            if not names:
                # Пустой список = каталог скачан полностью.
                self.message = "Получен пустой список — каталог скачан полностью."
                logger.info("Каталог скачан полностью.")
                return

            self.received += len(names)
            self.cycles += 1
            self.message = f"Получено {len(names)} имён, скачиваю…"

            # 2) скачиваем батчами по 3, сохраняем в БД
            for i in range(0, len(names), 3):
                batch = names[i : i + 3]
                contents = await self._download_with_retry(session, batch)
                # Сохраняем в БД
                async with session_scope() as db:
                    for fname in batch:
                        content = contents.get(fname, "")
                        await upsert_file(fname, content, db)
                    await db.commit()
                self.downloaded += len(batch)
                self.message = (
                    f"Получено имён: {self.received}. "
                    f"Скачано {self.downloaded} из {self.received}…"
                )

            # 3) отметить скачанными
            marked_now, _ = await self._mark_with_retry(session, names)
            self.marked += marked_now or len(names)
            self.message = (
                f"Получено имён: {self.received}. "
                f"Скачано {self.downloaded} из {self.received}. "
                f"Отмечено: {self.marked}."
            )

            if CYCLE_PAUSE:
                await asyncio.sleep(CYCLE_PAUSE)

    # ---- обработчики с retry для 429 (Throttled) ----

    async def _fetch_with_retry(self, session: aiohttp.ClientSession) -> list[str]:
        attempt = 0
        while True:
            try:
                return await services.fetch_names(session)
            except services.Throttled as ex:
                attempt += 1
                if attempt > MAX_RETRIES:
                    raise
                self._set_throttled(ex.retry_after)
                await asyncio.sleep(ex.retry_after)
                self.state = "running"

    async def _download_with_retry(
        self, session: aiohttp.ClientSession, batch: list[str]
    ) -> dict[str, str]:
        attempt = 0
        while True:
            try:
                return await services.download_files(session, batch)
            except services.Throttled as ex:
                attempt += 1
                if attempt > MAX_RETRIES:
                    raise
                self._set_throttled(ex.retry_after)
                await asyncio.sleep(ex.retry_after)
                self.state = "running"

    async def _mark_with_retry(
        self, session: aiohttp.ClientSession, names: list[str]
    ) -> tuple[int, int]:
        attempt = 0
        while True:
            try:
                return await services.mark_downloaded(session, names)
            except services.Throttled as ex:
                attempt += 1
                if attempt > MAX_RETRIES:
                    raise
                self._set_throttled(ex.retry_after)
                await asyncio.sleep(ex.retry_after)
                self.state = "running"

    # ---- настройки состояния паузы/бана ----

    def _set_throttled(self, retry_after: float) -> None:
        self.state = "throttled"
        self.blocked_until_ts = time.time() + retry_after
        self.blocked_until_nsk = None
        self.retry_in = retry_after
        self.message = f"Превышена частота запросов (429). Пауза {retry_after:.0f} с."

    def _set_blocked(self, retry_after: float, detail: str) -> None:
        self.state = "blocked"
        until = time.time() + retry_after
        self.blocked_until_ts = until
        self.blocked_until_nsk = datetime.fromtimestamp(until, NSK).strftime("%d.%m.%Y %H:%M:%S (НСК)")
        self.retry_in = retry_after
        self.last_error = detail or "Заблокирован за злоупотребление запросами (403)."
        self.message = f"Заблокирован на {retry_after:.0f} с. До разблокировки (НСК): {self.blocked_until_nsk}."


# Глобальный экземпляр.
download_manager = DownloadManager()
