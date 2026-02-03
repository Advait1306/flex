# Todo Extraction Pipeline Evaluation Plan

## Overview

This document outlines the evaluation framework for testing the AI pipeline that extracts todos from text. The pipeline consists of two main components:

1. **Context Collector** - Extracts actionable items from trigger text, with optional document context
2. **Triage Agent** - Decides whether to create, update, or ignore each item based on existing todos

## Test Scenario Structure

Each test scenario requires three inputs and expected outputs:

```python
class TestScenario(BaseModel):
    name: str                           # Descriptive test name
    category: str                       # Scenario category for organization

    # Inputs
    trigger: str                        # User's input text (required)
    document_content: list[dict] = []   # BlockNote format blocks (optional)
    existing_todos: list[TodoItem] = [] # Current todo state injected into triage agent

    # Expected outputs
    expected_creates: list[ExpectedTodo]   # Todos that should be created
    expected_updates: list[ExpectedUpdate] # Todos that should be updated
    expected_ignores: int = 0              # Count of items that should be ignored
```

### Supporting Types

```python
class ExpectedTodo(BaseModel):
    title: str                          # Expected title (semantic match)
    description: str | None = None      # Expected description if any
    has_subtasks: bool = False          # Whether subtasks should be created

class ExpectedUpdate(BaseModel):
    match_todo_title: str               # Title of existing todo to match
    new_status: str | None = None       # Expected status change
    new_title: str | None = None        # Expected title change
    new_description: str | None = None  # Expected description change
```

## Scenario Categories

### 1. Simple Create (no context)
Basic todo creation without document context or existing todos.

| Scenario | Trigger | Expected |
|----------|---------|----------|
| Explicit TODO | "TODO: fix the login bug" | Create "fix the login bug" |
| Implicit task | "I need to review the PR" | Create "review the PR" |
| Action verb | "Add unit tests for auth" | Create "Add unit tests for auth" |

### 2. Create with Document Context
Todo creation with background info extracted from document.

| Scenario | Trigger | Document | Expected |
|----------|---------|----------|----------|
| Context enrichment | "Start the design work" | "Working on mobile app redesign" | Create with background_info |
| Multiple items + doc | "Fix bug and add tests" | "Auth module has issues" | 2 creates, both with context |

### 3. Update Status
Status changes to existing todos.

| Scenario | Trigger | Existing Todos | Expected |
|----------|---------|----------------|----------|
| Explicit completion | "Finished the review" | "Review API design" | Update status → completed |
| In progress | "Working on the bug fix" | "Fix login bug" | Update status → in_progress |
| Back to pending | "Need to redo the tests" | "Write tests" (completed) | Update status → pending |

### 4. Fuzzy Matching Updates
Updates where trigger doesn't exactly match todo title.

| Scenario | Trigger | Existing Todos | Expected |
|----------|---------|----------------|----------|
| Keyword match | "Done with auth" | "Fix authentication issue" | Update (match via keywords) |
| Partial match | "Finished API work" | "Review API design" | Update (match via "API") |
| Synonym handling | "Completed the tests" | "Write unit tests" | Update (match via "tests") |

### 5. Multiple Items
Triggers containing multiple actionable items.

| Scenario | Trigger | Expected |
|----------|---------|----------|
| Two creates | "Need to fix bug and review PR" | 2 creates |
| Create + update | "Done with A, need to start B" | 1 update, 1 create |
| Multiple updates | "Finished both reviews" | 2 updates |

### 6. Ignore Cases
Triggers that should result in no action.

| Scenario | Trigger | Expected |
|----------|---------|----------|
| General statement | "That sounds good" | Ignore |
| Question | "What's the status?" | Ignore |
| Acknowledgment | "Got it, thanks" | Ignore |
| Unrelated | "The weather is nice" | Ignore |

### 7. Mixed Operations
Complex scenarios combining multiple operation types.

| Scenario | Trigger | Existing Todos | Expected |
|----------|---------|----------------|----------|
| Update + create | "Done with auth, now need to test" | "Fix auth" | 1 update, 1 create |
| Multiple updates + create | "Finished A and B, starting C" | "Task A", "Task B" | 2 updates, 1 create |

### 8. Subtasks
Scenarios involving parent-child task relationships.

| Scenario | Trigger | Expected |
|----------|---------|----------|
| Explicit subtasks | "Add tests for login and signup" | Parent + 2 subtasks |
| Related items | "Review PR: check types and docs" | Parent + 2 subtasks |

### 9. Edge Cases
Boundary conditions and unusual inputs.

| Scenario | Trigger | Expected |
|----------|---------|----------|
| Empty trigger | "" | No action |
| Very long trigger | "..." (500+ chars) | Appropriate extraction |
| Special characters | "Fix bug #123 @john" | Handle gracefully |
| Multiple languages | Mixed language input | Handle or ignore |
| Duplicate mention | "Fix bug, also fix that bug" | Single create (dedupe) |

## Hybrid Data Generation Approach

### Layer 1: Template-Based (Deterministic Coverage)

Define base templates for each category to ensure complete coverage:

```python
TEMPLATES = {
    "simple_create": [
        {"trigger": "TODO: {task}", "expected_creates": ["{task}"]},
        {"trigger": "Need to {task}", "expected_creates": ["{task}"]},
        {"trigger": "I should {task}", "expected_creates": ["{task}"]},
    ],
    "update_status": [
        {"trigger": "Finished {task}", "existing": ["{task}"], "expected_updates": [("completed", "{task}")]},
        {"trigger": "Done with {task}", "existing": ["{task}"], "expected_updates": [("completed", "{task}")]},
        {"trigger": "Working on {task}", "existing": ["{task}"], "expected_updates": [("in_progress", "{task}")]},
    ],
    # ... more categories
}
```

### Layer 2: LLM Variation (Natural Language Diversity)

Use an LLM to generate variations of the templates:

1. **Trigger Variations**: Different phrasings for the same intent
   - "Finished the review" → "Done reviewing", "Review is complete", "Wrapped up the review"

2. **Document Content Generation**: Realistic BlockNote documents
   - Generate meeting notes, project descriptions, chat excerpts

3. **Task Name Variations**: Diverse but realistic task descriptions
   - Software tasks: "fix bug", "add feature", "refactor module"
   - Generic tasks: "send email", "schedule meeting", "prepare presentation"

### Layer 3: Validation

1. **Automated Consistency Checks**
   - Verify scenario structure is valid
   - Check that expected outputs are consistent with inputs
   - Validate BlockNote format for documents

2. **Human Review (Sample)**
   - Randomly sample 5-10 scenarios per category
   - Verify trigger → expected output makes sense
   - Check edge cases manually

3. **Pipeline Execution**
   - Run scenarios through actual pipeline
   - Compare actual vs expected outputs

## Verification Methods

### 1. Exact Match
For deterministic expectations (status changes, ignore counts):

```python
assert actual.status == expected.status
assert len(actual.created_todos) == len(expected.creates)
```

### 2. Semantic Similarity
For title/description matching where exact match is too strict:

```python
from sentence_transformers import SentenceTransformer

def semantic_match(actual: str, expected: str, threshold: float = 0.8) -> bool:
    embeddings = model.encode([actual, expected])
    similarity = cosine_similarity(embeddings[0], embeddings[1])
    return similarity >= threshold
```

### 3. LLM-as-Judge
For complex semantic verification:

```python
def llm_judge(scenario: TestScenario, actual_output: PipelineResult) -> JudgeResult:
    prompt = f"""
    Given the input:
    - Trigger: {scenario.trigger}
    - Existing todos: {scenario.existing_todos}

    Expected: {scenario.expected_creates}, {scenario.expected_updates}
    Actual: {actual_output.created_todos}, {actual_output.updated_todos}

    Does the actual output semantically match the expected output?
    Score from 0-1 and explain any discrepancies.
    """
    return llm.invoke(prompt)
```

## Implementation Phases

### Phase 1: Foundation
- [ ] Define Pydantic models for test scenarios
- [ ] Create scenario loader (JSON/YAML files)
- [ ] Implement basic test runner

### Phase 2: Data Generation
- [ ] Build template-based generator for each category
- [ ] Create LLM variation generator
- [ ] Generate initial dataset (50-100 scenarios)

### Phase 3: Verification
- [ ] Implement exact match verification
- [ ] Add semantic similarity matching
- [ ] Set up LLM-as-judge for complex cases

### Phase 4: Integration
- [ ] CI/CD integration
- [ ] Metrics dashboard (pass rate, category breakdown)
- [ ] Regression detection

## File Structure

```
evals/
├── plan.md                 # This document
├── scenarios/
│   ├── simple_create.yaml
│   ├── update_status.yaml
│   ├── fuzzy_match.yaml
│   ├── multiple_items.yaml
│   ├── ignore_cases.yaml
│   ├── mixed_operations.yaml
│   ├── subtasks.yaml
│   └── edge_cases.yaml
├── generators/
│   ├── template_generator.py
│   └── llm_variation_generator.py
├── verification/
│   ├── exact_match.py
│   ├── semantic_match.py
│   └── llm_judge.py
├── runner.py               # Main test runner
└── results/                # Test run outputs
```

## Metrics

- **Pass Rate**: % of scenarios where actual matches expected
- **Category Breakdown**: Pass rate per scenario category
- **False Positives**: Created todos that shouldn't exist
- **False Negatives**: Missed creates or updates
- **Match Quality**: Semantic similarity scores for titles/descriptions
