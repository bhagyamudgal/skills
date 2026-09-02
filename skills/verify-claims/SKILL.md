---
name: verify-claims
description: Verify an inference-backed, decision-driving claim before it drives a diagnosis, recommendation, external mutation, or user decision. Verify it again when it is challenged or materially reverses.
---

# Verify claims

A decision-driving claim changes what someone believes or does. I call a claim `verified` only with support from two distinct evidence surfaces, its basis and the boundary where the user will experience the claimed result. One surface is a hunch with a citation. I need both.

## 1. Start the claim card

I apply this workflow when a claim affects a diagnosis, recommendation, external mutation, completion verdict, or user decision and contains an inference. I exit the workflow for a directly observed fact or ordinary narration.

I start this card in the existing ledger, report, or durable issue artifact only when the user has already authorized writes to it. Otherwise I keep it inline.

```markdown
### Claim

- **Claim:** <falsifiable sentence>
- **Consequence:** <decision or action this controls>
- **Counter-hypothesis:** <strongest plausible alternative and distinguishing prediction>
- **Distinguishing observation:** <result, or concrete reason it is unavailable>
- **Basis evidence:** <observation, source, and what it establishes>
- **Boundary evidence:** <observation and acceptance surface, or missing evidence>
- **State:** hypothesis | basis-verified | verified | contradicted | blocked
- **Limitations:** <remaining uncertainty and any explicit reversible-work assumption>
- **Next action:** <action permitted by this state>
- **Independent recheck:** <reviewer verdict and evidence for a material reversal; otherwise not applicable>
```

**Gate.** The exact claim and its consequence are recorded, or the workflow has exited.

## 2. Frame competing predictions

I record the strongest plausible counter-hypothesis, not a token opposite. I name the observation that would distinguish it from the claim.

**Gate.** The claim and counter-hypothesis predict different observable results.

## 3. Gather paired evidence

I choose the lane matching the consequence. I inspect the current target. Prior summaries are leads, not evidence.

| Lane | Basis evidence | Acceptance-boundary evidence |
|---|---|---|
| Code behavior | Exact code path and relevant state or test setup | Runtime, test, browser, network, or persisted result at the public seam |
| External mutation | Exact write target, request, and mutation result ledger | Fresh read-back from the authoritative external system |
| Configuration or invocation | Parsed configuration, registration, and discovery result | Picker visibility, manual invocation, or actual consumer behavior |
| Data claim | Source lineage, query, filters, and intended dataset | Direct result from that dataset, including a recomputed count or total when claimed |

I use observations from distinct surfaces. I run the distinguishing observation from step 2 when its surface is available. I record commands, targets, timestamps, file locations, or result identifiers precisely enough for another agent to recheck them.

**Gate.** Each evidence field contains an observation or a concrete reason it is missing or inconclusive, and the distinguishing-observation field contains either its result or the concrete reason it was unavailable.

## 4. Assign exactly one state

- `hypothesis` means basis evidence is absent or inconclusive. I communicate only the hypothesis and the next evidence needed.
- `basis-verified` means the basis supports the claim, while boundary evidence or the distinguishing observation is missing or inconclusive. I label the conclusion provisional.
- `verified` means both evidence surfaces support the claim and a completed distinguishing observation does not support the counter-hypothesis. Definitive language is permitted.
- `contradicted` means a required observation falsifies the claim or supports the counter-hypothesis. I withdraw the claim.
- `blocked` means required evidence is unavailable and an external or irreversible action depends on the claim. I name the evidence needed to unblock it.

An unavailable boundary creates an evidence ceiling. The claim cannot reach `verified`. I continue reversible work only when its assumption is explicit in the card, and I hold external and irreversible actions.

**Gate.** The state follows from the recorded evidence, and the communicated conclusion and next action do not exceed it.

## 5. If the claim materially reverses, recheck independently

A reversal is material when new evidence changes the claim truth state, recommended action, or justification for an action already taken. With no material reversal, I record `not applicable` and continue.

For a material reversal, I dispatch a fresh reviewer who did not produce the original conclusion. I give it exact raw-source identifiers, the decision scope or query, and the counter-hypothesis. I do not pass a directory or any artifact containing a prior or proposed conclusion. I withhold the original rationale, prior conclusion, and proposed replacement value. I ask it to produce a claim card, then reconcile its evidence with the working card before relying on the replacement conclusion.

When no fresh reviewer is available, I set the replacement claim to `blocked` and name the missing recheck.

**Gate.** A non-reversal is recorded as not applicable. Otherwise the independent card is reconciled or reliance on the replacement conclusion is blocked.

## 6. Persist before reliance

I populate every card field. I persist the card in an already-authorized writable artifact before communicating or acting on the claim. Otherwise I communicate it inline without creating or updating external state.

**Done.** Every field is populated, the distinguishing result or concrete unavailability reason is present, and the communicated conclusion and next action match the recorded state. A claim without a completed distinguishing observation is never `verified`.
