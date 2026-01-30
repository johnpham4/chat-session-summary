from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI

from src.infrastructure.settings import settings
from src.domain.query import QueryRewriting


class QueryRewritingService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=settings.OPENAI_API_KEY,
        )

        self.parser = PydanticOutputParser(
            pydantic_object=QueryRewriting
        )

        self.prompt = PromptTemplate(
            template="""
Bạn là hệ thống PHÂN TÍCH câu hỏi trong chatbot hội thoại.

Bạn sẽ nhận:
- Câu hỏi hiện tại của người dùng
- Các tin nhắn hội thoại gần đây (short-term memory)
- Bản tóm tắt hội thoại cũ hơn (session summary)

NHIỆM VỤ DUY NHẤT:
- Xác định câu hỏi có mơ hồ hay KHÔNG.
- Nếu có thể làm rõ bằng cách VIẾT LẠI dựa trên context → viết lại.
- KHÔNG được trả lời câu hỏi.

ĐỊNH NGHĨA "MƠ HỒ":
- Một câu hỏi CHỈ được coi là mơ hồ nếu:
  + Sau khi xét toàn bộ context,
    vẫn tồn tại nhiều cách hiểu hợp lý khác nhau.
- Nếu context đã xác định rõ chủ đề,
  BẮT BUỘC giả định câu hỏi thuộc chủ đề đó.

QUY TẮC:
- Không hỏi lại nếu có thể suy ra hợp lý từ context.
- Không coi câu hỏi là mơ hồ chỉ vì nó ngắn.
- Chỉ sinh câu hỏi làm rõ khi KHÔNG thể viết lại.

VÍ DỤ – KHÔNG MƠ HỒ:
Context: Đang nói về Transformer.
User: "attention là gì"
Output:
{{
  "original_query": "attention là gì",
  "is_ambiguous": false,
  "rewritten_query": null,
  "clarifying_questions": []
}}

VÍ DỤ – MƠ HỒ:
User: "nó hoạt động thế nào"
Context: Không rõ đối tượng
Output:
{{
  "original_query": "nó hoạt động thế nào",
  "is_ambiguous": true,
  "rewritten_query": null,
  "clarifying_questions": ["Bạn đang hỏi về đối tượng nào?"]
}}

VÍ DỤ – MƠ HỒ NHƯNG VIẾT LẠI ĐƯỢC:
User: "cài đặt nó thế nào"
Context: Đang nói về Docker
Output:
{{
  "original_query": "cài đặt nó thế nào",
  "is_ambiguous": true,
  "rewritten_query": "cài đặt Docker thế nào",
  "clarifying_questions": []
}}

PHÂN TÍCH:
User: {user_query}
Session Summary: {session_summary}
Recent Messages: {recent_messages}

{format_instructions}

Chỉ trả về JSON hợp lệ.
""",
    input_variables=[
        "user_query",
        "session_summary",
        "recent_messages"
    ],
    partial_variables={
        "format_instructions": self.parser.get_format_instructions()
    }
)

    async def rewrite(
        self,
        user_query: str,
        session_summary: dict | None = None,
        recent_messages: list[str] | None = None
    ) -> QueryRewriting:
        chain = self.prompt | self.llm | self.parser
        return await chain.ainvoke({
            "user_query": user_query,
            "session_summary": session_summary or {},
            "recent_messages": "\n".join(recent_messages or [])
        })
