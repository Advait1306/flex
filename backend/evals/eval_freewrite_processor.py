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


def _load_document_paragraphs(document_file: str) -> list[str]:
    """Load a document file and split into paragraphs by double-newline."""
    doc_path = DATASETS_DIR / document_file
    doc_text = doc_path.read_text()
    return [p.strip() for p in doc_text.split("\n\n") if p.strip()]


def _resolve_scenario(scenario: dict, paragraphs: list[str] | None) -> dict:
    """Resolve trigger/context from document paragraphs if using sliding window mode."""
    if paragraphs is None or "trigger_line" not in scenario:
        return scenario

    idx = scenario["trigger_line"]
    resolved = {**scenario}
    resolved["trigger"] = paragraphs[idx]
    resolved["document_context"] = "\n".join(paragraphs[:idx])
    return resolved


def run(runs: int = 3, scenario_filter: str | None = None, group_filter: str | None = None) -> list[ScenarioResult]:
    """Run freewrite processor eval scenarios, optionally filtered by ID substring."""
    with open(DATASETS_DIR / "freewrite_processor.yaml") as f:
        data = yaml.safe_load(f)

    results = []
    for group in data["groups"]:
        if group_filter and group_filter not in group.get("name", ""):
            continue
        scenarios = [s for s in group["scenarios"] if not scenario_filter or scenario_filter in s["id"]]
        if not scenarios:
            continue

        fixture_name = group.get("fixtures")
        document_file = group.get("document_file")

        paragraphs = None
        if document_file:
            paragraphs = _load_document_paragraphs(document_file)
            print(f"  Loaded document: {document_file} ({len(paragraphs)} paragraphs)")

        if fixture_name:
            print(f"  Loading fixture set: {fixture_name}")
            load_fixture_set(fixture_name)

        try:
            for scenario in scenarios:
                resolved = _resolve_scenario(scenario, paragraphs)

                if paragraphs is not None and "trigger_line" in scenario:
                    ctx_words = len(resolved["document_context"].split())
                    print(f"  [{scenario['id']}] trigger_line={scenario['trigger_line']}, context={ctx_words} words")

                sr = ScenarioResult(scenario_id=scenario["id"])
                for i in range(runs):
                    print(f"  [{scenario['id']}] run {i + 1}/{runs}...", end=" ", flush=True)
                    checks = _evaluate_once(resolved)
                    passed = all(checks.values())
                    print("PASS" if passed else f"FAIL {checks}")
                    sr.runs.append(checks)
                results.append(sr)
        finally:
            if fixture_name:
                cleanup_fixtures()

    return results
