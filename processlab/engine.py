"""Deterministic lane-assignment engine.

No LLM calls happen here, by design. An LLM may describe a process, but this
module decides where AI is allowed. Rules are evaluated top to bottom and the
first match wins.

    R1  Already automated                              -> KEEP
    R2  Structured input + clear rule                  -> AUTOMATE
          (hard gate if irreversible or high-stakes)
    R3  Irreversible, or high consequence in a
        high-stakes domain                             -> HUMAN
    R4  Unstructured + low consequence + reversible    -> AI
    R5  Unstructured (anything else)                   -> AI_ASSIST
    R6a Structured, unclear rule, low consequence      -> AI_ASSIST
    R6b Structured, unclear rule, higher consequence   -> HUMAN
"""

from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from processlab.schema import (
    InputType,
    Lane,
    LaneDecision,
    Level,
    Process,
    ProcessReport,
    Reversibility,
    RuleClarity,
    Step,
)

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "thresholds.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    with open(path or DEFAULT_CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    for key in ("high_stakes_domains", "weights"):
        if key not in config:
            raise ValueError(f"Config is missing required key: '{key}'")
    return config


def _high_stakes(step: Step, config: dict[str, Any]) -> list[str]:
    stakes = set(config["high_stakes_domains"])
    return [d.value for d in step.domains if d.value in stakes]


def opportunity_score(step: Step, config: dict[str, Any]) -> int:
    """0-100: how much this step would benefit from redesign."""
    if step.already_automated:
        return 0
    w = config["weights"]
    raw = (
        w["volume"][step.volume.value]
        + w["exception_rate"][step.exception_rate.value]
        + w["input_type"][step.input_type.value]
    )
    max_raw = max(w["volume"].values()) + max(w["exception_rate"].values()) + max(
        w["input_type"].values()
    )
    return round(100 * raw / max_raw)


def assign_lane(step: Step, config: dict[str, Any]) -> LaneDecision:
    stakes = _high_stakes(step, config)
    score = opportunity_score(step, config)

    def decide(lane: Lane, rule_id: str, reasons: list[str], hard_gate: bool = False):
        return LaneDecision(
            step_id=step.id,
            step_name=step.name,
            lane=lane,
            rule_id=rule_id,
            reasons=reasons,
            hard_gate=hard_gate,
            opportunity_score=score,
        )

    # R1: don't re-solve what already works
    if step.already_automated:
        return decide(Lane.KEEP, "R1", ["Already automated in the current process. Keep as-is."])

    unstructured = step.input_type == InputType.UNSTRUCTURED
    clear_rule = step.rule_clarity == RuleClarity.CLEAR
    irreversible = step.reversibility == Reversibility.IRREVERSIBLE
    high_consequence = step.consequence == Level.HIGH

    # R2: rules don't need a language model
    if not unstructured and clear_rule:
        hard_gate = irreversible or (high_consequence and bool(stakes))
        reasons = ["Structured input with a clear rule. Deterministic automation, no AI needed."]
        if hard_gate:
            why = "irreversible" if irreversible else f"high consequence ({', '.join(stakes)})"
            reasons.append(
                f"Hard gate: {why}. AI is excluded from this step by design; "
                "the rule must be tested and every outcome logged."
            )
        return decide(Lane.AUTOMATE, "R2", reasons, hard_gate=hard_gate)

    # R3: judgment with serious or permanent consequences stays human
    if irreversible or (high_consequence and stakes):
        reasons = []
        if irreversible:
            reasons.append("Irreversible action without a clear rule.")
        if high_consequence and stakes:
            reasons.append(f"High consequence in a high-stakes domain ({', '.join(stakes)}).")
        reasons.append("Requires human judgment.")
        return decide(Lane.HUMAN, "R3", reasons)

    # R4: messy input, low stakes, easy to undo -> let AI handle it
    if unstructured and step.consequence == Level.LOW and step.reversibility == Reversibility.REVERSIBLE:
        return decide(
            Lane.AI,
            "R4",
            ["Unstructured input that needs interpretation.", "Low consequence and reversible, so AI can act alone."],
        )

    # R5: messy input with real stakes -> AI drafts, human approves
    if unstructured:
        return decide(
            Lane.AI_ASSIST,
            "R5",
            [
                "Unstructured input that needs interpretation.",
                f"Consequence is {step.consequence.value} / {step.reversibility.value}, "
                "so a human approves the AI's output.",
            ],
        )

    # R6: structured data but no clean rule
    if step.consequence == Level.LOW:
        return decide(
            Lane.AI_ASSIST,
            "R6a",
            ["Structured input but the rule is not fully defined.", "Low consequence: AI suggests, human confirms."],
        )
    return decide(
        Lane.HUMAN,
        "R6b",
        [
            "Structured input but the rule is not fully defined.",
            f"{step.consequence.value.capitalize()} consequence: keep human judgment "
            "(candidate for writing a clearer rule later).",
        ],
    )


def analyze_process(process: Process, config: dict[str, Any] | None = None) -> ProcessReport:
    config = config or load_config()
    decisions = [assign_lane(step, config) for step in process.steps]
    counts = Counter(d.lane for d in decisions)
    return ProcessReport(
        process_name=process.name,
        decisions=decisions,
        lane_counts={lane: counts.get(lane, 0) for lane in Lane},
        manual_steps_before=sum(1 for s in process.steps if not s.already_automated),
        manual_steps_after=sum(1 for d in decisions if d.lane in (Lane.HUMAN, Lane.AI_ASSIST)),
        hard_gates=[d.step_id for d in decisions if d.hard_gate],
    )
