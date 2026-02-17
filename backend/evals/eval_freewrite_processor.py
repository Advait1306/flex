from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ai.agents.freewrite_processor_agent import _extract_triage_items
from .fixtures import cleanup_fixtures, load_fixture_set

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
    """Run one evaluation of a freewrite processor scenario."""
    expected = scenario["expect"]

    result = _extract_triage_items(
        trigger_text=scenario["trigger"],
        document_context=scenario["document_context"],
    )

    checks = {}

    actual_action = "triage" if len(result) > 0 else "do_nothing"
    checks["action"] = actual_action == expected["action"]

    if "min_items" in expected:
        checks["item_count"] = len(result) >= expected["min_items"]

    if "items_contain" in expected:
        all_text = " ".join(item.text for item in result).lower()
        for keyword in expected["items_contain"]:
            checks[f"contains_{keyword}"] = keyword.lower() in all_text

    if "all_items_have_context" in expected and expected["all_items_have_context"]:
        checks["all_items_have_context"] = all(
            item.context.strip() for item in result
        )

    if "context_contains" in expected:
        all_context = " ".join(item.context for item in result).lower()
        for keyword in expected["context_contains"]:
            checks[f"context_{keyword}"] = keyword.lower() in all_context

    return checks


def run(runs: int = 3, scenario_filter: str | None = None) -> list[ScenarioResult]:
    """Run freewrite processor eval scenarios, optionally filtered by ID substring."""
    with open(DATASETS_DIR / "freewrite_processor.yaml") as f:
        data = yaml.safe_load(f)

    results = []
    for group in data["groups"]:
        fixture_name = group.get("fixtures")
        scenarios = [s for s in group["scenarios"] if not scenario_filter or scenario_filter in s["id"]]
        if not scenarios:
            continue

        if fixture_name:
            print(f"  Loading fixture set: {fixture_name}")
            load_fixture_set(fixture_name)

        try:
            for scenario in scenarios:
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
