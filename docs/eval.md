# Eval Architecture

The eval framework is in place and functional, but scenario coverage is still incomplete — not all edge cases and behaviors are covered yet.

The eval system tests the AI pipeline components against predefined scenarios with deterministic programmatic checks. No LLM-as-judge — the LLM is the system under test, not the evaluator.

## Running

```bash
./eval.sh                                    # Run all components (3 runs each)
./eval.sh --component triage                 # Run one component
./eval.sh --runs 5                           # Override runs per scenario
./eval.sh --scenario create_new              # Filter scenarios by substring
./eval.sh --log-level debug                  # Set log verbosity (debug/info/warn/error)
./eval.sh --generate-fixtures                # Regenerate fixture embeddings only
./eval.sh --generate-fixtures --component triage  # Regenerate then run specific eval
```

## Components

Four independent eval modules, each testing a different stage of the pipeline:

### 1. Freewrite Processor (`eval_freewrite_processor.py`)

Tests `_extract_triage_items()` — given trigger text + document context, does the LLM correctly extract actionable items?

**Checks:**
- `action` — did it return items ("triage") or correctly ignore ("do_nothing")?
- `min_items` — at least N items extracted?
- `items_contain` — do extracted item texts contain expected keywords?
- `context_contains` — do extracted item contexts contain expected keywords?
- `all_items_have_context` — does every extracted item include a context string?

**No Qdrant needed.** This only tests LLM extraction.

### 2. Search (`eval_search.py`)

Tests `search_todos()` and `search_facts()` retrieval quality against fixture data in Qdrant.

**Checks:**
- `top_result` — is the first result the expected one?
- `includes_<id>` — is a specific item in the results?
- `excludes_<id>` — is a specific item absent from the results?

**Deterministic** — defaults to 1 run since embeddings are pre-computed and Qdrant search is deterministic.

### 3. Triage Agent (`eval_triage_agent.py`)

Tests the full triage agent end-to-end: given an item, does it search correctly and take the right action?

**Checks:**
- `action` — correct action type (create_todo, update_todo, save_fact, update_fact, do_nothing)?
- `args_contain` — do the action's arguments contain expected values? Supports:
  - Keyword containment for lists (case-insensitive)
  - Exact match for scalars (with `fixture_id()` conversion for todo/fact IDs)
- `args_null` — are specific arguments absent (e.g. `description` should not be set on status-only updates)?

**Mutation interception:** Search hits real Qdrant fixtures, but writes (`_create_todo`, `_update_todo`, `_save_fact`, `_update_fact`) are replaced with fakes that record calls. The last recorded action is checked against expectations.

### 4. Daemon Processor (`eval_daemon_processor.py`)

Tests `_extract_triage_items_from_snapshot()` — given an app accessibility tree snapshot, does the LLM correctly extract signal and filter UI noise?

**Checks:**
- `action` — did it return items ("triage") or correctly ignore ("do_nothing")?
- `min_items` / `max_items` — item count within expected range?
- `items_contain` — do extracted items contain expected keywords?
- `items_not_contain` — are noise terms correctly filtered out?
- `context_contains` — do extracted item contexts contain expected keywords?
- `all_items_have_context` — does every extracted item include a context string?

**No Qdrant needed.** Scenarios reference external content files (`datasets/daemon_inputs/`) containing real accessibility tree dumps. Currently tests Linear app views.

## Fixtures

### Fixture Definitions (`datasets/fixtures/full.yaml`)

Defines a test universe of todos and facts:

| ID  | Item                            | Type | Status      |
| --- | ------------------------------- | ---- | ----------- |
| t1  | Buy groceries                   | todo | pending     |
| t2  | Fix authentication bug          | todo | in_progress |
| t3  | Set up waitlist for Felix       | todo | pending     |
| t4  | Buy billboards for BLR          | todo | pending     |
| t5  | Call dentist for appointment    | todo | pending     |
| f1  | Preferred language is Python    | fact | preference  |
| f2  | Works at startup called Felix   | fact | work        |
| f3  | Sabesh handles frontend         | fact | work        |
| f4  | SuperMemory for vector/graph DB | fact | work        |

### Pre-computed Embeddings (`fixture_data/full/`)

`generate_fixtures` reads the YAML, computes real embeddings (one vector per tag, multivector), and writes `todos.json` / `facts.json`. These are loaded into Qdrant at eval time.

### Deterministic IDs

YAML uses short IDs (`t1`, `f1`). `fixture_id()` converts these to deterministic UUIDs via `uuid.uuid5` with a fixed namespace, so eval checks can compare against expected IDs.

## Isolation

Evals never touch production data:

1. **Collection patching** — `unittest.mock.patch` redirects `COLLECTION_NAME` to `todos_eval` / `facts_eval` in Qdrant
2. **Mutation interception** (triage only) — write functions are replaced with recording fakes
3. **Cleanup** — `cleanup_fixtures()` deletes eval collections in a `finally` block
4. **Traffic tagging** — `X-Title: Flex-Eval` header on all OpenRouter requests distinguishes eval from production LLM calls

## Scenarios

Scenarios are defined in YAML files under `datasets/`. Each file uses a `groups` structure where each group references a fixture set:

```yaml
groups:
  - name: full_collection
    fixtures: full          # loads fixture_data/full/
    scenarios:
      - id: create_new_unrelated
        item:
          text: "Buy a new laptop for work"
          context: ""
        expect:
          action: create_todo
          args_contain:
            title: [laptop]
```

Groups with no `fixtures` key create empty Qdrant collections (cold-start testing).

## Multi-Run Strategy

LLM outputs are non-deterministic, so freewrite, triage, and daemon evals default to 3 runs per scenario. A scenario passes only if ALL checks pass in ALL runs. Search defaults to 1 run (deterministic).

Output shows per-run pass/fail:

```
Component: triage
Scenario                    Runs    Pass
--------------------------  ------  ----
create_new_unrelated        PPP     3/3
update_existing_with_ctx    PPF     2/3
meaningless_greeting        PPP     3/3
```

## File Structure

```
evals/
├── run.py                          # CLI entry point + results formatter
├── fixtures.py                     # Fixture generation, loading, cleanup
├── eval_freewrite_processor.py     # Freewrite extraction eval
├── eval_search.py                  # Search retrieval eval
├── eval_triage_agent.py            # Triage agent eval
├── eval_daemon_processor.py        # Daemon snapshot extraction eval
├── datasets/
│   ├── fixtures/
│   │   └── full.yaml               # Fixture definitions (todos + facts)
│   ├── freewrite_processor.yaml    # Freewrite scenarios
│   ├── search.yaml                 # Search scenarios
│   ├── triage_agent.yaml           # Triage scenarios
│   ├── daemon_processor.yaml       # Daemon scenarios
│   └── daemon_inputs/              # Accessibility tree dumps for daemon eval
│       ├── linear_simple_title.txt
│       ├── linear_issue_detail.txt
│       ├── linear_board_view.txt
│       └── linear_pr_view.txt
└── fixture_data/
    └── full/
        ├── todos.json              # Pre-computed todo embeddings
        └── facts.json              # Pre-computed fact embeddings
```
