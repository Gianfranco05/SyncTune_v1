import pytest
from sqlalchemy.orm import Session

from app.core.database import engine


@pytest.fixture
def anyio_backend():
    # `anyio` (an httpx/starlette dependency, already installed — no new
    # dependency for async tests) only runs asyncio here, never trio.
    return "asyncio"


@pytest.fixture
def db():
    """A session bound to a connection whose outer transaction is always
    rolled back — integration tests can freely INSERT against the real
    Postgres (see docker-compose.yml) without leaving data behind.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
