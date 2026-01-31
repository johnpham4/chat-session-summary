import argparse
import asyncio
from uuid import UUID
from pathlib import Path
from loguru import logger
import json

from src.infrastructure.settings import settings
from src.infrastructure.db.postgres.pool import PostgresPool


async def load_messages_by_session(session_id: UUID):
    await PostgresPool.init()
    pool = PostgresPool.get_pool()

    query = """
        SELECT role, content, created_at
        FROM chat_message
        WHERE session_id = $1
        ORDER BY created_at ASC
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, session_id)

    return rows


async def main(session_id: UUID, output: Path):
    logger.info("Start exporting conversation", session_id=str(session_id))

    rows = await load_messages_by_session(session_id)

    if not rows:
        logger.warning("No messages found for session", session_id=str(session_id))
        return

    messages = [
        { "role": r["role"], "content": r["content"]}
        for r in rows
    ]

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    logger.info(
        "Conversation exported successfully",
        session_id=str(session_id),
        message_count=len(messages),
        output=str(output),
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export conversation by session_id (JSON)"
    )
    parser.add_argument(
        "--session-id", "-s", required=True, help="Chat session UUID"
    )
    parser.add_argument(
        "--output", "-o", default="conversation.json", help="Output JSON file"
    )

    args = parser.parse_args()

    output_path = Path("data") / args.output

    asyncio.run(
        main(
            session_id=UUID(args.session_id),
            output=output_path
        )
    )