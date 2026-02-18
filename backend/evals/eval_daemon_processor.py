from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ai.agents.daemon_processor_agent import _extract_triage_items_from_snapshot

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
    """Run one evaluation of a daemon processor scenario."""
    expected = scenario["expect"]

    content_path = DATASETS_DIR / scenario["content_file"]
    content = content_path.read_text()

    result = _extract_triage_items_from_snapshot(
        content=content,
        app_name=scenario["app_name"],
        app_category=scenario["app_category"],
    )

    checks = {}

    actual_action = "triage" if len(result) > 0 else "do_nothing"
    checks["action"] = actual_action == expected["action"]

    if "max_items" in expected:
        checks["max_items"] = len(result) <= expected["max_items"]

    if "min_items" in expected:
        checks["min_items"] = len(result) >= expected["min_items"]

    if "all_items_have_context" in expected and expected["all_items_have_context"]:
        checks["all_items_have_context"] = all(
            item.context.strip() for item in result
        )

    if "context_contains" in expected:
        all_context = " ".join(item.context for item in result).lower()
        for keyword in expected["context_contains"]:
            checks[f"context_{keyword}"] = keyword.lower() in all_context

    if "items_contain" in expected:
        all_text = " ".join(item.text for item in result).lower()
        for keyword in expected["items_contain"]:
            checks[f"contains_{keyword}"] = keyword.lower() in all_text

    if "items_not_contain" in expected:
        all_text = " ".join(item.text for item in result).lower()
        for keyword in expected["items_not_contain"]:
            checks[f"not_contains_{keyword}"] = keyword.lower() not in all_text

    return checks


def run(runs: int = 3, scenario_filter: str | None = None, group_filter: str | None = None) -> list[ScenarioResult]:
    """Run daemon processor eval scenarios, optionally filtered by ID substring."""
    with open(DATASETS_DIR / "daemon_processor.yaml") as f:
        data = yaml.safe_load(f)

    results = []
    for group in data["groups"]:
        if group_filter and group_filter not in group.get("name", ""):
            continue
        for scenario in group["scenarios"]:
            if scenario_filter and scenario_filter not in scenario["id"]:
                continue
            sr = ScenarioResult(scenario_id=scenario["id"])
            for i in range(runs):
                print(f"  [{scenario['id']}] run {i + 1}/{runs}...", end=" ", flush=True)
                checks = _evaluate_once(scenario)
                passed = all(checks.values())
                print("PASS" if passed else f"FAIL {checks}")
                sr.runs.append(checks)
            results.append(sr)

    return results
