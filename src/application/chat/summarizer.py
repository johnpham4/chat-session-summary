from uuid import UUID
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
import tiktoken
import json
from loguru import logger

from src.domain.chat import ChatMessageRecord, ChatSession, ChatMessage, ChatSessionSummary, SummaryContent
from src.infrastructure.settings import settings


class ChatSummarizeService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=settings.OPENAI_API_KEY
        )

        self.parser = PydanticOutputParser(
            pydantic_object=SummaryContent
        )

        self.prompt = PromptTemplate(
            template="""
Bạn là hệ thống TÓM TẮT hội thoại cho chatbot.

NHIỆM VỤ:
Phân tích lịch sử hội thoại và tạo ra một bản tóm tắt CÓ CẤU TRÚC.

YÊU CẦU BẮT BUỘC:
- CHỈ được trả về MỘT object JSON hợp lệ
- JSON phải TUÂN THỦ CHÍNH XÁC schema bên dưới
- KHÔNG được trả lời người dùng
- KHÔNG đặt câu hỏi mới
- KHÔNG sinh thêm nội dung ngoài schema

TRÍCH XUẤT CÁC TRƯỜNG SAU:
1. user_profile:
   - preferences: danh sách sở thích / ưu tiên của người dùng
   - constraints: danh sách ràng buộc / giới hạn
2. key_facts:
   - Các thông tin quan trọng đã được nhắc tới
3. decisions:
   - Các quyết định hoặc kết luận đã được đưa ra
4. open_questions:
   - Các vấn đề hoặc câu hỏi CHƯA được giải quyết
5. todos:
   - Các hành động hoặc bước tiếp theo cần làm

SCHEMA OUTPUT (JSON):
{format_instructions}

LỊCH SỬ HỘI THOẠI:
{conversation_text}

CHỈ TRẢ VỀ JSON HỢP LỆ:
""",
            input_variables=["conversation_text"],
            partial_variables={
                "format_instructions": self.parser.get_format_instructions()
            }
        )

        self.encoding = tiktoken.encoding_for_model("gpt-4")

    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def should_summarize(self, session: ChatSession) -> bool:
        total_text = " ".join([msg[1].content for msg in session.messages])
        token_count = self.count_tokens(total_text)
        msg_count = len(session.messages)

        should_trigger = token_count > settings.TOKEN_THRESHOLD

        if should_trigger:
            logger.warning(
                f"Threshold exceeded! "
                f"Messages: {msg_count}, Tokens: {token_count}/{settings.TOKEN_THRESHOLD}"
            )

        return should_trigger, token_count

    async def summarize_chat(self, session: ChatSession) -> ChatSessionSummary | None:
        logger.info(f"Starting summarization for session {session.id}...")

        messages = session.messages

        start_idx = 1 if messages and messages[0][1].role == "system" else 0

        if len(messages) - start_idx <= settings.KEEP_RECENT:
            logger.debug(f"Too few messages to summarize. Skipping.")
            return None

        to_summarize = messages[start_idx:-settings.KEEP_RECENT]
        logger.debug(f"Summarizing {len(to_summarize)} messages (keeping {settings.KEEP_RECENT} recent)")

        summary = await self._create_summary(to_summarize, session.id)

        await summary.save(summary.model_dump())

        await self.delete_old_messages(session.id, to_summarize)

        logger.success(
            f"Complete! Summary ID: {summary.id}. "
            f"Extracted: {len(summary.key_facts or [])} facts, "
            f"{len(summary.decisions or [])} decisions, "
            f"{len(summary.open_questions or [])} questions. "
            f"Deleted {len(to_summarize)} old messages."
        )

        return summary

    async def _create_summary(self, messages: list[list[UUID, ChatMessage]], session_id: UUID) -> ChatSessionSummary:
        conversation_text = "\n".join([
            f"{msg[1].role}: {msg[1].content}"
            for msg in messages
        ])

        chain = self.prompt | self.llm | self.parser
        llm_output: SummaryContent = await chain.ainvoke({"conversation_text": conversation_text})

        summary = ChatSessionSummary(
            session_id=session_id,
            user_profile=llm_output.user_profile,
            key_facts=llm_output.key_facts,
            decisions=llm_output.decisions,
            open_questions=llm_output.open_questions,
            todos=llm_output.todos
        )

        return summary

    async def delete_old_messages(self, session_id: UUID, messages: list[list[UUID, ChatMessage]]) -> None:
        ids = [msg_id for msg_id, _ in messages]

        await ChatMessageRecord.delete_many(session_id, ids)

        logger.info(f"deleted {len(ids)} summarized messages")