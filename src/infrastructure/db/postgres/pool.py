from asyncpg import Pool, create_pool
from src.infrastructure.settings import settings
from loguru import logger

class PostgresPool:
    _pool: Pool | None = None

    @classmethod
    async def init(cls, min_size=5, max_size=20):
        if cls._pool is None:
            cls._pool = await create_pool(
                dsn=settings.DATABASE_URL,
                min_size=min_size,
                max_size=max_size,
            )
            logger.info("Postgres pool initialized")

    @classmethod
    def get_pool(cls) -> Pool:
        if cls._pool is None:
            raise RuntimeError("Postgres pool not initialized")
        return cls._pool

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("Postgres pool closed")
