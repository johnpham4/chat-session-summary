from src.domain.chat import ChatSessionSummary, ChatMessage

class ContextAugmentService:
    @staticmethod
    def augment_context(
        original_query: str,
        rewritten_query: str | None,
        recent_messages: list[ChatMessage],
        summary: ChatSessionSummary | None = None
    ) -> str:
        context_parts = []

        # Add session summary if available
        if summary:
            summary_text = "[Session Context]\n"
            if summary.user_profile:
                summary_text += f"User Profile: {summary.user_profile}\n"
            if summary.key_facts:
                summary_text += f"Key Facts: {', '.join(summary.key_facts)}\n"
            if summary.decisions:
                summary_text += f"Decisions Made: {', '.join(summary.decisions)}\n"
            if summary.open_questions:
                summary_text += f"Open Questions: {', '.join(summary.open_questions)}\n"
            if summary.todos:
                summary_text += f"TODOs: {', '.join(summary.todos)}\n"
            context_parts.append(summary_text)

        # Add recent messages
        if recent_messages:
            messages_text = "[Recent Conversation]\n"
            for msg in recent_messages[-5:]:  # Last 5 messages
                messages_text += f"{msg.role}: {msg.content}\n"
            context_parts.append(messages_text)

        # Add current query
        query_to_use = rewritten_query or original_query
        context_parts.append(f"[Current Query]\n{query_to_use}")

        return "\n\n".join(context_parts)
