"""The flagship demo must keep producing the redesign we present publicly."""

import pytest

from processlab.engine import analyze_process
from processlab.schema import Lane

EXPECTED = {
    "record_booking": Lane.AUTOMATE,
    "send_agreement": Lane.KEEP,
    "agreement_reminders": Lane.KEEP,
    "request_id_verification": Lane.KEEP,
    "review_failed_verification": Lane.AI_ASSIST,
    "release_checkin_gate": Lane.AUTOMATE,
    "send_checkin_info": Lane.KEEP,
    "triage_guest_message": Lane.AI,
    "dispatch_maintenance": Lane.AUTOMATE,
    "reply_to_guest": Lane.AI_ASSIST,
    "apply_booking_adjustment": Lane.HUMAN,
    "handle_refund_dispute": Lane.HUMAN,
}


@pytest.fixture(scope="module")
def report(guest_process, config):
    return analyze_process(guest_process, config)


@pytest.mark.parametrize("step_id,lane", EXPECTED.items())
def test_step_lane(report, step_id, lane):
    decision = next(d for d in report.decisions if d.step_id == step_id)
    assert decision.lane == lane


def test_checkin_release_is_the_only_hard_gate(report):
    assert report.hard_gates == ["release_checkin_gate"]


def test_checkin_release_never_uses_ai(report):
    d = next(d for d in report.decisions if d.step_id == "release_checkin_gate")
    assert d.lane not in (Lane.AI, Lane.AI_ASSIST)


def test_summary_counts(report):
    assert report.manual_steps_before == 8
    assert report.manual_steps_after == 4
    assert sum(report.lane_counts.values()) == len(EXPECTED)
