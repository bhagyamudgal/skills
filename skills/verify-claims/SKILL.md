---
name: verify-claims
description: Verify an inference-backed, decision-driving claim before it drives a diagnosis, recommendation, external mutation, completion verdict, or user decision. Also use when such a claim is challenged or materially changes with new evidence.
---

# Verify Claims

A **decision-driving claim** changes what someone believes or does. A `verified` claim needs support from two distinct evidence surfaces: its basis and the boundary where the user will experience the claimed result.

## 1. Start the claim card

Apply this workflow when a claim affects a diagnosis, recommendation, external mutation, completion verdict, or user decision and contains an inference. Exit the workflow for a directly observed fact or ordinary narration.

Start this card in the existing ledger, report, or durable issue artifact only when the user has already authorized writes to it; otherwise keep it inline:

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

**Gate:** the exact claim and its consequence are recorded, or the workflow has exited.

## 2. Frame competing predictions

Record the strongest plausible counter-hypothesis, not a token opposite. Name the observation that would distinguish it from the claim.

**Gate:** the claim and counter-hypothesis predict different observable results.

## 3. Gather paired evidence

Choose the lane matching the consequence. Inspect the current target; prior summaries are leads, not evidence.

| Lane | Basis evidence | Acceptance-boundary evidence |
|---|---|---|
| Code behavior | Exact code path and relevant state or test setup | Runtime, test, browser, network, or persisted result at the public seam |
| External mutation | Exact write target, request, and mutation result ledger | Fresh read-back from the authoritative external system |
| Configuration or invocation | Parsed configuration, registration, and discovery result | Picker visibility, manual invocation, or actual consumer behavior |
| Data claim | Source lineage, query, filters, and intended dataset | Direct result from that dataset, including a recomputed count or total when claimed |

Use observations from distinct surfaces. Run the distinguishing observation from step 2 when its surface is available. Record commands, targets, timestamps, file locations, or result identifiers precisely enough for another agent to recheck them.

**Gate:** each evidence field contains an observation or a concrete reason it is missing or inconclusive, and the distinguishing-observation field contains either its result or the concrete reason it was unavailable.

## 4. Assign exactly one state

- `hypothesis` — basis evidence is absent or inconclusive. Communicate only the hypothesis and the next evidence needed.
- `basis-verified` — the basis supports the claim, while boundary evidence or the distinguishing observation is missing or inconclusive. Label the conclusion provisional.
- `verified` — both evidence surfaces support the claim and a completed distinguishing observation does not support the counter-hypothesis. Definitive language is permitted.
- `contradicted` — a required observation falsifies the claim or supports the counter-hypothesis. Withdraw the claim.
- `blocked` — required evidence is unavailable and an external or irreversible action depends on the claim. Name the evidence needed to unblock it.

An unavailable boundary creates an **evidence ceiling**: the claim cannot reach `verified`. Continue reversible work only when its assumption is explicit in the card; hold external and irreversible actions.

**Gate:** the state follows from the recorded evidence, and the communicated conclusion and next action do not exceed it.

## 5. If the claim materially reverses, recheck independently

A reversal is material when new evidence changes the claim's truth state, recommended action, or justification for an action already taken. With no material reversal, record `not applicable` and continue.

For a material reversal, dispatch a fresh reviewer who did not produce the original conclusion. Give it exact raw-source identifiers, the decision scope or query, and the counter-hypothesis; do not pass a directory or any artifact containing a prior or proposed conclusion. Withhold the original rationale, prior conclusion, and proposed replacement value. Ask it to produce a claim card, then reconcile its evidence with the working card before relying on the replacement conclusion.

When no fresh reviewer is available, set the replacement claim to `blocked` and name the missing recheck.

**Gate:** a non-reversal is recorded as not applicable; otherwise the independent card is reconciled or reliance on the replacement conclusion is blocked.

## 6. Persist before reliance

Populate every card field. Persist the card in an already-authorized writable artifact before communicating or acting on the claim; otherwise communicate it inline without creating or updating external state.

**Done:** every field is populated, the distinguishing result or concrete unavailability reason is present, and the communicated conclusion and next action match the recorded state. A claim without a completed distinguishing observation is never `verified`.
