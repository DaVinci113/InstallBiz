from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StoredFileResponseShema(BaseModel):
    """Файл для списков/таблиц."""

    id: int
    file_name: str
    downloaded_at: datetime

    model_config = {"from_attributes": True}


class StoredFileCreateShema(BaseModel):
    file_name: str


# ---- Страница файлов (пагинация) ----

class FilePageResponse(BaseModel):
    items: list[StoredFileResponseShema]
    total: int
    page: int
    size: int
    pages: int


# ---- Расчёт статистики по цифрам ----

class CalcRequest(BaseModel):
    # all=True — посчитать вообще все файлы (ids игнорируется).
    all: bool = False
    ids: list[int] = Field(default_factory=list)


class FileStats(BaseModel):
    file_name: str
    counts: dict[str, int]  # {"0": n, ..., "9": n}


class CalcResponse(BaseModel):
    overall: dict[str, int]  # {"0": n, ..., "9": n}
    per_file: list[FileStats]
    total_files: int


# ---- Статус фоновой задачи скачивания ----

class DownloadStatus(BaseModel):
    state: str  # idle | running | throttled | blocked | done | error
    started_at_ts: Optional[float] = None  # epoch (UTC)
    started_at_nsk: Optional[str] = None   # человекочитаемое время по Новосибирску
    received: int = 0       # сколько имён суммарно получено от API
    downloaded: int = 0     # сколько файлов сохранено в БД
    marked: int = 0         # сколько файлов отмечено скачанными
    cycles: int = 0         # сколько раз ходили за именами
    message: Optional[str] = None
    blocked_until_nsk: Optional[str] = None  # когда истечёт бан (по НСК)
    retry_in: Optional[float] = None         # сек до истечения текущей паузы
    last_error: Optional[str] = None
