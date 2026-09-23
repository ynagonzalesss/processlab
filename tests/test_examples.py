"""Every example process must validate, and the published redesigns must not drift."""

import json
from pathlib import Path

import pytest

from processlab.engine import analyze_process
from processlab.schema import Lane, Process

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
ALL_EXAMPLES = sorted(EXAMPLES_DIR.glob("*.json"))

EXPECTED = {
    "deal_desk.json": {
        "capture_deal_request": Lane.AI,
        "sync_opportunity": Lane.KEEP,
        "validate_deal_fields": Lane.AUTOMATE,
        "route_by_discount_tier": Lane.AUTOMATE,
        "approve_nonstandard_discount": Lane.HUMAN,
        "summarize_nonstandard_terms": Lane.AI_ASSIST,
        "generate_quote": Lane.AUTOMATE,
        "send_contract": Lane.KEEP,
        "draft_customer_update": Lane.AI_ASSIST,
        "release_order_to_billing": Lane.AUTOMATE,
    },
    "invoice_approval.json": {
        "forward_to_ap_inbox": Lane.KEEP,
        "extract_invoice_fields": Lane.AI,
        "three_way_match": Lane.AUTOMATE,
        "check_duplicate": Lane.AUTOMATE,
        "suggest_gl_coding": Lane.AI_ASSIST,
        "resolve_match_exception": Lane.AI_ASSIST,
        "approve_within_tolerance": Lane.AUTOMATE,
        "approve_high_value": Lane.HUMAN,
        "handle_bank_detail_change": Lane.HUMAN,
        "release_payment": Lane.AUTOMATE,
        "send_remittance": Lane.KEEP,
        "answer_payment_status": Lane.AI,
    },
}

EXPECTED_GATES = {
    "deal_desk.json": ["release_order_to_billing"],
    "invoice_approval.json": ["release_payment"],
}


def load(path: Path) -> Process:
    return Process.model_validate(json.loads(path.read_text()))


def test_there_are_at_least_three_examples():
    assert len(ALL_EXAMPLES) >= 3


@pytest.mark.parametrize("path", ALL_EXAMPLES, ids=lambda p: p.name)
def test_example_validates_and_has_a_hard_gate(path, config):
    report = analyze_process(load(path), config)
    assert report.hard_gates, "every example should demonstrate at least one hard gate"


@pytest.mark.parametrize(
    "filename,step_id,lane",
    [(f, s, l) for f, steps in EXPECTED.items() for s, l in steps.items()],
)
def test_step_lane(filename, step_id, lane, config):
    report = analyze_process(load(EXAMPLES_DIR / filename), config)
    decision = next(d for d in report.decisions if d.step_id == step_id)
    assert decision.lane == lane


@pytest.mark.parametrize("filename", EXPECTED)
def test_expected_covers_every_step(filename):
    ids = {s.id for s in load(EXAMPLES_DIR / filename).steps}
    assert ids == set(EXPECTED[filename])


@pytest.mark.parametrize("filename,gates", EXPECTED_GATES.items())
def test_hard_gates(filename, gates, config):
    assert analyze_process(load(EXAMPLES_DIR / filename), config).hard_gates == gates


def test_money_movement_never_uses_ai(config):
    """Across every example, anything irreversible and financial stays out of AI lanes."""
    for path in ALL_EXAMPLES:
        process = load(path)
        report = analyze_process(process, config)
        by_id = {s.id: s for s in process.steps}
        for d in report.decisions:
            step = by_id[d.step_id]
            if step.reversibility.value == "irreversible" and "financial" in [x.value for x in step.domains]:
                assert d.lane not in (Lane.AI, Lane.AI_ASSIST), f"{path.name}:{d.step_id}"
