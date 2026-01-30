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
   - LLM outputs được parse thành structured data
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
│              Query Rewriting Service                        │
│  - Detect ambiguity                                         │
│  - Rewrite if needed                                        │
│  - Generate clarifying questions                            │
└──────────────────────┬──────────────────────────────────────┘
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
│              LLM Generation                                 │
│  - Send augmented context to LLM                            │
│  - Generate response                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Summarization Check                            │
│  - Count tokens in conversation                             │
│  - If > threshold: trigger summarization                    │
│  - Save summary to database                                 │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Language**: Python 3.13+
- **Framework**: FastAPI (API), Gradio (UI)
- **LLM**: OpenAI GPT-4 (via langchain-openai)
- **Database**: PostgreSQL with asyncpg
- **ORM**: Custom async ORM with Pydantic
- **Token Counting**: tiktoken

## Setup

### 1. Prerequisites

- Python 3.13+
- Docker & Docker Compose
- OpenAI API key

### 2. Installation

```bash
# Clone và cd vào project
cd test

# Install dependencies
pip install -e .

# Copy .env.example và điền OPENAI_API_KEY
cp .env.example .env
# Edit .env và thêm: OPENAI_API_KEY=sk-...
```

### 3. Database Setup

```bash
# Start PostgreSQL
docker compose up -d

# Wait 5 seconds for DB to be ready, then create schema
python setup_db.py
```

### 4. Run Application

**Option A: FastAPI + Gradio UI (Recommended)**

```bash
# Terminal 1: Run API server
python -m uvicorn api.main:app --reload --port 8000

# Terminal 2: Run Gradio UI
python app_ui/app.py
```

**Option B: Demo Scripts**

```bash
# Run demo flows (Flow 1: Summarization, Flow 2: Ambiguous queries)
python demo.py

# Load test conversation data
python load_test_data.py
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
├── test_data/               # Sample conversation logs
├── demo.py                  # Demo script
├── load_test_data.py        # Load test conversations
└── setup_db.py              # Database setup script
```

## Models & Storage Strategy

### Database Models (Persist to PostgreSQL)

1. **ChatSession** (`chat_session` table)
   - Represents một phiên chat
   - Fields: `id`, `name`, `created_at`

2. **ChatHistory** (`chat_history` table)
   - Lưu toàn bộ messages của 1 session
   - Fields: `id`, `session_id`, `messages` (JSONB array)
   - Messages contain: `role`, `content`, `created_at`

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

## Demo Flows

### Flow 1: Session Memory Trigger

```bash
python demo.py
```

Demo này:
1. Tạo chat session mới
2. Gửi 16+ messages (long conversation)
3. Monitor token count sau mỗi message
4. Khi vượt threshold: trigger summarization
5. Log summary fields: key_facts, decisions, open_questions

**Expected Output:**
```
Total tokens: 8500/10000
Total tokens: 10200/10000  # ← Threshold exceeded!
✓ SUMMARY CREATED!
Key Facts: ['User planning trip to Japan', 'Budget $3000 for 10 days', ...]
```

### Flow 2: Ambiguous Query Handling

```bash
python demo.py
```

Demo này test:
1. Very ambiguous query: "it"
2. Query with unclear reference: "what about that thing?"
3. Vague query: "can you help?"
4. System response với clarifying questions

**Expected Output:**
```
Testing ambiguous query: 'it'
Response: Your question is a bit unclear. Could you clarify:
- Are you asking about something we discussed earlier?
- Do you want information about a specific topic?
✓ Clarifying questions detected!
```

## Test Data

3 conversation logs trong `test_data/`:

1. **conversation_1_long.jsonl** - Long conversation (20 exchanges) về Italy trip planning
   - Tests: Summarization trigger
   - Expected: Summary with travel preferences, budget, decisions

2. **conversation_2_ambiguous.jsonl** - Series of ambiguous queries
   - Tests: Query rewriting, clarifying questions
   - Progression: ambiguous → clarified → specific

3. **conversation_3_context_building.jsonl** - Context building over time
   - Tests: Context augmentation
   - Shows: How system maintains context across turns

Load test data:
```bash
python load_test_data.py
```

## Configuration

Edit [.env](.env):

```bash
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/chat_db
TOKEN_THRESHOLD=10000        # Trigger summarization
MAX_CONTEXT_MESSAGES=20      # Max messages in context
SUMMARIZE_THRESHOLD=15       # Min messages before summarize
KEEP_RECENT=5                # Messages to keep after summarize
```

## API Endpoints

```
POST   /sessions                      - Create new chat session
GET    /sessions                      - List all sessions
GET    /sessions/{session_id}         - Get session details + messages
POST   /chats/{chat_id}/messages      - Send message (non-streaming)
POST   /chats/{chat_id}/messages/stream - Send message (streaming)
```

## Limitations

1. **Token Counting**: Hiện dùng tiktoken với gpt-4 encoding, có thể không chính xác 100% cho các models khác
2. **Summarization**: Chỉ summarize 1 lần khi trigger, không merge với summaries cũ
3. **Query Rewriting**: Dựa vào LLM, có thể không stable 100%
4. **Database**: Chưa có indexes optimization cho large scale
5. **Error Handling**: Basic error handling, chưa có retry logic

## Future Improvements

- [ ] Incremental summarization (merge với summaries cũ)
- [ ] Caching cho LLM calls
- [ ] Embeddings cho semantic search trong history
- [ ] Multi-user support với authentication
- [ ] Rate limiting
- [ ] Monitoring & logging dashboard

## License

MIT
