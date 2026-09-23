from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Plain sync SQLAlchemy + psycopg2, not async: asyncpg's overlapped I/O has a
# known incompatibility with Docker Desktop's Windows port-forwarding (the
# handshake gets reset — see IMPLEMENTATION_PLAN.md). With a 5-user cap
# (Spotify Development Mode, FASE 0) a blocking query per request is not a
# real bottleneck, so sync SQLAlchemy is the simpler, more portable choice.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
