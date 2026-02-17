# Evals

Evaluates pipeline components individually using real LLM calls and real Qdrant search against pre-computed fixture data.

## Prerequisites

- `OPENROUTER_API_KEY` set in environment (used for LLM calls and embeddings)
- Qdrant running locally (required for search and triage evals)

## Quick start

```bash
cd backend

# 1. Generate fixture embeddings (one-time, or after changing fixture data)
uv run python -m evals.run --generate-fixtures

# 2. Run all evals
uv run python -m evals.run

# 3. Run a specific component
uv run python -m evals.run --component freewrite
uv run python -m evals.run --component search
uv run python -m evals.run --component triage

# 4. Control runs per scenario (default: 3)
uv run python -m evals.run --runs 5

# 5. Set logging level for debugging (default: error)
uv run python -m evals.run --component triage --scenario no_duplicate --log-level info
```

## Components

| Component | What it tests | Needs Qdrant | Needs LLM |
|-----------|--------------|--------------|-----------|
| `freewrite` | `_extract_triage_items()` — extracts actionable items from freeform text | No | Yes |
| `search` | `search_todos()` / `search_facts()` — retrieval quality against fixture data | Yes | Embeddings only |
| `triage` | `triage_agent()` — end-to-end decision making (search + action selection) | Yes | Yes |

## File structure

```
evals/
├── run.py                          # CLI entry point
├── fixtures.py                     # generate / load / cleanup fixture data
├── eval_freewrite_processor.py     # freewrite processor evaluator
├── eval_search.py                  # search evaluator
├── eval_triage_agent.py            # triage agent evaluator
├── datasets/
│   ├── fixtures/                   # fixture sets (Qdrant data)
│   │   └── full.yaml
│   ├── freewrite_processor.yaml    # freewrite test scenarios
│   ├── search.yaml                 # search test scenarios
│   └── triage_agent.yaml           # triage test scenarios
└── fixture_data/                   # generated (git-ignored) — pre-computed embeddings
    └── full/
        ├── todos.json
        └── facts.json
```

## Fixtures

Fixtures define the todos and facts that get loaded into Qdrant test collections before scenarios run. Each YAML file in `datasets/fixtures/` is a named fixture set.

**`datasets/fixtures/full.yaml`** (example):

```yaml
todos:
  - id: "t1"
    title: "Buy groceries"
    description: "milk, eggs, bread"
    status: "pending"
    tags: ["groceries", "shopping"]

facts:
  - id: "f1"
    fact: "User's preferred programming language is Python"
    category: "preference"
    tags: ["programming", "python", "language"]
```

To add a new fixture set, create a new YAML file in `datasets/fixtures/` (e.g. `sparse.yaml`) and run:

```bash
uv run python -m evals.run --generate-fixtures
```

This computes embeddings for all fixture sets and writes them to `fixture_data/<name>/`.

## Scenarios

Scenario files use a `groups` structure. Each group has a name, an optional `fixtures` reference, and an array of test scenarios.

```yaml
groups:
  - name: full_collection
    fixtures: full           # references datasets/fixtures/full.yaml
    scenarios:
      - id: my_test
        ...

  - name: empty_collection   # no fixtures — runs against empty Qdrant collections
    scenarios:
      - id: cold_start_test
        ...
```

When a group has no `fixtures` key, the eval creates empty Qdrant collections for that group's scenarios.

### Freewrite processor scenarios

```yaml
- id: simple_action
  trigger: "I need to buy groceries"      # the user's input text
  document_context: ""                     # surrounding document content
  expect:
    action: triage                         # "triage" or "do_nothing"
    min_items: 1                           # minimum extracted items
    items_contain: ["groceries"]           # keywords in item text (case-insensitive)
    context_contains: ["waitlist"]         # keywords in item context field
```

### Search scenarios

```yaml
- id: exact_keyword_match
  type: todos                              # "todos" or "facts"
  query: "groceries"
  expect:
    top_result: "t1"                       # expected top-1 result ID
    should_include: ["t1"]                 # IDs that must appear in results
    should_exclude: ["t2"]                 # IDs that must not appear
```

### Triage agent scenarios

```yaml
- id: status_change_complete
  item:
    text: "close that"                     # the triage item text
    context: "BLR billboard"               # context from freewrite processor
  expect:
    action: update_todo                    # "create_todo", "update_todo", "save_fact", "do_nothing"
    args_contain:
      todo_id: "t4"                        # exact match on argument value
      status: "completed"                  # exact match
      title: ["laptop", "work"]            # list = keyword check (case-insensitive)
```

## How it works

- **Fixture isolation**: Search and triage evals patch `COLLECTION_NAME` to use `todos_eval` / `facts_eval` collections, keeping production data untouched.
- **Mutation interception**: Triage eval patches `_create_todo`, `_update_todo`, and `_save_fact` with fakes that record calls without writing to Qdrant.
- **Real search**: Search functions run against real Qdrant with pre-computed fixture embeddings. Query embeddings are computed live.
- **Multiple runs**: LLM-based evals (freewrite, triage) are non-deterministic. Run multiple times to measure consistency. Search is deterministic (defaults to 1 run).

## Output

```
============================================================
Search Eval (1 run each)
============================================================
+-----------------+-----------+------+
| Scenario        | Pass Rate | Runs |
+-----------------+-----------+------+
| exact_keyword   | 1/1       | P    |
| semantic_auth   | 1/1       | P    |
| unrelated_query | 0/1       | F    |
+-----------------+-----------+------+
Overall: 2/3 scenarios passed (67%)
```

`P` = all checks passed for that run, `F` = at least one check failed. Failed runs print the individual check results inline.
