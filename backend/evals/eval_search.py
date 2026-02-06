from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import yaml

from store.todos import search_todos
from store.facts import search_facts
from .fixtures import cleanup_fixtures, fixture_id, load_fixture_set

DATASETS_DIR = Path(__file__).parent / "datasets"


@dataclass
class ScenarioResult:
    scenario_id: str
    runs: list[dict[str, bool]] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        """Fraction of runs where ALL checks passed."""
        if not self.runs:
            return 0.0
        return sum(1 for r in self.runs if all(r.values())) / len(self.runs)


def _evaluate_once(scenario: dict) -> dict[str, bool]:
    """Run one evaluation of a search scenario."""
    expected = scenario["expect"]

    with patch("store.todos.COLLECTION_NAME", "todos_eval"), \
         patch("store.facts.COLLECTION_NAME", "facts_eval"):

        if scenario["type"] == "todos":
            results = search_todos(query=scenario["query"], user_id=0, limit=10)
            result_ids = [r.todo.id for r in results]
        else:
            results = search_facts(query=scenario["query"], user_id=0, limit=10)
            result_ids = [r.fact.id for r in results]

    checks = {}

    if "top_result" in expected:
        checks["top_result"] = (
            result_ids[0] == fixture_id(expected["top_result"]) if result_ids else False
        )

    if "should_include" in expected:
        for expected_id in expected["should_include"]:
            checks[f"includes_{expected_id}"] = fixture_id(expected_id) in result_ids

    if "should_exclude" in expected:
        for excluded_id in expected["should_exclude"]:
            checks[f"excludes_{excluded_id}"] = fixture_id(excluded_id) not in result_ids

    return checks


def run(runs: int = 1) -> list[ScenarioResult]:
    """Run all search eval scenarios. Deterministic, so 1 run is default."""
    with open(DATASETS_DIR / "search.yaml") as f:
        data = yaml.safe_load(f)

    results = []
    for group in data["groups"]:
        fixture_name = group.get("fixtures")
        if fixture_name:
            print(f"  Loading fixture set: {fixture_name}")
            load_fixture_set(fixture_name)

        try:
            for scenario in group["scenarios"]:
                sr = ScenarioResult(scenario_id=scenario["id"])
                for i in range(runs):
                    print(f"  [{scenario['id']}] run {i + 1}/{runs}...", end=" ", flush=True)
                    checks = _evaluate_once(scenario)
                    passed = all(checks.values())
                    print("PASS" if passed else f"FAIL {checks}")
                    sr.runs.append(checks)
                results.append(sr)
        finally:
            if fixture_name:
                cleanup_fixtures()

    return results
