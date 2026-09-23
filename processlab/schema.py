"""Data contracts for ProcessLab.

Every process, whether hand-written or extracted by an LLM later, must pass
through these models. If it doesn't validate, the rules engine never sees it.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InputType(str, Enum):
    STRUCTURED = "structured"      # form fields, status flags, system data
    UNSTRUCTURED = "unstructured"  # emails, chat messages, free text


class RuleClarity(str, Enum):
    CLEAR = "clear"      # can be written as a complete if/then
    PARTIAL = "partial"  # rules cover common cases, judgment for the rest
    NONE = "none"        # judgment every time


class Reversibility(str, Enum):
    REVERSIBLE = "reversible"
    COSTLY = "costly"            # can be undone, but it hurts
    IRREVERSIBLE = "irreversible"


class Level(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Domain(str, Enum):
    FINANCIAL = "financial"
    LEGAL = "legal"
    SAFETY = "safety"
    COMPLIANCE = "compliance"
    RELATIONSHIP = "relationship"
    OPERATIONAL = "operational"


class Lane(str, Enum):
    KEEP = "keep"            # already automated, leave it alone
    AUTOMATE = "automate"    # deterministic automation, no AI
    AI = "ai"                # AI acts on its own
    AI_ASSIST = "ai_assist"  # AI drafts, human approves
    HUMAN = "human"          # human only


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    system: str | None = None
    input_type: InputType
    rule_clarity: RuleClarity
    reversibility: Reversibility
    consequence: Level
    domains: list[Domain] = Field(default_factory=list)
    volume: Level
    exception_rate: Level
    already_automated: bool = False
    depends_on: list[str] = Field(default_factory=list)
    notes: str | None = None


class Process(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    steps: list[Step] = Field(min_length=1)

    @model_validator(mode="after")
    def check_graph(self) -> "Process":
        ids = [s.id for s in self.steps]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"Duplicate step ids: {sorted(dupes)}")

        known = set(ids)
        for step in self.steps:
            missing = [d for d in step.depends_on if d not in known]
            if missing:
                raise ValueError(f"Step '{step.id}' depends on unknown steps: {missing}")
            if step.id in step.depends_on:
                raise ValueError(f"Step '{step.id}' depends on itself")

        # Cycle detection (DFS, three-colour)
        graph = {s.id: s.depends_on for s in self.steps}
        state: dict[str, int] = {}  # 0/absent = unvisited, 1 = visiting, 2 = done

        def visit(node: str, path: list[str]) -> None:
            if state.get(node) == 1:
                cycle = path[path.index(node):] + [node]
                raise ValueError(f"Dependency cycle: {' -> '.join(cycle)}")
            if state.get(node) == 2:
                return
            state[node] = 1
            for dep in graph[node]:
                visit(dep, path + [node])
            state[node] = 2

        for node in graph:
            visit(node, [])
        return self


class LaneDecision(BaseModel):
    step_id: str
    step_name: str
    lane: Lane
    rule_id: str
    reasons: list[str]
    hard_gate: bool = False
    opportunity_score: int = Field(ge=0, le=100)


class ProcessReport(BaseModel):
    process_name: str
    decisions: list[LaneDecision]
    lane_counts: dict[Lane, int]
    manual_steps_before: int
    manual_steps_after: int
    hard_gates: list[str]
