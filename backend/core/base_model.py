import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM model 的基底。"""
    pass


class TimestampMixin:
    """共用時間戳欄位。"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class VersionMixin:
    """Optimistic lock 版本欄位。"""
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class AuditMixin:
    """操作人欄位。"""
    updated_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
