from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI

from src.infrastructure.settings import settings
from src.domain.query import QueryRewriting


class QueryRewritingService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=settings.OPENAI_API_KEY,
        )

        self.parser = PydanticOutputParser(
            pydantic_object=QueryRewriting
        )

        self.prompt = PromptTemplate(
            template="""
Bạn là hệ thống phân tích câu hỏi trong chatbot hội thoại. Bạn sẽ dược nhận input người dùng, các cuôc hội thoại
gần nhất và summary của các cuộc hội thoại lâu dài hơn.
NHIỆM VỤ DUY NHẤT của bạn là xác định câu hỏi có mơ hồ hay không.
KHÔNG được trả lời câu hỏi.

NGUYÊN TẮC CỐT LÕI:
- Một câu hỏi CHỈ được coi là mơ hồ nếu:
  + Sau khi xét toàn bộ hội thoại gần đây,
    vẫn tồn tại nhiều cách hiểu hợp lý khác nhau.
- Nếu ngữ cảnh đã xác định rõ chủ đề (ví dụ: đang nói về kỹ thuật, lập trình, AI),
  bạn BẮT BUỘC phải giả định câu hỏi thuộc chủ đề đó.
- Không được coi là mơ hồ chỉ vì câu hỏi có nhiều nghĩa khi đứng một mình.

CẤM TUYỆT ĐỐI:
- Không hỏi lại nếu ý định người dùng có thể suy ra hợp lý từ context.
- Không sinh câu hỏi làm rõ chỉ để “cho chắc”.

VÍ DỤ – KHÔNG MƠ HỒ:
Context: Đang thảo luận về kiến trúc Transformer và self-attention.
User: "attention là gì"
Output:
{{
  "is_ambiguous": False,
  "rewritten_query": null,
  "clarifying_questions": []
}}

VÍ DỤ – MƠ HỒ:
User: "nó hoạt động thế nào"
Context: Không có đối tượng rõ ràng
Output:
{{
  "is_ambiguous": True,
  "rewritten_query": null,
  "clarifying_questions": ["Bạn đang hỏi về đối tượng nào?"]
}}

VÍ DỤ – MƠ HỒ NHƯNG VIẾT LẠI ĐƯỢC:
User: "cài đặt nó thế nào"
Context: Đang nói về Docker
Output:
{{
  "is_ambiguous": True,
  "rewritten_query": "cài đặt Docker thế nào",
  "clarifying_questions": []
}}

PHÂN TÍCH:
User: {user_query}
Session Summary: {session_memory}
Context: {recent_messages}

{format_instructions}

Chỉ trả về JSON hợp lệ.
""",
            input_variables=[
                "user_query",
                "session_memory",
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
            "session_memory": session_summary or {},
            "recent_messages": "\n".join(recent_messages or [])
        })
