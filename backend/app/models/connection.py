import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Provider(str, enum.Enum):
    spotify = "spotify"
    youtube = "youtube"


class Connection(Base):
    """One OAuth connection (tokens included) for a user + provider.

    ``provider_account_id`` is not in the spec's original column list but is
    the actual identity anchor used to find/create a User on login, since
    Spotify no longer returns email in Development Mode — see
    IMPLEMENTATION_PLAN.md FASE 0.
    """

    __tablename__ = "connections"
    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", name="uq_connection_provider_account"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[Provider] = mapped_column(Enum(Provider, name="provider_enum"))
    provider_account_id: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str] = mapped_column(String)
    refresh_token: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="connections")
