import argparse
import logging

from tabulate import tabulate

LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
}

ALL_COMPONENTS = ["freewrite", "search", "triage", "daemon"]


def print_results(component: str, results: list, runs: int):
    """Print formatted results table for a component."""
    labels = {
        "freewrite": "Freewrite Processor",
        "search": "Search",
        "triage": "Triage Agent",
        "daemon": "Daemon Processor",
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
        "--scenario",
        help="Run only scenarios matching this substring (e.g. 'duplicate' or 'status_change')",
    )
    parser.add_argument(
        "--generate-fixtures",
        action="store_true",
        help="Regenerate fixture embeddings and exit",
    )
    parser.add_argument(
        "--log-level",
        choices=LOG_LEVELS.keys(),
        default="error",
        help="Logging level (default: error)",
    )
    args = parser.parse_args()

    # Must call setup_logging BEFORE importing modules that use get_logger
    from logging_config import setup_logging
    setup_logging(level=LOG_LEVELS[args.log_level])

    from ai.config import set_app_name
    set_app_name("Flex-Eval")

    from .fixtures import generate_fixtures
    from . import eval_daemon_processor, eval_freewrite_processor, eval_search, eval_triage_agent

    if args.generate_fixtures:
        generate_fixtures()
        return

    components = [args.component] if args.component else ALL_COMPONENTS

    if "freewrite" in components:
        print("\nRunning freewrite processor eval...")
        results = eval_freewrite_processor.run(runs=args.runs, scenario_filter=args.scenario)
        print_results("freewrite", results, args.runs)

    if "search" in components:
        print("\nRunning search eval...")
        results = eval_search.run(runs=args.runs, scenario_filter=args.scenario)
        print_results("search", results, args.runs)

    if "triage" in components:
        print("\nRunning triage agent eval...")
        results = eval_triage_agent.run(runs=args.runs, scenario_filter=args.scenario)
        print_results("triage", results, args.runs)

    if "daemon" in components:
        print("\nRunning daemon processor eval...")
        results = eval_daemon_processor.run(runs=args.runs, scenario_filter=args.scenario)
        print_results("daemon", results, args.runs)


if __name__ == "__main__":
    main()
