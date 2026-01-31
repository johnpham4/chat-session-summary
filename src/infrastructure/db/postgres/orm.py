from typing import Any, ClassVar, Type, TypeVar, Generic
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
import json

from src.infrastructure.db.postgres.pool import PostgresPool


T = TypeVar("T", bound="BasePostgresRecord")

class BasePostgresRecord(BaseModel, Generic[T]):
    id: UUID | None = Field(default_factory=uuid4)
    __table__: ClassVar[str]

    @staticmethod
    def _parse_row(row: Any) -> dict[str, Any]:
        data = dict(row)
        for key, value in data.items():
            # Parse JSON strings back to Python objects
            if isinstance(value, str) and value.strip().startswith(('[', '{')):
                try:
                    data[key] = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    pass
        return data

    @classmethod
    def to_record(cls, model: BaseModel) -> dict[str, Any]:
        data = model.model_dump(exclude_none=True)

        for k, v in data.items():
            if isinstance(v, (dict, list)):
                data[k] = json.dumps(v)

        return data


    @classmethod
    def from_record(cls: Type[T], row: Any) -> T:
        parsed = cls._parse_row(row)
        return cls(**parsed)

    @classmethod
    async def save(cls: Type[T], data: dict[str, Any]) -> T:
        pool = PostgresPool.get_pool()
        keys = data.keys()

        values = []
        for v in data.values():
            if isinstance(v, (dict, list)):
                values.append(json.dumps(v))
            else:
                values.append(v)

        columns = ", ".join(keys)
        placeholders = ", ".join(f"${i+1}" for i in range(len(values)))

        query = f"""
        INSERT INTO {cls.__table__} ({columns})
        VALUES ({placeholders})
        RETURNING *
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)

        return cls(**cls._parse_row(row))

    @classmethod
    async def get_by_id(cls: Type[T], id: int) -> T | None:
        pool = PostgresPool.get_pool()

        query = f"SELECT * FROM {cls.__table__} WHERE id=$1"

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, id)

        return cls(**cls._parse_row(row)) if row else None

    @classmethod
    async def get_all(cls: Type[T], limit: int = 100) -> list[T]:
        pool = PostgresPool.get_pool()

        query = f"SELECT * FROM {cls.__table__} LIMIT $1"

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, limit)

        return [cls(**cls._parse_row(row)) for row in rows]

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

        return cls(**cls._parse_row(row)) if row else None

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

        return [cls(**cls._parse_row(row)) for row in rows]