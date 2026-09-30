"""PostgreSQL Asynchronous Engine and Session Factory.

Manages connection pooling, lifecycle scopes, and declarative model foundations.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import DateTime, text
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from src.common.config.settings import get_settings
from src.common.exceptions.base import DatabaseConnectionError
from src.common.logging.logger import get_logger

logger = get_logger("database.postgres")
settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(AsyncAttrs, DeclarativeBase):
    """Base model class with standardized audit trail timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injector yielding an isolated async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error("Database transaction rolled back due to error", error=str(exc))
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for background workers and manual session control."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_postgres_health() -> bool:
    """Execute a simple query to verify active PostgreSQL connectivity."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1;"))
            scalar = result.scalar()
            return scalar == 1
    except Exception as exc:
        logger.error("PostgreSQL health check failed", error=str(exc))
        raise DatabaseConnectionError(
            f"Failed to connect to PostgreSQL: {exc}",
            details={"host": settings.POSTGRES_HOST, "port": settings.POSTGRES_PORT},
        ) from exc
