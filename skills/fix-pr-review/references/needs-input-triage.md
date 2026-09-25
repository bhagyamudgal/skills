# Settle NEEDS-INPUT

### 1. Settle NEEDS-INPUT

Keep the run-level stash untouched throughout this step. Initialize `needs_input_status[idx]=pending` for each `needs_input_items` entry. For any entry lacking `gh_status`, initialize paired `not-applicable` states when `has_github_surface=false`; otherwise initialize paired `skipped` states with `NEEDS-INPUT not yet authorized`. If the count is nonzero, use AskUserQuestion:

   Question:
     header: "NEEDS-INPUT"
     text: "<N> item(s) need your input. Would you like to triage them now?"
     options:
       - label: "Triage now"
         description: "Walk through each NEEDS-INPUT item and decide: fix, defer, or dismiss"
       - label: "Skip for now"
         description: "Leave them unresolved and handle them manually later"

On "Triage now", for each `needs_input_items` entry, use AskUserQuestion:

   Question:
     header: "Item N<idx>"
     text: "<file:line>: <why_unclear>"
     options:
       - label: "Fix it"
         description: "Provide guidance and have the agent apply a fix"
       - label: "Defer"
         description: "Mark as out-of-scope, post a DEFER reply on GitHub"
       - label: "Dismiss"
         description: "Not a real issue. Post a DISMISS reply on GitHub"

For every automatic `Other` freeform path in the batch prompt or an item prompt, honor an instruction that unambiguously maps named items to `Fix it`, `Defer`, `Dismiss`, or `Skip for now`. Preserve the exact freeform text with the item. If the mapping is ambiguous, set each affected item's `needs_input_status=skipped` and carry the text into its manual-handling reason. Do not leave it pending.

On "Fix it", use a follow-up AskUserQuestion to collect guidance:

   Question:
     header: "Guidance"
     text: "What should the fix do for <file:line>? Describe the intended behavior or approach."
     options:
       - label: "Use reviewer's suggestion"
         description: "Apply the original review comment's recommended change as-is"
       - label: "I'll describe"
         description: "Let me type specific guidance for this fix"

    On "Use reviewer's suggestion", use the original comment's recommendation as the fix plan. On "I'll describe" or "Other", treat unambiguous fix guidance as the fix plan. Honor an unambiguous defer, dismiss, or skip instruction through that action's branch. Preserve ambiguous text, set `needs_input_status=skipped`, and continue.

    Validate the complete FIX record through Phase 4 before editing. Record immutable `phase8_snapshot_fix_state[idx]` as the entry `fix_status` when it is `inverse_risk_applied` or `reverted_inverse_risk`; otherwise record `clear`. When the snapshot state is `inverse_risk_applied`, require the validated plan to record `phase8_remediation_kind[idx]=removal|replacement` and map every entry in the prior `perfix_owned_components[idx]` ledger exactly once to removal or replacement evidence. Reject an incomplete or duplicated map. Derive `phase8_item_files[idx]` from the union of every mapped owned-component path and every additional file declared by the validated plan, then capture each file's current content or authoritative absence in a dedicated `phase8_item_snapshot[idx]`. This snapshot includes all earlier landed fixes. Every later restore of this snapshot is state-preserving: restore the exact bytes, then restore `fix_status[idx]` from `phase8_snapshot_fix_state` when it is not `clear`, or use the branch's named fallback status when it is `clear`. Never change `phase8_snapshot_fix_state` without replacing the snapshot itself. Immediately after the snapshot and before any edit, run the affected Phase 5 narrow type-check against that state and parse `phase8_item_baseline_errors[idx]` with the Phase 1 diagnostic-identity multiset parser; when the applicable tooling is unavailable, record the baseline as unavailable and preserve the existing skipped-check behavior. Both item stores are append-only and separate from the run-level `preedit_snapshot` and `baseline_errors`: nested Phases 5-6 neither read nor overwrite the run-level stores. Set `phase8_triage_context=true` only after the snapshot, snapshot state, applicable remediation map, and item baseline are complete.

    In Phase 8 context, Phase 5 edits and retry agents may touch only `phase8_item_files[idx]`. When the plan expands, revalidate it and derive only the newly declared paths absent from `phase8_item_snapshot[idx]`; preserve every existing snapshot and baseline entry byte-for-byte. Before any new path is edited, append that path's current content or authoritative absence and its isolated per-path baseline, parsed with the Phase 1 diagnostic-identity multiset parser, to the item stores. Never recapture an existing path or rerun its baseline after an edit. If earlier item edits make a trustworthy per-path baseline for a new path impossible, fail closed: restore every path already present in the append-only item snapshot through the state-preserving restore rule with fallback `restored_failed`, leave the new path unedited, set `needs_input_status[idx]=failed` and `convergence[idx]=not-run, unsafe expansion baseline for <new-path>; snapshotted paths restored and new path left unedited`, then set paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix, unsafe expansion baseline` otherwise. Clear `phase8_triage_context` and continue with the next independent item. Phase 5.5 may verify all sites but may apply a corrective edit only within declared, snapshotted files.

    Apply the Phase 5 per-fix loop. When it returns a settled `skipped` or `aborted` item, preserve its `fix_status`, `needs_input_status`, `convergence`, and `gh_status`, then rejoin Phase 8 immediately; Phase 5.5 and Phase 6 are barred from running or reapplying it. Otherwise run Phase 5.5 for that fix. After a successful active-snapshot restore yields `reverted_inverse_risk`, preserve that status without another restore, set `needs_input_status[idx]=failed`, set paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix, inverse-risk fix reverted` otherwise, clear `phase8_triage_context`, and rejoin Phase 8. For any other status outside `landed_fix_statuses`, record it as `pre_restore_fix_status[idx]`, restore every declared path from `phase8_item_snapshot[idx]` through the state-preserving restore rule with fallback `restored_failed`, set `needs_input_status[idx]=failed`, and preserve the original convergence evidence with an appended `restored item snapshot after <pre_restore_fix_status>` disposition. Set paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix, convergence rejected and item restored` otherwise. Clear `phase8_triage_context` and rejoin Phase 8 at the next independent item. Only a status in `landed_fix_statuses` proceeds to the affected Phase 6 type-check, review, and simplify assessments in verification-only mode; do not apply type-fix, self-heal, or simplify edits.

    A Critical or Serious blocker, validation abort, edit failure, exhausted retry, or Phase 6 failure aborts only this item. Before restoring, record the exact triggering error or blocker as `phase8_failure_reason[idx]`. Restore every declared path from `phase8_item_snapshot[idx]`, including removing a path whose snapshot recorded authoritative absence, through the state-preserving restore rule with fallback `restored_failed`; set `needs_input_status[idx]=failed`. Preserve existing convergence evidence and append `restored item snapshot after <phase8_failure_reason>`; when convergence never ran, set `convergence[idx]=not-run, <phase8_failure_reason>; item snapshot restored`. Set paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix, <phase8_failure_reason>; item restored` otherwise. Clear the context and continue with the next independent item without restoring the run-level stash, exiting the skill, or bypassing the renderer. Ordinary Phase 5 and Phase 6 behavior remains unchanged when `phase8_triage_context` is false.

    When the fix and verification land cleanly, record current content risk as clear without changing the immutable snapshot state, then update `done_verified_snapshot` from the prior snapshot plus this item's verified declared-path bytes. If `phase8_snapshot_fix_state[idx]=inverse_risk_applied` and `phase8_remediation_kind[idx]=removal`, set `fix_status[idx]=reverted_inverse_risk`, set `needs_input_status[idx]=failed`, set paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `original finding not accepted, risky fix removed` otherwise, clear `phase8_triage_context`, and rejoin Phase 8 without GitHub reply or resolution. A verified replacement retains its applicable landed status and may proceed to the Phase 7 reply/resolve mechanics. Set `needs_input_status=fixed` only when `fix_status ∈ landed_fix_statuses` and both GitHub operations are successful or not applicable; set it to `reconcile-required` if either operation has that state, otherwise set it to `failed`. Preserve the final classification, `fix_status`, convergence, current-content risk, and `gh_status` before continuing.

Immediately before any chosen Fix, Defer, or Dismiss reply mutates GitHub, invoke `preflight-mutations` for that item's reply/resolve batch with the exact PR and current head SHA, target thread ID, final reply text, classification, and the per-item choice above. Name the target thread as the batch's durable home, with the per-item choice as its authorization: thread ID plus expected reply/resolve states, re-readable through the API after every write. Apply its result contract before continuing. Record a blocked or confirmed failure as `needs_input_status=failed`, an indeterminate operation as `reconcile-required`, and the exact Phase 7 `gh_status`; then continue to the next independent item. Every branch rejoins report rendering.

On "Defer": set the classification to `DEFER` and run the Phase 7 reply/resolve mechanics. On "Dismiss": do the same with classification `DISMISS`. When `has_github_surface=false`, set both GitHub states to `not-applicable` without entering any GitHub report section. Map the final result for either branch: both required operations successful or not applicable → `needs_input_status` "deferred" or "dismissed"; either operation `reconcile-required` → `reconcile-required`; every other non-success or confirmed failure → `failed`. Preserve every authoritative outcome in `gh_status`, then continue.

On "Skip for now": mark each untouched entry `needs_input_status=skipped` and preserve its current classification, `gh_status`, and any freeform guidance for later handling.

Treat `inverse_risk_applied` as a content-state blocker, not a triage disposition. Fix, Skip, Defer, Dismiss, or freeform reclassification preserves that status and its publication block until the risky owned components are removed or replaced, Phase 5.5 and Phase 6 pass on the resulting content, and `done_verified_snapshot` is rebuilt. A verified removal may set `reverted_inverse_risk`; a verified replacement may set an applicable landed status.

Skip the questions if the NEEDS-INPUT count is 0. Before leaving this step, every `needs_input_items` entry needs a non-pending status. Convert an unexpected remaining `pending` entry to `skipped`. Preserve its recorded choice and guidance as the manual-handling reason.
