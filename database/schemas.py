from datetime import datetime, timezone

from pydantic import BaseModel, Field


class StoredFileResponseShema(BaseModel):

    id: int
    file_name: str
    downloaded_at: datetime

    model_config = {"from_attributes": True}


class StoredFileCreateShema(BaseModel):

    file_name: str