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
        logger.info(f"[PIPELINE START] Session: {chat_id}, Query: '{user_message}...'")

        session = await ChatSession.get_by_id(chat_id)
        if not session:
            raise ValueError(f"Session {chat_id} not found")

        # Load messages from database
        await session.load_messages()
        logger.debug(f"Loaded {len(session.messages)} messages from session")

        # Get session summary for context
        summary = await self.summarize_service.get_latest_summary(session.id)

        # Window size context messages
        recent_msgs = [f"{msg.role}: {msg.content}" for msg in session.messages[-settings.MAX_CONTEXT_MESSAGES:]]
        logger.info("Query Understanding: Checking for ambiguity...")
        logger.info(f"Recent messages: {recent_msgs}")
        query_result = await self.query_rewriting.rewrite(
            user_query=user_message,
            session_summary=summary.model_dump() if summary else None,
            recent_messages=recent_msgs
        )

        if query_result.is_ambiguous:
            logger.warning(f"Query is AMBIGUOUS. Rewritten: {query_result.rewritten_query}")
        else:
            logger.info("Query is clear, no rewriting needed")

        # Save user message
        await session.add_message("user", user_message)


        if query_result.is_ambiguous and query_result.rewritten_query is None:
            logger.info("Generating clarifying questions...")
            clarification_text = (
                "Câu hỏi của bạn chưa rõ ràng. Bạn có thể làm rõ :\n\n" +
                "\n".join(f"- {q}" for q in query_result.clarifying_questions)
            )
            logger.info(f"Clarifying questions: {query_result.clarifying_questions}")

            await session.add_message("assistant", clarification_text)

            return PreprocessResult(
                chat=session,
                early_response=clarification_text
            )

        final_user_query = (
            query_result.rewritten_query
            if query_result.rewritten_query
            else user_message
        )
        logger.debug(f"Final query for LLM: '{final_user_query[:100]}...'")

        total_text = " ".join([msg.content for msg in session.messages])
        token_count = self.summarize_service.count_tokens(total_text)
        msg_count = len(session.messages)
        logger.info(f"Messages: {msg_count}, Tokens: {token_count}")

        # Trigger summarization if needed
        if self.summarize_service.should_summarize(session):
            logger.warning(f"Context exceeded threshold! Triggering summarization...")
            summary = await self.summarize_service.summarize_chat(session)
            logger.success(f"Summarization complete. Summary ID: {summary.id}")
            logger.debug(f"Summary: user_profile={len(summary.user_profile or {})} items, "
                        f"key_facts={len(summary.key_facts or [])}, "
                        f"decisions={len(summary.decisions or [])}, "
                        f"open_questions={len(summary.open_questions or [])}")
        else:
            logger.debug(f"No summarization needed (threshold not reached)")

        if not summary or self.summarize_service.should_summarize(session):
            summary = await self.summarize_service.get_latest_summary(session.id)

        logger.info("Context Augmentation: Building augmented context...")
        if summary:
            logger.info(f"Using session summary (ID: {summary.id})")

        augmented_context = self.context_augment.augment_context(
            original_query=user_message,
            rewritten_query=query_result.rewritten_query,
            recent_messages=session.messages[-10:],  # Last 10 messages
            summary=summary
        )
        logger.debug(f"Augmented context length: {len(augmented_context)} chars")

        context_messages = self._prepare_context(session, summary)

        logger.success(f"Preprocessing complete. Ready for LLM call.")

        return PreprocessResult(
            chat=session,
            context_messages=context_messages
        )

    def _prepare_context(self, session: ChatSession, summary: ChatSessionSummary | None = None) -> list:
        messages = []

        messages.append(SystemMessage(content=self.system_prompt_str))

        # Inject summary session
        if summary:
            messages.append(
                SystemMessage(
                    content=f"[Session Memory]\n{summary.model_dump_json()}"
                )
            )

        recent_messages = session.messages[-settings.MAX_CONTEXT_MESSAGES:]
        for msg in recent_messages:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))

        return messages

    async def get_chat(self, session_id: UUID) -> ChatSession | None:
        session = await ChatSession.get_by_id(session_id)
        if session:
            await session.load_messages()
        return session

    async def delete_chat(self, session_id: UUID) -> None:
        await ChatSession.update(session_id, {"is_deleted": True})


