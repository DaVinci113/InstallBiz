from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, func, Text, UniqueConstraint
from datetime import datetime


class Base(DeclarativeBase):
    ...


class StoredFileModel(Base):

    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("file_name", name="files_file_name_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_name: Mapped[str]
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
