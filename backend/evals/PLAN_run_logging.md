# Per-Run Logging for Evals

## Problem

`AgentLog` in `ai/logging_config.py` is a singleton with a single class-level `_file` handle. During evals, scenarios run sequentially, but there's no per-scenario log capture. We need:

1. A `runs/` folder where each eval invocation gets a timestamped directory
2. Per-scenario agent log files within that directory
3. A summary file with the tabulated results
4. Make `AgentLog` directable to arbitrary paths so the eval framework can point it at per-scenario files

## Current State

- `AgentLog.start()` (`ai/logging_config.py:56-65`) creates its own path at `logs/agent_YYYYMMDD_HHMMSS.log` and opens a file handle
- `AgentLog.close()` (`ai/logging_config.py:143-150`) closes the file
- In production, `run_freewrite_processor_agent()` calls `start()` once, all triage agents write to the same file, then `close()` is called
- In eval code, neither `start()` nor `close()` is called — agent log writes are silently dropped (`if cls._file` guards)

## Plan

### Step 1: Add `path` parameter to `AgentLog.start()`

**File:** `ai/logging_config.py:56-65`

Change `start()` to accept an optional path. If provided, use it instead of generating one.

```python
@classmethod
def start(cls, path: Path | None = None) -> Path:
    """Start a new agent log file. Returns the log file path."""
    if cls._file:
        cls._file.close()

    if path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = LOGS_DIR / f"agent_{timestamp}.log"

    path.parent.mkdir(parents=True, exist_ok=True)
    cls._path = path
    cls._file = open(cls._path, "w")
    cls._write_header()
    return cls._path
```

This is fully backwards-compatible — production code calls `AgentLog.start()` with no args and gets the same behavior.

### Step 2: Create run directory in `run.py`

In `main()`, before running any evals, create a timestamped run directory:

```python
from datetime import datetime
from pathlib import Path

RUNS_DIR = Path(__file__).parent / "runs"

run_dir = RUNS_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
run_dir.mkdir(parents=True, exist_ok=True)
```

Pass `run_dir` to each eval module's `run()` function.

### Step 3: Update eval modules to manage `AgentLog` per scenario

Each eval module's `run()` accepts `run_dir: Path`. Before each scenario run, call `AgentLog.start(path)` to direct logs to a file in the run directory. After each run, call `AgentLog.close()`.

**Log file naming:** `{component}/{scenario_id}_run{n}.log`

```
runs/20260205_143022/
├── summary.txt
├── freewrite/
│   ├── simple_action_run1.log
│   ├── simple_action_run2.log
│   └── ...
├── search/
│   └── ...                        (search has no agent logs, but create dir for consistency)
└── triage/
    ├── create_new_unrelated_run1.log
    └── ...
```

For **freewrite** and **triage** evals (which trigger `AgentLog` writes):

```python
def run(runs: int, run_dir: Path) -> list[ScenarioResult]:
    component_dir = run_dir / "freewrite"  # or "triage"
    component_dir.mkdir(exist_ok=True)
    ...
    for i in range(runs):
        log_path = component_dir / f"{scenario['id']}_run{i + 1}.log"
        AgentLog.start(log_path)
        try:
            checks = _evaluate_once(scenario)
        finally:
            AgentLog.close()
```

For **search** eval: no `AgentLog` calls, so just skip the start/close. Still create the dir and pass `run_dir` for signature consistency.

### Step 4: Save summary to run directory

In `run.py`, after all evals complete, write the tabulated output to `runs/<timestamp>/summary.txt` in addition to printing to stdout.

Reuse the existing `print_results()` function but also capture output to a file. Simplest approach: build all output lines as strings, write them to both stdout and the summary file.

### Files to modify

| File | Change |
|------|--------|
| `ai/logging_config.py` | Add optional `path` param to `AgentLog.start()` |
| `evals/eval_freewrite_processor.py` | Accept `run_dir`, call `AgentLog.start(path)` / `close()` per scenario run |
| `evals/eval_search.py` | Accept `run_dir` (no AgentLog calls, just for signature consistency) |
| `evals/eval_triage_agent.py` | Accept `run_dir`, call `AgentLog.start(path)` / `close()` per scenario run |
| `evals/run.py` | Create run dir, pass to eval modules, write summary.txt |

### Verification

1. Run `python -m evals.run --component freewrite --runs 2`
2. Check `evals/runs/<timestamp>/` exists
3. Check `evals/runs/<timestamp>/freewrite/simple_action_run1.log` has AgentLog output
4. Check `evals/runs/<timestamp>/summary.txt` matches stdout
