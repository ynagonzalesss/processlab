"""Render a process report as a Mermaid flowchart (GitHub renders it natively)."""

from processlab.schema import Lane, Process, ProcessReport

_LABELS = {
    Lane.KEEP: "KEEP",
    Lane.AUTOMATE: "AUTOMATE",
    Lane.AI: "AI",
    Lane.AI_ASSIST: "AI + HUMAN",
    Lane.HUMAN: "HUMAN",
}
_STYLES = {
    Lane.KEEP: "fill:#e5e7eb,stroke:#6b7280,color:#111827",
    Lane.AUTOMATE: "fill:#dbeafe,stroke:#2563eb,color:#111827",
    Lane.AI: "fill:#ede9fe,stroke:#7c3aed,color:#111827",
    Lane.AI_ASSIST: "fill:#fef3c7,stroke:#d97706,color:#111827",
    Lane.HUMAN: "fill:#fee2e2,stroke:#dc2626,color:#111827",
}


def to_mermaid(process: Process, report: ProcessReport) -> str:
    by_id = {d.step_id: d for d in report.decisions}
    lines = ["flowchart TD"]
    for step in process.steps:
        d = by_id[step.id]
        name = step.name.replace('"', "'")
        gate = " 🔒" if d.hard_gate else ""
        lines.append(f'    {step.id}["{name}<br/><b>{_LABELS[d.lane]}{gate}</b>"]:::{d.lane.value}')
    for step in process.steps:
        for dep in step.depends_on:
            lines.append(f"    {dep} --> {step.id}")
    for lane, style in _STYLES.items():
        lines.append(f"    classDef {lane.value} {style}")
    return "\n".join(lines)
