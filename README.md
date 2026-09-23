# ProcessLab

**An AI that knows when *not* to use AI.**

ProcessLab takes a business process and decides, step by step, where AI belongs and where it doesn't. Each step lands in one of five lanes, and every placement comes with a reason you can audit.

| Lane | Meaning |
|---|---|
| ✅ KEEP | Already automated. Don't re-solve it. |
| ⚙️ AUTOMATE | Structured input + clear rule. Deterministic automation, no AI. |
| 🤖 AI | Messy input, low stakes, reversible. AI acts alone. |
| 🤖👤 AI + HUMAN | Messy input with real stakes. AI drafts, a human approves. |
| 👤 HUMAN | Irreversible or high-stakes judgment. |

## The core design choice

The LLM interprets. The rules engine decides.

A language model is good at reading messy input. It should not be the thing that decides whether a guest receives door codes. That decision is a rule, and rules don't need a language model. ProcessLab keeps lane assignment in plain, tested Python so every decision is repeatable and explainable.

## Status

- [x] **Phase 1:** Rules engine, schema, guest-onboarding case study, tests
- [ ] Phase 2: LLM extraction (plain-language description → validated process JSON)
- [ ] Phase 3: Redesign view + before/after Mermaid diagrams
- [ ] Phase 4: Simulation with sample cases + audit log
- [ ] Phase 5: Streamlit UI + public deploy

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m processlab.cli examples/guest_onboarding.json
pytest
```

## Case study: vacation rental guest onboarding

Based on a real short-term rental operation I've supported for 3+ years.

```
STEP                                 LANE        RULE   OPP  GATE
------------------------------------------------------------------
Record booking in PMS                AUTOMATE    R2      62
Send renter agreement                KEEP        R1       0
Remind guest to sign agreement       KEEP        R1       0
Request guest ID verification        KEEP        R1       0
Follow up on failed ID verification  AI + HUMAN  R5      75
Approve release of check-in details  AUTOMATE    R2      62  🔒
Send check-in info 1 day before      KEEP        R1       0
Triage inbound guest message         AI          R4      88
Notify maintenance vendor            AUTOMATE    R2      50
Reply to guest about their issue     AI + HUMAN  R5      88
Apply discount or booking adjustmen  HUMAN       R6b     50
Handle refund or payment dispute     HUMAN       R3      75
```

8 manual steps before → 4 that still need a human after. One hard gate: check-in release is a compliance rule (agreement signed AND ID verified), so AI is excluded from it by design.

## The rules

Evaluated top to bottom; first match wins.

| Rule | Condition | Lane |
|---|---|---|
| R1 | Already automated | KEEP |
| R2 | Structured input + clear rule (🔒 hard gate if irreversible or high-stakes) | AUTOMATE |
| R3 | Irreversible, or high consequence in a financial / legal / safety / compliance domain | HUMAN |
| R4 | Unstructured + low consequence + reversible | AI |
| R5 | Unstructured, anything else | AI + HUMAN |
| R6a | Structured, unclear rule, low consequence | AI + HUMAN |
| R6b | Structured, unclear rule, higher consequence | HUMAN |

Thresholds and weights live in [`processlab/config/thresholds.yaml`](processlab/config/thresholds.yaml).

## Guardrails are tested, not promised

`tests/test_engine.py` runs every combination of step attributes (14,580 cases) and checks that:

- AI never acts alone on anything consequential or irreversible
- High-stakes decisions never reach an AI lane
- Irreversible automation is always a hard gate
- Anything with a clear rule on structured data never uses AI

If a future rule change breaks one of these, the build fails.

## Project structure

```
processlab/
├── processlab/
│   ├── schema.py          # Pydantic contracts (strict: unknown fields rejected)
│   ├── engine.py          # Deterministic lane assignment, no LLM
│   ├── cli.py             # Run the engine on a process file
│   └── config/thresholds.yaml
├── examples/guest_onboarding.json
├── tests/
└── docs/design-decisions.md
```

See [`docs/design-decisions.md`](docs/design-decisions.md) for the reasoning behind the rules.
