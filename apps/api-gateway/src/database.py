import asyncio
import logging
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from .config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


SQLITE_URL = "sqlite+aiosqlite:///./local_reviews.db"

# Initial determination
current_db_url = settings.DATABASE_URL
connect_args = {}
if current_db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine: AsyncEngine = create_async_engine(
    current_db_url,
    echo=False,
    future=True,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """
    Initializes database tables. If PostgreSQL is configured but not reachable / credentials fail,
    automatically falls back to zero-docker SQLite and creates all tables.
    """
    global engine, AsyncSessionLocal

    # Import all models so Base.metadata is fully populated
    from .models import Repository, PullRequest, ReviewRun, ReviewComment  # noqa: F401

    if settings.DATABASE_URL.startswith("postgresql"):
        try:
            # Fast check against PostgreSQL with 0.8s timeout
            async with asyncio.timeout(0.8):
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            logger.info("Connected to PostgreSQL and verified schema.")
            return
        except Exception as exc:
            logger.warning(
                f"PostgreSQL unavailable or credentials failed ({type(exc).__name__}). "
                f"Automatically falling back to local SQLite: {SQLITE_URL}"
            )
            try:
                await engine.dispose()
            except Exception:
                pass

            engine = create_async_engine(
                SQLITE_URL,
                echo=False,
                future=True,
                connect_args={"check_same_thread": False},
            )
            AsyncSessionLocal.configure(bind=engine)

    # Initialize tables on SQLite or configured SQLite engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Initialized database tables successfully.")


async def close_db() -> None:
    global engine
    if engine:
        await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
