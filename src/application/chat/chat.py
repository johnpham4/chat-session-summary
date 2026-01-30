from typing import AsyncIterator
from uuid import UUID
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from src.infrastructure.settings import settings
from src.application.chat.rewriting import QueryRewritingService
from src.application.chat.context_augment import ContextAugmentService
from src.domain.chat import ChatSession, ChatSessionSummary
from src.domain.query import PreprocessResult
from src.application.chat.summarization import ChatSummarizeService


class ChatService:

    system_prompt_str: str | None = "Bạn là một trợ lý AI thông minh, chuện xác và hữu ích. Hãy trả lời bằng tiếng Việt một cách tự nhiên, rõ ràng và chi tiết."

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=settings.OPENAI_API_KEY,
            streaming=True
        )
        self.summarize_service = ChatSummarizeService()
        self.query_rewriting = QueryRewritingService()
        self.context_augment = ContextAugmentService()

    async def create_chat(self, name: str) -> ChatSession:
        session = ChatSession(name=name)
        await session.save(session.model_dump(exclude={'messages'}))

        await session.add_message("system", self.system_prompt_str)

        return session

    async def send_message(self, chat_id: UUID, user_message: str) -> tuple[ChatSession, str]:
        result = await self._preprocess_query(chat_id, user_message)

        if result.early_response:
            return result.chat, result.early_response

        response = await self.llm.ainvoke(result.context_messages)
        assistant_reply = response.content
        await result.chat.add_message("assistant", assistant_reply)

        return result.chat, assistant_reply

    async def stream_message(self, chat_id: UUID, user_message: str) -> AsyncIterator[str]:
        result = await self._preprocess_query(chat_id, user_message)

        if result.early_response:
            yield result.early_response
            return

        full_response = ""
        async for chunk in self.llm.astream(result.context_messages):
            if chunk.content:
                full_response += chunk.content
                yield chunk.content

        await result.chat.add_message("assistant", full_response)

    async def _preprocess_query(self, chat_id: UUID, user_message: str) -> PreprocessResult:
        session = await ChatSession.get_by_id(chat_id)
        if not session:
            raise ValueError(f"Session {chat_id} not found")

        # Save user query
        await session.add_message("user", user_message)

        await session.load_messages(limit=settings.MAX_CONTEXT_MESSAGES)
        logger.debug(f"Loaded {len(session.messages)} messages")


        summary: ChatSessionSummary | None = None
        if self.summarize_service.should_summarize(session):
            logger.warning("Context exceeded threshold → summarizing session")
            summary = await self.summarize_service.summarize_chat(session)
            logger.success(f"Summarization done. Summary ID={summary.id}")
        else:
            logger.debug("No summarization needed")

        if not summary:
            summary = await self.summarize_service.get_latest_summary(session.id)

        recent_msgs_text = [
            f"{msg.role}: {msg.content}"
            for msg in session.messages[-settings.MAX_CONTEXT_MESSAGES:]
        ]

        # First rewrite
        logger.info("Query understanding: rewriting & ambiguity detection")
        query_result = await self.query_rewriting.rewrite(
            user_query=user_message,
            session_summary=summary.model_dump() if summary else None,
            recent_messages=recent_msgs_text
        )

        if query_result.is_ambiguous:
            logger.warning("Query detected as ambiguous")
            logger.info(f"Rewritten query: {query_result.rewritten_query}")
        else:
            logger.info("Query is clear")


        # If still ambiguous
        if query_result.is_ambiguous and query_result.rewritten_query is None:
            clarification_text = (
                "Câu hỏi của bạn chưa đủ rõ. Bạn có thể làm rõ thêm không?\n\n" +
                "\n".join(f"- {q}" for q in query_result.clarifying_questions)
            )

            await session.add_message("assistant", clarification_text)

            return PreprocessResult(
                chat=session,
                early_response=clarification_text
            )

        logger.info("Context augmentation for building LLM prompt context")
        context_messages = self.context_augment.build_messages(
            system_prompt=self.system_prompt_str,
            session=session,
            summary=summary,
            query_result=query_result
        )
        logger.info(f"Context augmentation {context_messages}")

        return PreprocessResult(
            chat=session,
            context_messages=context_messages
        )

    async def get_chat(self, session_id: UUID) -> ChatSession | None:
        session = await ChatSession.get_by_id(session_id)
        if session:
            await session.load_messages()
        return session

    async def delete_chat(self, session_id: UUID) -> None:
        await ChatSession.update(session_id, {"is_deleted": True})


