# Per-fix loop

### Per-fix loop

For each FIX item in topological order:

1. Print `[<idx>/<total>] Fixing: <file:line>`.

   If `--interactive` flag is set, use AskUserQuestion before applying each fix:

   Question:
     header: "Fix <idx>"
     text: "[<idx>/<total>] <file:line>: <fix_plan summary, first 80 chars>"
     options:
       - label: "Apply fix"
         description: "Execute this fix and continue to the next"
       - label: "Skip"
         description: "Skip this fix and mark it NEEDS-INPUT in the final report"
       - label: "Skip remaining"
         description: "Stop here and skip all remaining fixes"

   On "Apply fix": continue with steps 2-7. In ordinary Phase 5, "Skip" marks `fix_status[idx] = skipped` and advances to the next fix; "Skip remaining" marks every remaining fix `skipped` and jumps to Phase 6. In Phase 8 context, "Skip" restores every declared path from `active_snapshot` through the state-preserving restore rule with fallback `skipped`, sets `needs_input_status[idx]=skipped` and `convergence[idx]=not-run, user skipped before edit`, then sets paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix, user skipped before edit` otherwise. Phase 8 "Skip remaining" performs that same restore and settlement for the current item; it marks each not-yet-run fix skipped unless its current status is `inverse_risk_applied`, which remains unchanged with its publication blocker. Earlier landed fixes remain untouched. Both choices clear `phase8_triage_context`, terminate the nested Phase 5 path immediately, bypass Phases 5.5-6, and rejoin Phase 8 at the next independent item. On "Other": treat as freeform instruction (e.g., "modify the fix plan for this item").

2. In ordinary context, first add any never-edited declared path to `preedit_snapshot`. Then capture every declared path in `perfix_snapshot[idx]` and bind it as `active_snapshot` before editing. In Phase 8 context, every declared path must already sit in `active_snapshot`. A missing entry violates the declared-path gate, so stop the item and use the Phase 8 expansion rule to append that new path and baseline before editing. Existing entries stay immutable.
3. Apply the change(s) via `Edit` tool.
4. **Narrow type-check (this file only)**:
   - Detect project type. With `turbo.json`, use turborepo mode. With `tsconfig.json` and no turbo file, use plain TS mode. With neither, skip the check.
   - Turborepo: run `bun turbo run check-types --filter=<package>` (or `pnpm turbo run check-types --filter=<package>` if the repo uses pnpm), targeting the workspace package containing the edited file. The `turbo run` form is what carries `--filter` through; `bun` alone drops unknown flags instead of forwarding them to the underlying script.
   - Plain TS: `bunx tsc --noEmit` or `npx tsc --noEmit`.
   - Without TS tooling, skip the check with a one-line note. `/done` in Phase 6 catches what the narrow check would have caught.
5. **Compare diagnostic-identity multisets.** Parse the current output with Phase 1's parser, then subtract `active_baseline_errors[path]` from the current multiset by identity and count. Ordinary Phase 5 uses the Phase 1 run baseline; a Phase 8 item uses the baseline captured immediately before that item's edits. Classifications:
   - **pass.** The current multiset for every edited file is empty.
   - **failed.** `current - baseline` is non-empty for any edited file; report those remaining identities as genuinely new errors.
   - **inconclusive, preexisting errors.** Current errors remain, but `current - baseline` is empty because every current identity and duplicate count is covered by the baseline. Continue.
6. On **pass** or **inconclusive**, mark `[<idx>] ✓ fixed` or `[<idx>] ~ inconclusive` and continue.
7. On **failed.**

   Print the error output trimmed to ~30 lines, then use AskUserQuestion:

   Question:
     header: "Type-check"
     text: "[<idx>] Fix applied but type-check has NEW errors vs baseline. <error count> new error(s) in <file>."
     options:
       - label: "Retry fix"
         description: "Revert and re-dispatch to a fresh subagent with error context (max 2 retries)"
       - label: "Skip this fix"
         description: "Revert this fix, mark as NEEDS-INPUT, continue with remaining fixes"
       - label: "<Abort all | Abort item>"
         description: "Ordinary: revert all run-level edits and exit | Phase 8: restore only this item"

   On "Retry fix": restore the fix's declared paths from `active_snapshot`, re-dispatch the fix plan to a fresh `general-purpose` subagent with the new-errors context, loop (max 2 retries; on 3rd failure, auto-treat as "Skip this fix"). Before each retry, check the failure against the symptom-patching rule: when the way forward is a null check, a retry wrapper, or a wider timeout proposed only to make the check pass, do not spend the retry. Stop and work the item through systematic-debugging instead, then re-enter. One detour per item; a second symptom-shaped failure takes the Skip path.
   In ordinary context, "Skip this fix" restores the current `perfix_snapshot[idx]`, marks `fix_status[idx]=skipped` and `[<idx>] NEEDS-INPUT`, skips its Phase 7 reply/resolve, and continues with the remaining fixes. In Phase 8 context, it restores every `phase8_item_files[idx]` path through the state-preserving restore rule with fallback `skipped`, sets `needs_input_status[idx]=skipped` and `convergence[idx]=not-run, user skipped after type-check failure`, then sets paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix, user skipped after type-check failure` otherwise. Clear `phase8_triage_context`, terminate before Phases 5.5-6, and rejoin Phase 8 at the next independent item.
   Present "Abort all" only in ordinary context and "Abort item" only in Phase 8 context. On "Abort all", restore every run-level path, restore the stash, and exit non-zero. On "Abort item", restore only `phase8_item_files[idx]` through the state-preserving restore rule with fallback `aborted`, set `needs_input_status[idx]=failed` and `convergence[idx]=not-run, user aborted after type-check failure`, then set paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix, user aborted after type-check failure` otherwise. Clear `phase8_triage_context`, terminate before Phases 5.5-6, and rejoin Phase 8 at the next independent item without touching the stash or earlier fixes.
