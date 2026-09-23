import itertools

from processlab.engine import assign_lane, opportunity_score
from processlab.schema import InputType, Lane, Level, Reversibility, RuleClarity
from tests.conftest import make_step


# --- One test per rule -------------------------------------------------------

def test_r1_already_automated_is_kept(config):
    d = assign_lane(make_step(already_automated=True, input_type="unstructured"), config)
    assert (d.lane, d.rule_id) == (Lane.KEEP, "R1")
    assert d.opportunity_score == 0


def test_r2_structured_clear_is_automated(config):
    d = assign_lane(make_step(), config)
    assert (d.lane, d.rule_id, d.hard_gate) == (Lane.AUTOMATE, "R2", False)


def test_r2_high_stakes_becomes_hard_gate(config):
    d = assign_lane(make_step(consequence="high", domains=["compliance"]), config)
    assert d.lane == Lane.AUTOMATE and d.hard_gate


def test_r2_irreversible_becomes_hard_gate(config):
    d = assign_lane(make_step(reversibility="irreversible"), config)
    assert d.lane == Lane.AUTOMATE and d.hard_gate


def test_r3_irreversible_judgment_is_human(config):
    d = assign_lane(make_step(input_type="unstructured", rule_clarity="none",
                              reversibility="irreversible"), config)
    assert (d.lane, d.rule_id) == (Lane.HUMAN, "R3")


def test_r3_high_stakes_judgment_is_human(config):
    d = assign_lane(make_step(input_type="unstructured", rule_clarity="partial",
                              consequence="high", domains=["financial"]), config)
    assert (d.lane, d.rule_id) == (Lane.HUMAN, "R3")


def test_r4_low_risk_messy_input_goes_to_ai(config):
    d = assign_lane(make_step(input_type="unstructured", rule_clarity="partial"), config)
    assert (d.lane, d.rule_id) == (Lane.AI, "R4")


def test_r5_messy_input_with_stakes_is_ai_assist(config):
    d = assign_lane(make_step(input_type="unstructured", rule_clarity="partial",
                              consequence="medium"), config)
    assert (d.lane, d.rule_id) == (Lane.AI_ASSIST, "R5")


def test_r5_high_consequence_non_stakes_domain_is_ai_assist(config):
    d = assign_lane(make_step(input_type="unstructured", consequence="high",
                              domains=["relationship"]), config)
    assert d.lane == Lane.AI_ASSIST


def test_r6a_structured_unclear_low_is_ai_assist(config):
    d = assign_lane(make_step(rule_clarity="partial"), config)
    assert (d.lane, d.rule_id) == (Lane.AI_ASSIST, "R6a")


def test_r6b_structured_unclear_higher_is_human(config):
    d = assign_lane(make_step(rule_clarity="none", consequence="medium"), config)
    assert (d.lane, d.rule_id) == (Lane.HUMAN, "R6b")


def test_every_decision_explains_itself(config):
    d = assign_lane(make_step(), config)
    assert d.reasons and all(r.strip() for r in d.reasons)


# --- Opportunity score -------------------------------------------------------

def test_opportunity_score_bounds(config):
    low = make_step(volume="low", exception_rate="low", input_type="structured")
    high = make_step(volume="high", exception_rate="high", input_type="unstructured")
    assert 0 < opportunity_score(low, config) < opportunity_score(high, config) == 100


# --- Guardrail invariants over EVERY combination ----------------------------
# These are the promises the project makes. If a future rule change breaks one,
# the build fails.

DOMAIN_SETS = [[], ["operational"], ["relationship"], ["financial"], ["compliance", "safety"]]

ALL_COMBOS = list(itertools.product(
    InputType, RuleClarity, Reversibility, Level, Level, Level, [False, True], DOMAIN_SETS,
))


def _all_decisions(config):
    for it, rc, rev, cons, vol, exc, auto, domains in ALL_COMBOS:
        step = make_step(input_type=it, rule_clarity=rc, reversibility=rev,
                         consequence=cons, volume=vol, exception_rate=exc,
                         already_automated=auto, domains=domains)
        yield step, assign_lane(step, config)


def test_ai_alone_only_for_low_risk_reversible_unstructured(config):
    for step, d in _all_decisions(config):
        if d.lane == Lane.AI:
            assert step.input_type == InputType.UNSTRUCTURED
            assert step.consequence == Level.LOW
            assert step.reversibility == Reversibility.REVERSIBLE


def test_high_stakes_never_touches_ai(config):
    stakes = set(config["high_stakes_domains"])
    for step, d in _all_decisions(config):
        if step.consequence == Level.HIGH and {x.value for x in step.domains} & stakes:
            assert d.lane not in (Lane.AI, Lane.AI_ASSIST), step


def test_irreversible_never_touches_ai(config):
    for step, d in _all_decisions(config):
        if step.reversibility == Reversibility.IRREVERSIBLE:
            assert d.lane not in (Lane.AI, Lane.AI_ASSIST), step


def test_irreversible_automation_is_always_gated(config):
    for step, d in _all_decisions(config):
        if d.lane == Lane.AUTOMATE and step.reversibility == Reversibility.IRREVERSIBLE:
            assert d.hard_gate


def test_structured_clear_rules_never_use_ai(config):
    for step, d in _all_decisions(config):
        if step.input_type == InputType.STRUCTURED and step.rule_clarity == RuleClarity.CLEAR:
            assert d.lane in (Lane.KEEP, Lane.AUTOMATE)
