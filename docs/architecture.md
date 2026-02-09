# Flex Architecture

Flex is an AI-powered task and knowledge management app built around freewriting. Users type or dictate stream-of-consciousness text into a block editor; the system automatically extracts actionable todos and user facts using an LLM agent pipeline.

**Stack**: Next.js frontend + FastAPI backend + LangChain agents + Qdrant (vector search) + PostgreSQL

---

## Infrastructure

Two Docker services (`backend/docker-compose.yml`):

| Service    | Image               | Port         | Purpose                    |
| ---------- | ------------------- | ------------ | -------------------------- |
| `qdrant`   | qdrant/qdrant:v1.16 | 6333 / 6334  | Vector DB for todos/facts  |
| `postgres` | postgres:17         | 5433 -> 5432 | Users + freewrite docs     |

Data persists to `storage/` (gitignored).

---

## Backend

### Entry Point (`main.py`)

FastAPI app with async lifespan: initializes Tortoise ORM + Qdrant collections on startup. Registers four routers and CORS middleware.

### Authentication (`auth.py`)

HTTP Basic auth. `verify_user()` dependency looks up username in Postgres and verifies with bcrypt. All routers are protected.

### Shared Types (`models.py`)

- **`TodoItem`** -- id, title, description, parent_id, status (pending/in_progress/completed/cancelled), timestamps
- **`FactItem`** -- id, fact, category (preference/personal/work/context/other), tags, created_at
- **`TriagePayload`** -- text + context, passed from freewrite processor to triage agent

### Database Models (`db_models.py`)

- **`User`** -- username, password_hash (Postgres)
- **`FreewriteDocument`** -- JSON content, one per user (Postgres)

Todos and facts live in Qdrant, not Postgres.

### API Routers

| Endpoint                     | Method | Description                                       |
| ---------------------------- | ------ | ------------------------------------------------- |
| `/api/freewrite`             | GET    | Load freewrite content                            |
| `/api/freewrite`             | PUT    | Save content, compute diff, trigger AI pipeline   |
| `/api/todos`                 | GET    | List all todos                                    |
| `/api/todos/{id}`            | GET    | Get a todo                                        |
| `/api/todos`                 | POST   | Create a todo                                     |
| `/api/todos/{id}`            | PATCH  | Update a todo                                     |
| `/api/todos/{id}`            | DELETE | Delete a todo                                     |
| `/api/facts`                 | GET    | List all facts (read-only, created by AI)         |
| `/api/transcription/session` | POST   | Get ephemeral OpenAI token for voice transcription |

### AI Agent Pipeline (`ai/`)

Two-stage pipeline triggered when freewrite content changes:

**Stage 1: Freewrite Processor** (`ai/agents/freewrite_processor_agent.py`)
- Takes trigger text (newly typed text) + document context
- Uses LLM structured output to extract actionable items as `TriagePayload` objects
- Filters noise (greetings, gibberish, single characters)
- Fans out to triage agents via `asyncio.gather()`

**Stage 2: Triage Agent** (`ai/agents/triage_agent.py`)
- Processes one extracted item at a time via a tool-calling loop (max 5 iterations)
- Has six tools: `search_todos`, `search_facts`, `create_todo`, `update_todo`, `save_fact`, `do_nothing`
- Always searches before acting to avoid duplicates
- Decides: status change, new todo, update existing todo description, save as fact, or do nothing

**Queue Manager** (`ai/queue_manager.py`)
- Singleton async queue ensuring pipeline triggers are processed serially
- Prevents race conditions from rapid successive saves

**LLM Config** (`ai/config.py`)
- All LLM and embedding calls routed through OpenRouter
- Default model: `openai/gpt-5-mini`, temperature 0.1

### Storage Layer (`store/`)

| Data       | Store    | Why                                                   |
| ---------- | -------- | ----------------------------------------------------- |
| Users      | Postgres | Relational, auth queries                              |
| Freewrite  | Postgres | JSON column, one per user, no search needed           |
| Todos      | Qdrant   | Semantic search for triage agent to find related todos |
| Facts      | Qdrant   | Semantic search for triage agent to find relevant knowledge |

Both Qdrant collections use **multivector** config (MaxSim comparator) — each document has multiple embedding vectors (from tags). Search is **hybrid**: vector similarity + keyword full-text, merged and deduped.

---

## Frontend

### Stack

Next.js 16, React 19, BlockNote editor, Tailwind CSS v4, SWR, Axios, Radix UI / Shadcn components.

### Layout (`components/editor/DocumentFeed.tsx`)

Two-panel split:
- **Left**: BlockNote editor + voice input button
- **Right**: Tabbed sidebar with Todos and Facts lists

### Block Editor (`components/editor/BlockEditor.tsx`)

Minimal BlockNote editor (no menus, no toolbar — just text input). Smart auto-save: immediate on sentence-ending punctuation or newline, 1-second debounce otherwise.

### Voice Input (`hooks/useRealtimeTranscription.ts`)

1. Backend issues ephemeral OpenAI token (`POST /api/transcription/session`)
2. Frontend opens WebSocket directly to OpenAI Realtime API
3. Mic audio captured at 24kHz, converted to PCM16/Base64, sent via WebSocket
4. OpenAI handles VAD + transcription server-side (`gpt-4o-transcribe`)
5. Completed transcription inserted into editor, triggering the save → AI pipeline flow

### Auth (`components/AuthGate.tsx`)

Login form → Base64-encodes credentials → stores in sessionStorage → Axios interceptor attaches `Authorization: Basic` header on every request.

### Data Fetching

SWR with 500ms polling for todos and facts. Freewrite content loaded on mount.

---

## Data Flow

### Text → Todos/Facts

```
User types in BlockEditor
  → auto-save calls PUT /api/freewrite
    → compute diff (old vs new text)
    → save to Postgres
    → enqueue PipelineTrigger
      → Freewrite Processor extracts items via LLM
        → fan out to Triage Agents (one per item)
          → search existing todos/facts
          → create_todo / update_todo / save_fact / do_nothing
            → writes to Qdrant
```

### Voice → Text → Todos/Facts

```
Mic button clicked
  → get ephemeral OpenAI token
  → WebSocket to OpenAI Realtime API
  → audio streamed, VAD + transcription server-side
  → transcription inserted into BlockEditor
    → same flow as text input above
```
