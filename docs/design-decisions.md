# Design decisions

A running log of why ProcessLab works the way it does. Add to this as the project grows.

## 1. The rules engine comes before the LLM

Phase 1 has no language model at all. The engine had to be correct, tested, and explainable before anything probabilistic touched it. When LLM extraction arrives in Phase 2, its only job is to produce process JSON that passes the same schema. It never assigns lanes.

## 2. The schema is strict

`extra="forbid"` means unknown fields are rejected. This matters later: if an LLM invents a field like `confidence` or `ai_recommended`, validation fails instead of silently passing data the engine never considers. Dependency ids, self-references, and cycles are also validated, because a process graph that can't exist shouldn't be scored.

## 3. First match wins, in a fixed order

Rules are ordered so the safest conclusion is reached first:

- **R1 before everything:** if a step already works, the tool shouldn't propose rebuilding it. Recognizing existing automation is part of good process design.
- **R2 before R3:** a step with structured input and a clear rule is automated even when it's high-stakes. High stakes argue *for* deterministic automation, not against it, because a tested rule is more consistent than a person or a model. These steps become **hard gates**.
- **R3 before R4/R5:** anything irreversible or high-stakes without a clear rule goes to a human before AI is ever considered.

## 4. Hard gates

A hard gate is an automated step where AI is excluded by design, and every outcome should be logged. Example: releasing check-in details only when the agreement is signed AND ID is verified. It's a compliance rule with zero ambiguity, and the cost of getting it wrong is real.

## 5. Invariants are tested exhaustively

The step attribute space is small enough (14,580 combinations) to test every case. Instead of trusting that the rule order is right, the tests assert the promises directly: AI never acts alone on consequential or irreversible steps, and high-stakes steps never reach an AI lane.

## 6. Opportunity score is separate from lane

The lane says *how* a step should be handled. The opportunity score (0–100) says *how much* redesigning it is worth, based on volume, exception rate, and input messiness. A step can be HUMAN and still high-opportunity (e.g. refund disputes), which points to a better tool for the human, not AI.

## 7. Gates are checked for what feeds them

Excluding AI from a gate's decision is not enough if AI produced the gate's input. The report walks `depends_on` back from every hard gate and warns if an AI-alone step can reach it by any route that skips a step declaring `validates` for that AI step. Checks must be declared rather than assumed: an intermediate step that merely uses the data does not count.

The first run flagged two of the shipped examples. In deal desk, the terms summary read the raw captured request and so bypassed field validation. In invoice approval, the duplicate check read extracted fields in parallel with the 3-way match. Both now run after the validating step.

## Known limitations / next steps

- Step attributes are hand-assigned in Phase 1. Phase 2 will extract them from text, and the attribute assignment itself will need a human review step.
- Triage is rated low consequence because misroutes are caught downstream. A real deployment would add a deterministic safety-keyword override (gas, smoke, flood, lockout) that forces escalation regardless of AI classification.
- Rule R6b ("unclear rule, higher consequence → human") often flags a missing policy rather than a genuinely human task. The tool could suggest *writing the rule* as the redesign.
