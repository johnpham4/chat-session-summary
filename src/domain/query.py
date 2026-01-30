from typing import Optional
from pydantic import BaseModel
from dataclasses import dataclass
from typing import Optional, List
from langchain_core.messages import BaseMessage

from src.domain.chat import ChatSession

class QueryRewriting(BaseModel):
    original_query: str
    is_ambiguous: bool
    rewritten_query: Optional[str] = None
    clarifying_questions: List[str] = []


@dataclass
class PreprocessResult:
    chat: ChatSession
    context_messages: Optional[List[BaseMessage]] = None
    early_response: Optional[str] = None
