"""Run the rules engine on a process file.

    python -m processlab.cli examples/guest_onboarding.json
    python -m processlab.cli examples/guest_onboarding.json --json
"""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from processlab.engine import analyze_process, load_config
from processlab.schema import Lane, Process

LANE_LABELS = {
    Lane.KEEP: "KEEP",
    Lane.AUTOMATE: "AUTOMATE",
    Lane.AI: "AI",
    Lane.AI_ASSIST: "AI + HUMAN",
    Lane.HUMAN: "HUMAN",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ProcessLab rules engine")
    parser.add_argument("process_file", type=Path)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON")
    args = parser.parse_args(argv)

    try:
        process = Process.model_validate_json(args.process_file.read_text(encoding="utf-8"))
    except ValidationError as e:
        print(f"Invalid process file:\n{e}", file=sys.stderr)
        return 1

    report = analyze_process(process, load_config(args.config))

    if args.json:
        print(json.dumps(report.model_dump(mode="json"), indent=2))
        return 0

    print(f"\n{report.process_name}\n{'=' * len(report.process_name)}\n")
    print(f"{'STEP':<36} {'LANE':<11} {'RULE':<5} {'OPP':>4}  GATE")
    print("-" * 66)
    for d in report.decisions:
        gate = "🔒" if d.hard_gate else ""
        print(f"{d.step_name[:35]:<36} {LANE_LABELS[d.lane]:<11} {d.rule_id:<5} {d.opportunity_score:>4}  {gate}")

    print("\nWhy:")
    for d in report.decisions:
        print(f"  • {d.step_name}")
        for r in d.reasons:
            print(f"      {r}")

    print("\nSummary")
    for lane, n in report.lane_counts.items():
        print(f"  {LANE_LABELS[lane]:<11} {n}")
    print(f"  Manual steps before redesign: {report.manual_steps_before}")
    print(f"  Steps still needing a human:  {report.manual_steps_after}")
    print(f"  Hard gates (AI excluded):     {', '.join(report.hard_gates) or 'none'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
