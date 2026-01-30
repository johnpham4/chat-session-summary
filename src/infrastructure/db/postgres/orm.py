from typing import Any, ClassVar, Type, TypeVar, Generic
from pydantic import BaseModel, Field
from uuid import UUID, uuid4

from src.infrastructure.db.postgres.pool import PostgresPool


T = TypeVar("T", bound="BasePostgresRecord")

class BasePostgresRecord(BaseModel, Generic[T]):
    id: UUID | None = Field(default_factory=uuid4)
    __table__: ClassVar[str]

    @classmethod
    async def save(cls: Type[T], data: dict[str, Any]) -> T:
        pool = PostgresPool.get_pool()
        keys = data.keys()
        values = list(data.values())

        columns = ", ".join(keys)
        placeholders = ", ".join(f"${i+1}" for i in range(len(values)))

        query = f"""
        INSERT INTO {cls.__table__} ({columns})
        VALUES ({placeholders})
        RETURNING *
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)

        return cls(**row)

    @classmethod
    async def get_by_id(cls: Type[T], id: int) -> T | None:
        pool = PostgresPool.get_pool()

        query = f"SELECT * FROM {cls.__table__} WHERE id=$1"

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, id)

        return cls(**row) if row else None

    @classmethod
    async def get_all(cls: Type[T], limit: int = 100) -> list[T]:
        pool = PostgresPool.get_pool()

        query = f"SELECT * FROM {cls.__table__} LIMIT $1"

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, limit)

        return [cls(**row) for row in rows]

    @classmethod
    async def update(cls: Type[T], id: int, data: dict[str, Any]) -> T | None:
        pool = PostgresPool.get_pool()

        sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(data.keys()))
        values = list(data.values())

        query = f"""
        UPDATE {cls.__table__}
        SET {sets}
        WHERE id=$1
        RETURNING *
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, id, *values)

        return cls(**row) if row else None

    @classmethod
    async def delete(cls, id: int) -> None:
        pool = PostgresPool.get_pool()

        query = f"DELETE FROM {cls.__table__} WHERE id=$1"

        async with pool.acquire() as conn:
            await conn.execute(query, id)


    @classmethod
    async def paginate(cls: Type[T], page: int = 1, page_size: int = 20) -> list[T]:
        pool = PostgresPool.get_pool()
        offset = (page - 1) * page_size

        query = f"""
        SELECT *
        FROM {cls.__table__}
        WHERE is_deleted = false
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, page_size, offset)

        return [cls(**row) for row in rows]