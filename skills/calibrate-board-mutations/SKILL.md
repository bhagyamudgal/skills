---
name: calibrate-board-mutations
description: Calibrate and reconcile a batch of estimates on a shared project board. Use before estimating many board items, revising estimates after the unit or anchors change, or resuming a partially written estimate batch. Do not use for read-only analysis or a single write whose exact value the user already supplied.
---

# Calibrate Board Mutations

Prepare an evidence-backed estimate ledger, then delegate shared-state authorization to `preflight-mutations`. This skill reads and calculates; the workflow that owns the board performs the writes.

## 1. Fix the eligible scope

Resolve the board, estimate field, candidate item IDs, requester identity, and governing ownership policy from current board data. Include only items the policy permits. Treat unassigned, other-owned, and ambiguous items as read-only unless the user explicitly names and authorizes them.

Create one ledger in the existing authorized artifact that owns the batch:

```markdown
### Estimate calibration

- **Board / field:** <stable board ID and estimate field ID>
- **Eligible scope:** <owner rule and exact candidate IDs>
- **Unit / scale:** <agent-assisted hours, person-hours, points, allowed values, rounding>
- **Calibration source:** <applicable policy or 3–5 user-approved anchors>
- **Sample approval:** <approval source or pending>
- **Umbrella rule:** <classification and aggregation rule>

| Item ID | Owner | Kind | Current | Proposed | Basis | Status |
|---|---|---|---:|---:|---|---|
| <stable ID> | <owner> | leaf / umbrella | <value> | <value> | <evidence> | candidate / excluded / pending / landed / failed / skipped |
```

Record every candidate or its exclusion; totals may not silently drop items.

**Gate:** the board, field, owner boundary, and complete candidate set are exact.

## 2. Establish the calibration

Reuse a durable policy only when it defines all four facts:

1. estimate unit;
2. allowed scale and rounding;
3. representative anchors; and
4. applicability to this board and work type.

Otherwise ask the user for the unit and 3–5 anchors spanning the expected range. Record whether time means agent-assisted elapsed effort, person-hours, or another unit. Prepare no estimates until the calibration is complete.

**Gate:** another agent could apply the recorded calibration without inventing its unit or scale.

## 3. Build and preview a representative sample

Estimate 3–5 varied items before filling the batch. Cover the smallest, typical, and largest work; include an uncertainty edge and an umbrella when either exists. Ground each estimate in current ticket and implementation evidence.

Classify every umbrella exactly once:

- `direct` — estimate the umbrella itself and exclude its children from the same aggregate;
- `derived` — sum its eligible children and exclude the umbrella from the aggregate; or
- `excluded` — leave it outside the estimated scope with a reason.

Show the unit, anchors, sample estimates, reasoning, umbrella treatment, and sample total. Obtain the user's approval before converting ledger items from `candidate` to `pending`. A changed unit, anchor, sample decision, owner boundary, or umbrella rule invalidates all unexecuted estimates.

**Gate:** the user approved a representative sample and every umbrella has a non-duplicating treatment.

## 4. Prepare the exact batch

Fill the remaining eligible rows using the approved calibration. Calculate intended counts and totals mechanically from `pending` rows; keep excluded and umbrella-derived values out of the write total.

Invoke `preflight-mutations` with the exact board and field IDs, item IDs, current and proposed values, owner policy, sample approval, umbrella rule, invalidators, and authoritative read-back plan. Apply its result contract. The board-owning workflow may write only the exact batch that returns `ready` with matching guards.

**Gate:** every intended write is a `pending` ledger row covered by a current `ready` mutation card.

## 5. Reconcile authoritative results

After execution, re-fetch every attempted item from the board. Mark each row `landed`, `failed`, or `skipped` from observed final state, not command output. Preserve partial state and re-preflight only the remaining `pending` rows.

Report separately:

- attempted, landed, failed, skipped, excluded, and still-pending counts;
- the confirmed batch total calculated only from `landed` final values; and
- any wider scope total, with its exact inclusion rule.

If authoritative read-back is unavailable, report the intended values and missing verification; do not claim a confirmed total or completed batch.

**Done:** the approved calibration and complete ledger are preserved, every attempted item has authoritative final state or an explicit missing-read-back gap, and every reported total is reproducible from the ledger.
