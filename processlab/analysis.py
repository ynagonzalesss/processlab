"""Graph-aware checks that sit on top of the lane engine.

The engine scores each step on its own. These checks look at the process as a
whole: what feeds a hard gate, and how much each lane depends on a single
hand-assigned label.
"""

from typing import Any

from processlab.engine import assign_lane
from processlab.schema import (
    InputType,
    Lane,
    LaneDecision,
    Level,
    Process,
    Reversibility,
    RuleClarity,
    Step,
)

# Attributes that drive lane assignment, in order from least to most cautious.
_SCALES: dict[str, list] = {
    "input_type": [InputType.STRUCTURED, InputType.UNSTRUCTURED],
    "rule_clarity": [RuleClarity.CLEAR, RuleClarity.PARTIAL, RuleClarity.NONE],
    "reversibility": [Reversibility.REVERSIBLE, Reversibility.COSTLY, Reversibility.IRREVERSIBLE],
    "consequence": [Level.LOW, Level.MEDIUM, Level.HIGH],
}


def upstream(process: Process, step_id: str) -> list[str]:
    """Every step that feeds `step_id`, directly or through other steps."""
    graph = {s.id: s.depends_on for s in process.steps}
    seen: list[str] = []
    stack = list(graph[step_id])
    while stack:
        node = stack.pop()
        if node not in seen:
            seen.append(node)
            stack.extend(graph[node])
    return seen


def _reaches_unchecked(process: Process, lanes: dict[str, Lane], gate: str, source: str) -> bool:
    """True if some route from `source` to `gate` passes no step that validates `source`.

    A step only counts as a check if it declares `validates` and is not itself
    an AI-alone step: a rule or a person has to do the checking.
    """
    steps = {s.id: s for s in process.steps}
    seen: set[str] = set()
    stack = [gate]
    while stack:
        node = stack.pop()
        if node == source:
            return True
        if node in seen:
            continue
        seen.add(node)
        if source in steps[node].validates and lanes[node] != Lane.AI:
            continue  # this route is checked; don't look further up it
        stack.extend(steps[node].depends_on)
    return False


def tainted_gates(process: Process, decisions: list[LaneDecision]) -> list[str]:
    """Warn when a hard gate consumes unchecked output from a step where AI acts alone.

    A gate excludes AI from the decision itself, but if an unreviewed AI step
    produced the gate's input, AI still influences the outcome. Every route
    from the AI step to the gate must pass a step that `validates` it.
    """
    lanes = {d.step_id: d.lane for d in decisions}
    warnings = []
    for d in decisions:
        if not d.hard_gate:
            continue
        ai_sources = [
            u
            for u in upstream(process, d.step_id)
            if lanes[u] == Lane.AI and _reaches_unchecked(process, lanes, d.step_id, u)
        ]
        if ai_sources:
            warnings.append(
                f"Hard gate '{d.step_id}' depends on unchecked AI output from: "
                f"{', '.join(sorted(ai_sources))}. Route it through a step that "
                "validates it (a rule or a human) before the gate."
            )
    return warnings


def fragility(step: Step, config: dict[str, Any]) -> list[str]:
    """Single one-notch label changes that would move this step to another lane."""
    base = assign_lane(step, config).lane
    if base == Lane.KEEP:
        return []
    flips = []
    for attr, scale in _SCALES.items():
        i = scale.index(getattr(step, attr))
        for j in (i - 1, i + 1):
            if 0 <= j < len(scale):
                lane = assign_lane(step.model_copy(update={attr: scale[j]}), config).lane
                if lane != base:
                    flips.append(f"{attr}: {scale[i].value} -> {scale[j].value} gives {lane.value}")
    return flips
