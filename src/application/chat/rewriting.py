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

INPUT BAO GỒM:
- Câu hỏi hiện tại của người dùng
- Các tin nhắn hội thoại gần đây (short-term memory)
- Bản tóm tắt hội thoại cũ hơn (session summary)

NHIỆM VỤ DUY NHẤT:
1. Xác định câu hỏi có mơ hồ hay KHÔNG.
2. Nếu câu hỏi mơ hồ nhưng có thể làm rõ bằng cách VIẾT LẠI dựa trên context → viết lại.
3. Chỉ sinh câu hỏi làm rõ khi KHÔNG thể viết lại.
4. TUYỆT ĐỐI KHÔNG trả lời câu hỏi của người dùng.

ĐỊNH NGHĨA CÂU HỎI MƠ HỒ:
- Một câu hỏi CHỈ được coi là mơ hồ nếu:
  + Sau khi xét toàn bộ short-term memory và session summary,
    vẫn tồn tại nhiều cách hiểu hợp lý khác nhau.
- Nếu context đã xác định rõ chủ đề (ví dụ: kỹ thuật, AI, lập trình),
  BẮT BUỘC giả định câu hỏi thuộc chủ đề đó.

QUY TẮC BẮT BUỘC:
- Không coi câu hỏi là mơ hồ chỉ vì nó ngắn.
- Không hỏi lại nếu ý định người dùng có thể suy ra hợp lý từ context.
- Khi rewritten_query ≠ null:
  + clarifying_questions PHẢI là [].
- Khi sinh clarifying_questions:
  + Chỉ sinh khi không thể viết lại.
  + Sinh từ 2 đến 3 câu hỏi.
- Nếu trong các tin nhắn gần nhất hệ thống đã từng yêu cầu làm rõ,
  KHÔNG được sinh thêm câu hỏi làm rõ mới.
  Thay vào đó, phải tổng hợp từ context hiện có để viết lại query.

PHÂN TÍCH:
User Query: {user_query}

Session Summary:
{session_summary}

Recent Messages:
{recent_messages}

{format_instructions}

Chỉ trả về JSON hợp lệ theo đúng schema.
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
