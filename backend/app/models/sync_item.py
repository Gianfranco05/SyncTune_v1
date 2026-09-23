import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SyncItemStatus(str, enum.Enum):
    matched = "matched"
    review = "review"
    not_found = "not_found"
    selected = "selected"
    skipped = "skipped"
    imported = "imported"
    failed = "failed"
    duplicate = "duplicate"


class SyncItem(Base):
    __tablename__ = "sync_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_id: Mapped[int] = mapped_column(ForeignKey("syncs.id", ondelete="CASCADE"))
    source_id: Mapped[str] = mapped_column(String(255))
    source_title: Mapped[str] = mapped_column(String(500))
    source_artist: Mapped[str | None] = mapped_column(String(500), nullable=True)
    destination_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    destination_artist: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[SyncItemStatus] = mapped_column(
        Enum(SyncItemStatus, name="sync_item_status_enum"), default=SyncItemStatus.review
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sync: Mapped["Sync"] = relationship(back_populates="items")
