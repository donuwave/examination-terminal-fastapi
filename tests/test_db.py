from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from core.models import Base

test_engine = create_async_engine(settings.db.url, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_test_db() -> AsyncSession:
    async with TestSessionLocal() as session:
        yield session


async def recreate_schema():
    """Чистая схема на каждый тест: попытки и время зависят от состояния, общего быть не должно."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
