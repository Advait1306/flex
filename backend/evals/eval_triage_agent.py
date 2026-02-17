from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import yaml

from ai.agents.triage_agent import triage_agent
from models import FactItem, TodoItem, TriagePayload
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
    """Run one evaluation of a triage agent scenario."""
    expected = scenario["expect"]
    recorded_actions = []

    def fake_create_todo(title, description=None, parent_id=None, tags=None, user_id=None):
        recorded_actions.append(("create_todo", {
            "title": title,
            "description": description,
            "parent_id": parent_id,
            "tags": tags,
        }))
        return TodoItem(
            id="new-1", title=title, description=description,
            parent_id=parent_id, status="pending",
        )

    def fake_update_todo(todo_id, title=None, description=None, status=None, tags=None, user_id=None):
        recorded_actions.append(("update_todo", {
            "todo_id": todo_id,
            "title": title,
            "description": description,
            "status": status,
            "tags": tags,
        }))
        return TodoItem(
            id=todo_id, title=title or "updated",
            description=description, status=status or "pending",
        )

    def fake_save_fact(fact_item, tags=None, user_id=None):
        recorded_actions.append(("save_fact", {
            "fact_id": fact_item.id,
            "fact": fact_item.fact,
            "category": fact_item.category,
            "tags": tags or fact_item.tags,
        }))
        return fact_item

    with patch("store.todos.COLLECTION_NAME", "todos_eval"), \
         patch("store.facts.COLLECTION_NAME", "facts_eval"), \
         patch("ai.agents.triage_agent._create_todo", fake_create_todo), \
         patch("ai.agents.triage_agent._update_todo", fake_update_todo), \
         patch("ai.agents.triage_agent._save_fact", fake_save_fact):

        item = TriagePayload(
            text=scenario["item"]["text"],
            context=scenario["item"]["context"],
        )
        triage_agent(item, user_id=0)

    if recorded_actions:
        final_action = recorded_actions[-1][0]
        final_args = recorded_actions[-1][1]
    else:
        final_action = "do_nothing"
        final_args = {}

    checks = {}

    # Both save_fact and update_fact tools call _save_fact, so recorded action is
    # always "save_fact". Distinguish by checking if fact_id matches an expected
    # fixture (update_fact) or is a fresh UUID (save_fact).
    if final_action == "save_fact" and expected["action"] == "update_fact":
        expected_fact_id = expected.get("args_contain", {}).get("fact_id")
        checks["action"] = (
            expected_fact_id is not None
            and final_args.get("fact_id") == fixture_id(expected_fact_id)
        )
    else:
        checks["action"] = final_action == expected["action"]

    if "args_contain" in expected:
        for key, expected_val in expected["args_contain"].items():
            actual_val = final_args.get(key, "")

            if isinstance(expected_val, list):
                actual_str = str(actual_val).lower()
                for kw in expected_val:
                    checks[f"arg_{key}_{kw}"] = kw.lower() in actual_str
            else:
                # Convert fixture short IDs (e.g. "t3", "f4") to UUIDs for todo_id/fact_id
                compare_val = fixture_id(expected_val) if key in ("todo_id", "fact_id") else str(expected_val)
                checks[f"arg_{key}"] = str(actual_val) == compare_val

    if "args_null" in expected:
        for key in expected["args_null"]:
            checks[f"arg_{key}_null"] = final_args.get(key) is None

    return checks


def run(runs: int = 3, scenario_filter: str | None = None) -> list[ScenarioResult]:
    """Run triage agent eval scenarios, optionally filtered by ID substring."""
    with open(DATASETS_DIR / "triage_agent.yaml") as f:
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
