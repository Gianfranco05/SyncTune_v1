import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SyncStatus(str, enum.Enum):
    pending = "pending"
    analyzing = "analyzing"
    matching = "matching"
    review = "review"
    importing = "importing"
    completed = "completed"
    partial = "partial"
    failed = "failed"
    cancelled = "cancelled"


class Sync(Base):
    __tablename__ = "syncs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(50))
    destination: Mapped[str] = mapped_column(String(50))
    source_name: Mapped[str] = mapped_column(String(500))
    destination_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status_enum"), default=SyncStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="syncs")
    items: Mapped[list["SyncItem"]] = relationship(back_populates="sync", cascade="all, delete-orphan")
