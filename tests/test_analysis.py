from processlab.analysis import fragility, upstream
from processlab.diagram import to_mermaid
from processlab.engine import analyze_process, load_config
from processlab.schema import Lane, Process


def _step(id, **kw):
    base = dict(
        id=id, name=id, actor="a", input_type="structured", rule_clarity="clear",
        reversibility="reversible", consequence="low", volume="low", exception_rate="low",
    )
    return {**base, **kw}


def _process(*steps):
    return Process.model_validate({"name": "p", "steps": list(steps)})


AI_STEP = dict(input_type="unstructured", rule_clarity="partial")
GATE = dict(reversibility="irreversible")


def test_upstream_is_transitive():
    p = _process(_step("a"), _step("b", depends_on=["a"]), _step("c", depends_on=["b"]))
    assert sorted(upstream(p, "c")) == ["a", "b"]


def test_gate_fed_by_ai_through_another_step_is_flagged():
    p = _process(_step("read", **AI_STEP), _step("mid", depends_on=["read"]), _step("release", depends_on=["mid"], **GATE))
    report = analyze_process(p)
    assert report.hard_gates == ["release"]
    assert len(report.warnings) == 1 and "read" in report.warnings[0]


def test_gate_fed_by_reviewed_ai_is_not_flagged():
    p = _process(_step("draft", consequence="medium", **AI_STEP), _step("release", depends_on=["draft"], **GATE))
    report = analyze_process(p)
    assert report.decisions[0].lane == Lane.AI_ASSIST
    assert report.warnings == []


def test_fragility_reports_lane_flips():
    p = _process(_step("triage", **AI_STEP))
    flips = fragility(p.steps[0], load_config())
    assert any(f.startswith("consequence: low -> medium") for f in flips)
    assert analyze_process(p).decisions[0].fragile_on == flips


def test_kept_steps_are_never_fragile():
    p = _process(_step("done", already_automated=True))
    assert analyze_process(p).decisions[0].fragile_on == []


def test_mermaid_has_every_step_and_edge():
    p = _process(_step("a"), _step("b", depends_on=["a"], **GATE))
    out = to_mermaid(p, analyze_process(p))
    assert out.startswith("flowchart TD") and "a --> b" in out and "🔒" in out


def test_validating_step_clears_the_gate():
    p = _process(
        _step("read", **AI_STEP),
        _step("check", depends_on=["read"], validates=["read"]),
        _step("release", depends_on=["check"], **GATE),
    )
    assert analyze_process(p).warnings == []


def test_route_that_skips_the_check_is_still_flagged():
    p = _process(
        _step("read", **AI_STEP),
        _step("check", depends_on=["read"], validates=["read"]),
        _step("side", depends_on=["read"]),
        _step("release", depends_on=["check", "side"], **GATE),
    )
    assert len(analyze_process(p).warnings) == 1


def test_ai_step_cannot_validate_ai_output():
    p = _process(
        _step("read", **AI_STEP),
        _step("check", depends_on=["read"], validates=["read"], **AI_STEP),
        _step("release", depends_on=["check"], **GATE),
    )
    assert len(analyze_process(p).warnings) == 1


def test_validates_must_name_a_known_step():
    import pytest
    with pytest.raises(ValueError, match="validates unknown"):
        _process(_step("a", validates=["nope"]))


def test_shipped_examples_have_no_gate_warnings():
    from pathlib import Path
    for f in sorted((Path(__file__).parent.parent / "examples").glob("*.json")):
        report = analyze_process(Process.model_validate_json(f.read_text(encoding="utf-8")))
        assert report.warnings == [], f.name
