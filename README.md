# Chat Assistant with Session Memory

Chat assistant backend với tính năng session memory thông qua automatic summarization và query understanding pipeline.

## Features

### ✅ Core Features (Implemented)

1. **Session Memory via Summarization**
   - Tự động trigger summarization khi context vượt ngưỡng (~10k tokens)
   - Sử dụng tiktoken để đếm tokens chính xác
   - Lưu trữ summary vào PostgreSQL database
   - Schema: `user_profile`, `key_facts`, `decisions`, `open_questions`, `todos`

2. **Query Understanding Pipeline**
   - **Step 1**: Detect và rewrite ambiguous queries
   - **Step 2**: Context augmentation từ recent messages + session summary
   - **Step 3**: Generate clarifying questions nếu query vẫn unclear

3. **Structured Outputs**
   - Sử dụng Pydantic models cho tất cả outputs
   - LLM outputs được parse thành structured data (Pydantic model)
   - Validation tự động

4. **Storage**
   - PostgreSQL database cho persistence
   - 3 tables: `chat_session`, `chat_history`, `chat_session_summary`
   - Async operations với asyncpg

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Input (Query)                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Summarization Check                            │
│  - Count tokens in conversation                             │
│  - If > threshold: trigger summarization                    │
│  - Save summary to database                                 │
│   (if no summary -> get the last summary)                   │
│  - Soft delete out-of-window messages (Keep recent messages)│
└─────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Context Augmentation                           │
│  - Combine recent messages                                  │
│  - Add session summary (if available)                       │
│  - Build final context                                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Query Rewriting Service                        │
│  - Detect ambiguity                                         │
│  - If Rewrite (send to LLM to generate output)              │
│  - If generate clarifying questions (Ask user to confirm)   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              LLM Generation                                 │
│  - Send augmented context to LLM                            │
│  - Generate response                                        │
└──────────────────────┬──────────────────────────────────────┘
```

## Tech Stack

- **Language**: Python 3.13+
- **Framework**: FastAPI (API), Gradio (UI)
- **LLM**: OpenAI GPT-4o (via langchain-openai)
- **Database**: PostgreSQL with asyncpg
- **ORM**: Custom async ORM with Pydantic

## Setup

### 1. Prerequisites

- Python 3.13+
- Docker & Docker Compose
- OpenAI API key

### 2. Installation

```bash
# Clone và cd vào project
cd repo_name

# Install dependencies
uv sync

# Copy .env.example và điền OPENAI_API_KEY
cp .env.example .env
# Edit .env và thêm: OPENAI_API_KEY=sk-...
```

### 3. Database Setup

```bash
# Start PostgreSQL
docker compose up -d
```

### 4. Run Application

**Option A: FastAPI + Gradio UI (Recommended)**

```bash
# Terminal 1: Run API server
in make file run make endpoint

# Terminal 2: Run Gradio UI
in make file run make ui
```
## Project Structure

```
.
├── api/
│   └── main.py              # FastAPI endpoints
├── app_ui/
│   └── app.py               # Gradio UI
├── db/
│   └── schema.sql           # Database schema
├── src/
│   ├── settings.py          # Configuration
│   ├── application/
│   │   └── chat/
│   │       ├── chat.py              # Main chat service
│   │       ├── summarization.py     # Summarization logic
│   │       ├── rewriting.py         # Query rewriting
│   │       └── context_augment.py   # Context augmentation
│   ├── domain/
│   │   ├── chat.py          # Domain models (ChatMessage, ChatHistory, etc.)
│   │   └── query.py         # Query models (QueryRewriting, etc.)
│   └── infrastructure/
│       ├── db/postgres/     # Database layer
│       └── llm/             # LLM clients
```

## Models & Storage Strategy

### Database Models (Persist to PostgreSQL)

1. **ChatSession** (`chat_session` table)
   - Represents một phiên chat
   - Fields: `id`, `name`, `created_at`, `is_deleted`

2. **ChatMessageRecord** (`chat_message` table)
   - Lưu toàn bộ messages của 1 session
   - Fields: `id`, `session_id`, `role`, `content`, `is_deleted`

3. **ChatSessionSummary** (`chat_session_summary` table)
   - Lưu summarization results
   - Fields: `id`, `session_id`, `user_profile`, `key_facts`, `decisions`, `open_questions`, `todos`
   - Created when token threshold exceeded

### DTO Models (In-memory only)

1. **QueryRewriting** (Pydantic model)
   - Kết quả từ query rewriting pipeline
   - Fields: `original_query`, `is_ambiguous`, `rewritten_query`, `clarifying_questions`, etc.
   - Không lưu database (chỉ dùng trong pipeline)

2. **SessionContext** (Pydantic model)
   - Context được extract từ session summary
   - Used for query augmentation
   - Không persist

3. **PreprocessResult** (dataclass)
   - Internal result object
   - Contains: `chat`, `context_messages`, `early_response`


## API Endpoints

```
POST   /sessions                      - Create new chat session
GET    /sessions                      - List all sessions
GET    /sessions/{session_id}         - Get session details + messages
POST   /chats/{chat_id}/messages      - Send message (non-streaming)
POST   /chats/{chat_id}/messages/stream - Send message (streaming)
```
