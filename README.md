# Flex

**Flex turns streams of work context into structured todos and durable facts.** It accepts typed notes, live speech, and ambient context from macOS applications, extracts useful signals with language models, and reconciles them against a semantic memory instead of creating an endless list of duplicates.

Flex is a proof of concept for an ambient work assistant: capture information near the moment it appears, distill it into a smaller structured state, and let that state evolve as new evidence arrives.

## Project status

> [!IMPORTANT]
> Flex is an applied-AI prototype, not a production monitoring tool. The end-to-end paths work, but authentication, privacy controls, provider-failure handling, daemon isolation, and operational hardening are incomplete. Use it only with test data and applications you are comfortable sending through the configured model providers.

## What it demonstrates

- **Multiple signal sources** — typed freewrite sessions, realtime voice transcription, and macOS accessibility-tree snapshots
- **Signal extraction** — separate processors turn noisy documents or UI trees into focused pieces of intent and context
- **Agentic triage** — a tool-using agent searches before deciding whether to create, update, complete, ignore, or store information
- **Semantic memory** — todos and facts use hybrid vector and keyword retrieval with multivector tag embeddings
- **Continuous reconciliation** — new observations can update existing work rather than producing duplicate tasks
- **Traceable AI behavior** — LangSmith traces expose extraction and triage steps for debugging and feedback
- **Deterministic evaluation** — scenario fixtures, isolated collections, programmatic assertions, and repeated runs test nondeterministic model behavior

## End-to-end flow

```text
┌─────────────────────────────────────────────────────────────┐
│ Inputs                                                      │
│ freewrite editor · live voice · macOS application context   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                  extraction processors
                            │
                  text + relevant context
                            │
                ┌───────────▼───────────┐
                │ Triage agent         │
                │ search before action │
                └───────────┬───────────┘
                            │
       ┌────────────────────┼─────────────────────┐
       │                    │                     │
 create/update todo   save/update fact       do nothing
       │                    │
       └────────────┬───────┘
                    │
        Qdrant semantic memory + Postgres documents
```

The freewrite and daemon paths have different extraction prompts but converge on the same triage layer. Triage can search todos and facts, then choose among a constrained set of mutations. An async queue serializes incoming triggers so rapid document saves do not race each other.

## Components

```text
flex/
├── frontend/       # Next.js freewrite, voice, todo, and fact interface
├── backend/        # FastAPI API, AI pipelines, storage, and evals
├── daemon/         # Native macOS menu-bar context collector in Swift
├── docs/           # Architecture, daemon, eval, and readiness notes
├── install.sh      # Dependency bootstrap
├── run.sh          # Frontend/backend development runner
├── daemon.sh       # Daemon build, bundle, and debugging commands
└── eval.sh         # AI pipeline evaluation entry point
```

## Technical design

| Layer | Implementation |
| --- | --- |
| Interface | Next.js 16, React 19, BlockNote, SWR, Tailwind CSS |
| API | FastAPI, async Python, Tortoise ORM |
| AI pipeline | LangChain model/tool interfaces, structured output, OpenRouter |
| Voice | Mistral Voxtral realtime transcription over a WebSocket proxy |
| Memory | Qdrant hybrid search with multivector MaxSim embeddings |
| Documents/auth | PostgreSQL and HTTP Basic authentication |
| Native context | Swift macOS daemon using Accessibility APIs and AppleScript where required |
| Evaluation | YAML scenarios, fixed fixtures, isolated Qdrant collections, repeated programmatic checks |

### Why todos and facts are separate

Todos represent intent: work that can be pending, in progress, completed, or cancelled. Facts represent context that may make a later action more useful, such as a preference, decision, person, or project detail. Searching both stores lets Flex enrich a task without forcing every useful observation to become a task itself.

### Why the daemon deduplicates locally

Accessibility trees are noisy and can be polled frequently. Flex hashes extracted snapshots on-device and suppresses exact repeats before invoking the backend. This reduces redundant model traffic, but it is not a complete privacy boundary; non-duplicate captured content still leaves the device in the current prototype.

## Evaluation strategy

The eval harness tests four surfaces:

| Component | What is checked |
| --- | --- |
| Freewrite processor | Extraction, noise rejection, and context propagation |
| Search | Retrieval quality over fixed todo/fact fixtures |
| Triage agent | Tool choice and expected create/update/no-op behavior |
| Daemon processor | Signal extraction from application snapshots |

LLM-backed scenarios run three times by default and pass only when every run satisfies deterministic assertions. Search scenarios use precomputed embeddings, while triage writes are intercepted so evals cannot mutate normal collections.

```sh
./eval.sh
./eval.sh --component triage
./eval.sh --group startup_founder --runs 5
```

See [`docs/eval.md`](docs/eval.md) for fixtures, isolation, scenario formats, and failure output.

## Run locally

### Prerequisites

- macOS for the native daemon
- Docker Desktop
- Python 3.12 and [`uv`](https://docs.astral.sh/uv/)
- Node.js and npm
- API credentials for the model/transcription providers being tested

Create local environment files:

```sh
cp frontend/.env.example frontend/.env
cp backend/.env.example backend/.env
cp daemon/.env.example daemon/.env
```

Install and run the web application and API:

```sh
./install.sh
./run.sh
```

- Frontend: `http://localhost:3002`
- Backend: `http://localhost:8000`
- Qdrant: `http://localhost:6333`
- PostgreSQL: `localhost:5433`

Run one application at a time when debugging:

```sh
./run.sh frontend
./run.sh backend
```

## macOS daemon

The menu-bar daemon extracts context from supported applications and posts changed snapshots to the backend.

```sh
./daemon.sh

# Inspect extraction without running the complete pipeline
./daemon.sh --tree Slack
./daemon.sh --tree "Google Chrome"
./daemon.sh --tree Safari --raw

# Build an application bundle
./daemon.sh bundle
```

The daemon requires Accessibility permission. Chromium content extraction also depends on the browser's Apple Events JavaScript setting. See [`docs/daemon.md`](docs/daemon.md) for the extraction strategies and known limitations.

## Known limitations

- Provider timeouts, rate limits, and outages are not yet handled end to end.
- The daemon's application polling is not fully isolated; an unresponsive accessibility target can stall collection.
- Basic authentication and session-storage credentials are development choices, not a production security model.
- Current freewrite and captured context can be transmitted to external model providers.
- Action provenance and user-facing audit history are not yet implemented.
- Eval coverage is functional but does not yet cover every failure mode.

The more detailed engineering assessment is in [`docs/production_readiness.md`](docs/production_readiness.md).

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — services, pipelines, storage, and data flows
- [`docs/daemon.md`](docs/daemon.md) — application extraction and change detection
- [`docs/eval.md`](docs/eval.md) — evaluation design and fixture isolation
- [`docs/production_readiness.md`](docs/production_readiness.md) — reliability, privacy, observability, and remaining work

## License

No license has been selected yet. Until one is added, all rights are reserved.
