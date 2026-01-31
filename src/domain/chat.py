from pydantic import Field, BaseModel
from typing import Literal
from datetime import datetime
from uuid import UUID
from loguru import logger

from src.infrastructure.db.postgres.orm import BasePostgresRecord
from src.infrastructure.db.postgres.pool import PostgresPool

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class ChatMessageRecord(BasePostgresRecord):
    __table__ = "chat_message"

    session_id: UUID
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime = Field(default_factory=datetime.now)
    is_deleted: bool = Field(default=False)

    @classmethod
    async def delete_many(cls, session_id: UUID, ids: list[UUID]) -> None:
        if not ids:
            return

        pool = PostgresPool.get_pool()

        query = f"""
            UPDATE {cls.__table__}
            SET is_deleted = TRUE
            WHERE session_id = $1
            AND id = ANY($2::uuid[])
        """

        async with pool.acquire() as conn:
            await conn.execute(query, session_id, ids)

class ChatSession(BasePostgresRecord):
    __table__ = "chat_session"

    name: str
    created_at: datetime = Field(default_factory=datetime.now)
    messages: list[list[UUID, ChatMessage]] = Field(default_factory=list[list], exclude=True)
    is_deleted: bool = Field(default=False)

    async def load_messages(self, limit: int = 10, page: int = 0) -> None:
        pool = PostgresPool.get_pool()
        offset = page * limit

        query = """
            SELECT id, role, content
            FROM chat_message
            WHERE session_id = $1 and is_deleted = false
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, self.id, limit, offset)


        self.messages = [[row["id"],
                          ChatMessage(role=row['role'], content=row['content'])]
                         for row in reversed(rows)]

    async def count_messages(self) -> int:
        pool = PostgresPool.get_pool()

        query = "SELECT COUNT(*) FROM chat_message WHERE session_id = $1"

        async with pool.acquire() as conn:
            count = await conn.fetchval(query, self.id)

        return count or 0

    async def add_message(self, role: Literal["user", "assistant", "system"], content: str) -> None:
        self.messages.append(ChatMessage(role=role, content=content))

        pool = PostgresPool.get_pool()
        query = """
            INSERT INTO chat_message (session_id, role, content)
            VALUES ($1, $2, $3)
        """

        async with pool.acquire() as conn:
            await conn.execute(query, self.id, role, content)

        logger.info(f"Save {role} message to database...")


    def to_llm_context(self) -> list[dict]:
        return [
            {"role": m.role, "content": m.content}
            for m in self.messages
        ]

class UserProfile(BaseModel):
    preferences: list[str] = Field(default_factory=list, description="User preferences, interests, likes")
    constraints: list[str] = Field(default_factory=list, description="User constraints, limitations, dislikes")

class SummaryContent(BaseModel):
    user_profile: UserProfile
    key_facts: list[str]
    decisions: list[str]
    open_questions: list[str]
    todos: list[str]

class ChatSessionSummary(BasePostgresRecord):
    __table__ = "chat_session_summary"

    session_id: UUID
    user_profile: UserProfile
    key_facts: list[str]
    decisions: list[str]
    open_questions: list[str]
    todos: list[str]
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    async def get_latest_by_session(cls, session_id: UUID) -> "ChatSessionSummary | None":
        pool = PostgresPool.get_pool()

        query = """
            SELECT * FROM chat_session_summary
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, session_id)

        if not row:
            return None

        return cls(**cls._parse_row(row))
