"""
Ma'lumotlar bazasi ulanishi: async SQLAlchemy engine va session factory.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Async engine yaratish
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,          # SQL so'rovlarini logga chiqarish (debug uchun True qiling)
)


# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Barcha modellar uchun asosiy klass."""
    pass


async def get_db() -> AsyncSession:
    """
    FastAPI dependency injection uchun DB session generatori.
    Har bir so'rov uchun yangi session ochiladi va avtomatik yopiladi.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """Barcha jadvallarni bazada yaratish (development uchun)."""
    async with engine.begin() as conn:
        from app.db import models  # noqa: F401 — modellarni import qilish shart
        await conn.run_sync(Base.metadata.create_all)
