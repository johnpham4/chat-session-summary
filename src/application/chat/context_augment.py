from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from src.domain.chat import ChatSession, ChatSessionSummary
from src.domain.query import QueryRewriting
from src.infrastructure.settings import settings

class ContextAugmentService:

    def build_messages(
        self,
        system_prompt: str,
        session: ChatSession,
        summary: ChatSessionSummary | None,
        query_result: QueryRewriting
    ) -> list:

        messages = [SystemMessage(content=system_prompt)]

        if summary:
            memory_blocks = []

            # if "user_profile" in query_result.needed_context_from_memory:
            #     memory_blocks.append(
            #         f"User preferences: {summary.user_profile.preferences}"
            #     )

            if summary.key_facts:
                memory_blocks.append("Key facts:\n- " + "\n- ".join(summary.key_facts))

            if summary.open_questions:
                memory_blocks.append(
                    "Open questions:\n- " + "\n- ".join(summary.open_questions)
                )

            if memory_blocks:
                messages.append(
                    SystemMessage(
                        content="[Session Memory]\n" + "\n\n".join(memory_blocks)
                    )
                )

        # 2. Recent messages
        for msg in session.messages[-settings.KEEP_RECENT:]:
            if msg[1].role == "user":
                messages.append(HumanMessage(content=msg[1].content))
            elif msg[1].role == "assistant":
                messages.append(AIMessage(content=msg[1].content))

        # 3. Final query
        final_query = query_result.rewritten_query or query_result.original_query
        messages.append(HumanMessage(content=final_query))

        return messages
