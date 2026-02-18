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

# 4. Run a specific group (substring match on group name)
uv run python -m evals.run --component triage --group startup_founder
uv run python -m evals.run --component triage --group small_baseline

# 5. Control runs per scenario (default: 3)
uv run python -m evals.run --runs 5

# 6. Filter scenarios + set log level for debugging
uv run python -m evals.run --component triage --scenario no_duplicate --log-level info
```

## Components

| Component | What it tests | Needs Qdrant | Needs LLM |
|-----------|--------------|--------------|-----------|
| `freewrite` | `_extract_triage_items()` — extracts actionable items from freeform text | No | Yes |
| `search` | `search_todos()` / `search_facts()` — retrieval quality against fixture data | Yes | Embeddings only |
| `triage` | `triage_agent()` — end-to-end decision making (search + action selection) | Yes | Yes |
| `daemon` | `_extract_triage_items_from_snapshot()` — extracts signal from app accessibility trees | No | Yes |

## File structure

```
evals/
├── run.py                          # CLI entry point
├── fixtures.py                     # generate / load / cleanup fixture data
├── eval_freewrite_processor.py     # freewrite processor evaluator
├── eval_search.py                  # search evaluator
├── eval_triage_agent.py            # triage agent evaluator
├── eval_daemon_processor.py        # daemon snapshot extraction evaluator
├── datasets/
│   ├── fixtures/                   # fixture sets (Qdrant data)
│   │   ├── full.yaml               # small baseline (5 todos, 4 facts)
│   │   └── startup_founder.yaml    # large-scale (100 todos, 200 facts)
│   ├── freewrite_processor.yaml    # freewrite test scenarios
│   ├── freewrite_inputs/           # long-form document files for sliding window evals
│   │   └── startup_journal.txt
│   ├── search.yaml                 # search test scenarios
│   ├── triage_agent.yaml           # triage test scenarios
│   ├── daemon_processor.yaml       # daemon test scenarios
│   └── daemon_inputs/              # accessibility tree dumps (Linear, Slack)
└── fixture_data/                   # generated (git-ignored) — pre-computed embeddings
    ├── full/
    └── startup_founder/
```

## Fixtures

Fixtures define the todos and facts that get loaded into Qdrant test collections before scenarios run. Each YAML file in `datasets/fixtures/` is a named fixture set.

| Fixture | Size | Purpose |
|---------|------|---------|
| `full.yaml` | 5 todos, 4 facts | Small baseline for quick sanity checks |
| `startup_founder.yaml` | 100 todos, 200 facts | Large-scale precision tests based on startup journal persona |

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
  - name: small_baseline
    fixtures: full               # references datasets/fixtures/full.yaml
    scenarios:
      - id: my_test
        ...

  - name: startup_founder
    fixtures: startup_founder    # references datasets/fixtures/startup_founder.yaml
    scenarios:
      - id: status_start_crowded
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

### Sliding window mode (freewrite)

Groups can reference a `document_file` to run sliding window scenarios against a long document. Each scenario uses `trigger_line` (a paragraph index) instead of inline `trigger`/`document_context`:

```yaml
- name: long_context
  document_file: freewrite_inputs/startup_journal.txt
  scenarios:
    - id: sw_action_early
      trigger_line: 42          # 0-based paragraph index
      expect:
        action: triage
        min_items: 1
        items_contain: ["budget review"]
```

The document is split by `\n\n` into paragraphs. For each scenario:
- **trigger** = the paragraph at `trigger_line`
- **document_context** = all preceding paragraphs joined with `\n`

This tests how the freewrite processor handles increasing context sizes. Early paragraphs get small context (~500 words), late paragraphs get large context (~20k words). The eval prints context word count per scenario for visibility.

The document file (`startup_journal.txt`) is a ~20k word freewrite journal with known anchor paragraphs at specific indices — some actionable, some noise.

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

### Daemon processor scenarios

```yaml
- id: slack_dm_task_request
  app_name: "Slack"                            # application name
  app_category: "electron"                     # app category
  content_file: "daemon_inputs/slack_dm.txt"   # accessibility tree dump
  expect:
    action: triage                             # "triage" or "do_nothing"
    min_items: 2                               # minimum extracted items
    max_items: 4                               # maximum extracted items
    all_items_have_context: true               # every item must have context
    items_contain: ["PR #247"]                 # keywords in item text
    items_not_contain: ["[Button]", "[Link]"]  # UI chrome correctly filtered
```

## How it works

- **Fixture isolation**: Search and triage evals patch `COLLECTION_NAME` to use `todos_eval` / `facts_eval` collections, keeping production data untouched.
- **Mutation interception**: Triage eval patches `_create_todo`, `_update_todo`, and `_save_fact` with fakes that record calls. All recorded actions are scanned for a matching entry (not just the last action).
- **Real search**: Search functions run against real Qdrant with pre-computed fixture embeddings. Query embeddings are computed live.
- **Multiple runs**: LLM-based evals (freewrite, triage, daemon) are non-deterministic. Run multiple times to measure consistency. Search is deterministic (defaults to 1 run).

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
