from uuid import UUID
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
import tiktoken
from loguru import logger

from src.domain.chat import ChatSession, ChatMessage, ChatSessionSummary
from src.infrastructure.settings import settings


class ChatSummarizeService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=settings.OPENAI_API_KEY
        )

        self.parser = PydanticOutputParser(
            pydantic_object=ChatSessionSummary
        )

        self.prompt = PromptTemplate(
            template = """
Bạn là một chuyên gia tóm tắt cuộc hội thoại.
Hãy tóm tắt lịch sử cuộc trò chuyện sau đây một cách ngắn gọn và có cấu trúc.

**Tập trung vào:**
1. **user_profile**: Thông tin về người dùng - sở thích, yêu cầu, ràng buộc, bối cảnh cá nhân
2. **key_facts**: Các sự thật quan trọng đã được đề cập trong cuộc trò chuyện
3. **decisions**: Các quyết định hoặc kết luận đã được đưa ra
4. **open_questions**: Các câu hỏi chưa được giải quyết, vấn đề còn mở
5. **todos**: Các công việc cần làm, hành động tiếp theo

Câu trúc output:
{format_instructions}

Lịch sử cuộc trò chuyện:
{conversation}

Hãy trả lời chỉ với JSON hợp lệ, không có text phụ nào khác:
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
        total_text = " ".join([msg.content for msg in session.messages])
        token_count = self.count_tokens(total_text)
        msg_count = len(session.messages)

        should_trigger = token_count > settings.TOKEN_THRESHOLD

        if should_trigger:
            logger.warning(
                f"Threshold exceeded! "
                f"Messages: {msg_count}, Tokens: {token_count}/{settings.TOKEN_THRESHOLD}"
            )

        return should_trigger

    async def summarize_chat(self, session: ChatSession) -> ChatSessionSummary | None:
        logger.info(f"Starting summarization for session {session.id}...")

        messages = session.messages

        start_idx = 1 if messages and messages[0].role == "system" else 0

        if len(messages) - start_idx <= self.KEEP_RECENT:
            logger.debug(f"Too few messages to summarize. Skipping.")
            return None

        to_summarize = messages[start_idx:-self.KEEP_RECENT]
        logger.debug(f"Summarizing {len(to_summarize)} messages (keeping {self.KEEP_RECENT} recent)")

        summary = await self._create_summary(to_summarize, session.id)

        await summary.save(summary.model_dump())
        logger.success(
            f"Complete! Summary ID: {summary.id}. "
            f"Extracted: {len(summary.key_facts or [])} facts, "
            f"{len(summary.decisions or [])} decisions, "
            f"{len(summary.open_questions or [])} questions"
        )

        return summary

    async def get_latest_summary(self, session_id: UUID) -> ChatSessionSummary | None:
        summaries = await ChatSessionSummary.get_all(limit=1000)
        session_summaries = [
            s for s in summaries
            if s.session_id == session_id
        ]

        if not session_summaries:
            return None

        # Return most recent
        return max(session_summaries, key=lambda s: s.updated_at)

    async def _create_summary(self, messages: list[ChatMessage], session_id: UUID) -> ChatSessionSummary:
        conversation_text = "\n".join([
            f"{msg.role}: {msg.content}"
            for msg in messages
        ])

        chain = self.prompt | self.llm | self.parser
        response: ChatSessionSummary = await chain.ainvoke({"conversation_text": conversation_text})

        response.session_id = session_id

        return response
