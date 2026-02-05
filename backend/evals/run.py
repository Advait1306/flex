import argparse
import sys

from tabulate import tabulate

# Break circular import: store -> ai.logging_config -> ai/__init__ -> ai.agents -> store
# Solution: stub the ai package so ai.logging_config can be imported without running
# ai/__init__.py (which eagerly imports agents that depend on store).
# Once store is loaded, we let the real ai/__init__ run.
import types as _types
from pathlib import Path as _Path

_ai_pkg = _types.ModuleType("ai")
_ai_pkg.__path__ = [str(_Path(__file__).resolve().parent.parent / "ai")]
_ai_pkg.__package__ = "ai"
sys.modules["ai"] = _ai_pkg

import store  # noqa: F401 - store loads fully (ai.logging_config loads under the stub)

# Replace stub with real package — store is in sys.modules so the cycle is broken
del sys.modules["ai"]
import ai  # noqa: F401

from ai.config import set_app_name
set_app_name("Flex-Eval")

from .fixtures import generate_fixtures
from . import eval_freewrite_processor, eval_search, eval_triage_agent

ALL_COMPONENTS = ["freewrite", "search", "triage"]


def print_results(component: str, results: list, runs: int):
    """Print formatted results table for a component."""
    labels = {
        "freewrite": "Freewrite Processor",
        "search": "Search",
        "triage": "Triage Agent",
    }
    print(f"\n{'=' * 60}")
    print(f"{labels[component]} Eval ({runs} run{'s' if runs != 1 else ''} each)")
    print(f"{'=' * 60}")

    rows = []
    total_passed = 0
    total_scenarios = len(results)

    for sr in results:
        pass_count = sum(1 for r in sr.runs if all(r.values()))
        all_passed = pass_count == len(sr.runs)
        total_passed += 1 if all_passed else 0

        checks_str = "".join("P" if all(r.values()) else "F" for r in sr.runs)
        rows.append([sr.scenario_id, f"{pass_count}/{len(sr.runs)}", checks_str])

    print(tabulate(rows, headers=["Scenario", "Pass Rate", "Runs"], tablefmt="grid"))
    print(f"Overall: {total_passed}/{total_scenarios} scenarios passed "
          f"({total_passed / total_scenarios * 100:.0f}%)\n")


def main():
    parser = argparse.ArgumentParser(description="Run evals for pipeline components")
    parser.add_argument(
        "--component",
        choices=ALL_COMPONENTS,
        help="Run eval for a specific component (default: all)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per scenario (default: 3)",
    )
    parser.add_argument(
        "--generate-fixtures",
        action="store_true",
        help="Regenerate fixture embeddings and exit",
    )
    args = parser.parse_args()

    if args.generate_fixtures:
        generate_fixtures()
        return

    components = [args.component] if args.component else ALL_COMPONENTS

    if "freewrite" in components:
        print("\nRunning freewrite processor eval...")
        results = eval_freewrite_processor.run(runs=args.runs)
        print_results("freewrite", results, args.runs)

    if "search" in components:
        print("\nRunning search eval...")
        results = eval_search.run(runs=args.runs)
        print_results("search", results, args.runs)

    if "triage" in components:
        print("\nRunning triage agent eval...")
        results = eval_triage_agent.run(runs=args.runs)
        print_results("triage", results, args.runs)


if __name__ == "__main__":
    main()
