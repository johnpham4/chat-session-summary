from typing import Optional
from pydantic import BaseModel
from dataclasses import dataclass
from typing import Optional, List
from langchain_core.messages import BaseMessage

from src.domain.chat import ChatSession


class SessionContext(BaseModel):
    user_profile_prefs: list[str] = []
    open_questions: list[str] = []

class QueryRewriting(BaseModel):
    original_query: str
    is_ambiguous: bool
    rewritten_query: str | None = None
    needed_context_from_memory: SessionContext
    clarifying_questions: list[str] = []
    final_augmented_context: str

    def add_questions(self, clarified_quetions: list[str]) -> "QueryRewriting":
        self.clarifying_questions.extend(clarified_quetions)


@dataclass
class PreprocessResult:
    chat: ChatSession
    context_messages: Optional[List[BaseMessage]] = None
    early_response: Optional[str] = None
