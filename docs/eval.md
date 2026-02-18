# Eval Architecture

The eval framework is in place and functional, but scenario coverage is still incomplete — not all edge cases and behaviors are covered yet.

The eval system tests the AI pipeline components against predefined scenarios with deterministic programmatic checks. No LLM-as-judge — the LLM is the system under test, not the evaluator.

## Running

```bash
./eval.sh                                    # Run all components (3 runs each)
./eval.sh --component triage                 # Run one component
./eval.sh --group startup_founder            # Run only groups matching substring
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

**Deterministic** — embeddings are pre-computed and Qdrant search is deterministic, so multiple runs will produce identical results.

### 3. Triage Agent (`eval_triage_agent.py`)

Tests the full triage agent end-to-end: given an item, does it search correctly and take the right action?

**Checks:**
- `action` — correct action type (create_todo, update_todo, save_fact, update_fact, do_nothing)?
- `args_contain` — do the action's arguments contain expected values? Supports:
  - Keyword containment for lists (case-insensitive)
  - Exact match for scalars (with `fixture_id()` conversion for todo/fact IDs)
- `args_null` — are specific arguments absent (e.g. `description` should not be set on status-only updates)?

**Mutation interception:** Search hits real Qdrant fixtures, but writes (`_create_todo`, `_update_todo`, `_save_fact`, `_update_fact`) are replaced with fakes that record calls. All recorded actions are scanned for a matching entry — the first candidate passing all expected checks wins. (`_update_fact` shares the `_save_fact` patch; the two are distinguished by checking whether the `fact_id` matches a known fixture ID.)

### 4. Daemon Processor (`eval_daemon_processor.py`)

Tests `_extract_triage_items_from_snapshot()` — given an app accessibility tree snapshot, does the LLM correctly extract signal and filter UI noise?

**Checks:**
- `action` — did it return items ("triage") or correctly ignore ("do_nothing")?
- `min_items` / `max_items` — item count within expected range?
- `items_contain` — do extracted items contain expected keywords?
- `items_not_contain` — are noise terms correctly filtered out?
- `context_contains` — do extracted item contexts contain expected keywords?
- `all_items_have_context` — does every extracted item include a context string?

**No Qdrant needed.** Scenarios reference external content files (`datasets/daemon_inputs/`) containing real accessibility tree dumps. Tests Linear and Slack app views.

## Fixtures

### Fixture Sets

Two fixture sets exist under `datasets/fixtures/`:

**`small_baseline.yaml`** — Small baseline (5 todos, 4 facts). Quick sanity checks.

**`startup_founder.yaml`** — Large-scale (100 todos, 200 facts). Based on the Felix startup journal persona. Tests precision when the agent must find the right item among many similar ones across engineering, product, design, marketing, hiring, operations, personal, and team/process categories.

### Pre-computed Embeddings (`fixture_data/<name>/`)

`--generate-fixtures` reads each YAML, computes real embeddings (one vector per tag, multivector), and writes `todos.json` / `facts.json`. These are loaded into Qdrant at eval time.

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
  - name: small_baseline
    fixtures: small_baseline # loads fixture_data/small_baseline/
    scenarios:
      - id: create_new_unrelated
        item:
          text: "Buy a new laptop for work"
          context: ""
        expect:
          action: create_todo
          args_contain:
            title: [laptop]

  - name: startup_founder
    fixtures: startup_founder   # loads fixture_data/startup_founder/
    scenarios:
      - id: status_start_crowded
        ...
```

Groups with no `fixtures` key create empty Qdrant collections (cold-start testing).

## Multi-Run Strategy

LLM outputs are non-deterministic, so all evals default to 3 runs per scenario. A scenario passes only if ALL checks pass in ALL runs. Search is deterministic (pre-computed embeddings), so multiple runs produce identical results.

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
│   │   ├── small_baseline.yaml     # Small baseline (5 todos, 4 facts)
│   │   └── startup_founder.yaml    # Large-scale (100 todos, 200 facts)
│   ├── freewrite_processor.yaml    # Freewrite scenarios
│   ├── search.yaml                 # Search scenarios
│   ├── triage_agent.yaml           # Triage scenarios
│   ├── daemon_processor.yaml       # Daemon scenarios
│   ├── daemon_inputs/              # Accessibility tree dumps for daemon eval
│   └── freewrite_inputs/           # Long-form documents for sliding window evals
└── fixture_data/                   # Generated (git-ignored) — pre-computed embeddings
    ├── small_baseline/
    └── startup_founder/
```
