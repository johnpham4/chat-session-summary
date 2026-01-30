from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from uuid import UUID
from contextlib import asynccontextmanager

from loguru import logger
import sys

from src.infrastructure.db.postgres.pool import PostgresPool
log_level = "DEBUG"
log_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS zz}</green> | <level>{level: <8}</level> | <yellow>Line {line: >4} ({file}):</yellow> <b>{message}</b>"
logger.add(sys.stderr, level=log_level, format=log_format, colorize=True, backtrace=True, diagnose=True)
logger.add("file.log", level=log_level, format=log_format, colorize=False, backtrace=True, diagnose=True)


from src.application.chat.chat import ChatService


@asynccontextmanager
async def lifespan(app: FastAPI):
    await PostgresPool.init()
    yield
    await PostgresPool.close()


app = FastAPI(
    title="Chat API with Session Management",
    lifespan=lifespan,
)
chat_service = ChatService()


class CreateChatRequest(BaseModel):
    name: str


class SendMessageRequest(BaseModel):
    message: str


class SessionResponse(BaseModel):
    session_id: str
    name: str
    chat_id: str
    message_count: int
    created_at: str


class MessageResponse(BaseModel):
    user_message: str
    assistant_response: str
    total_messages: int



@app.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateChatRequest):
    try:
        session = await chat_service.create_chat(request.name)

        return SessionResponse(
            session_id=str(session.id),
            name=session.name,
            chat_id=str(session.id),  # Kept for backward compatibility
            message_count=len(session.messages),
            created_at=session.created_at.isoformat()
        )
    except Exception as e:
        logger.exception(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions")
async def list_sessions(page: int = 1, page_size: int = 20):
    try:
        from src.domain.chat import ChatSession
        sessions = await ChatSession.paginate(page, page_size)

        result = []
        for session in sessions:
            msg_count = await session.count_messages()
            result.append({
                "session_id": str(session.id),
                "name": session.name,
                "message_count": msg_count,
                "created_at": session.created_at.isoformat()
            })

        return {
            "page": page,
            "page_size": page_size,
            "sessions": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: UUID, page: int = 0, page_size: int = 10):
    """Get paginated messages for a session"""
    try:
        from src.domain.chat import ChatSession
        session = await ChatSession.get_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        await session.load_messages(limit=page_size, page=page)

        return {
            "session_id": str(session.id),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content
                }
                for msg in session.messages
            ],
            "has_more": len(session.messages) == page_size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: UUID):
    """Soft delete a chat session"""
    try:
        await chat_service.delete_chat(session_id)
        return {"status": "success", "message": "Session deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(session_id: UUID, request: SendMessageRequest):
    try:
        session, response = await chat_service.send_message(session_id, request.message)

        return MessageResponse(
            user_message=request.message,
            assistant_response=response,
            total_messages=len(session.messages)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(session_id: UUID, request: SendMessageRequest):
    try:
        async def generate():
            async for chunk in chat_service.stream_message(session_id, request.message):
                yield f"data: {chunk}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
