# Phase 5: Execute the chosen fate

Multi-line bodies always go through the frozen `--body-file` paths recorded by the caller. Recheck every payload digest and the current step's protected issue fields immediately before its write; approved content changes only through the caller's re-render and approval-currency gates.

Use the already-rendered `Investigation and successors` section and evidence maps frozen by the caller from `${CLAUDE_SKILL_DIR}/references/ticket-evidence.md`. The caller has already preflighted each non-split fate or the split create card; keep every write inside its current card.

## Update in place

1. Confirm fresh approval still matches the exact frozen comment and body bytes and digests, current guards, source evidence, scope, verdicts, recommendation, fate, and ordered comment → edit actions.
2. Post the frozen status comment containing the Phase 3 table, complete evidence map, recommendation, required investigation section, and `Audited against <sha> on <date>` via `gh issue comment "$issue_number" --repo "$repository" --body-file "$status_comment_path"`.
3. Use the frozen edited body that preserves the author's original intent/context paragraphs, then a task list: `- [x]` for done items, `- [ ]` with a one-line status for partial/not-done, `- [x] ~<text>~ (obsolete: <reason>)` for obsolete, followed by the complete evidence map. Its footer is `_Audited <date> against <sha>._`
4. Apply that body via `gh issue edit "$issue_number" --repo "$repository" --body-file "$edited_body_path"`.
5. Run the rendered closeout gate from the evidence reference against the edited issue.

## Sunset (close)

1. Confirm fresh approval still matches the exact frozen comment bytes and digest, current guards, source evidence, scope, verdicts, recommendation, fate, close reason, and ordered comment → close actions.
2. Post the frozen reasoning comment with the table, complete evidence map, required investigation section, and why this ticket no longer needs to exist via `gh issue comment "$issue_number" --repo "$repository" --body-file "$reasoning_comment_path"`.
3. Run the rendered closeout gate from the evidence reference.
4. `gh issue close "$issue_number" --repo "$repository" --reason completed` when the work shipped, `--reason "not planned"` when it's obsolete.

## Split remainder

1. Require an existing writable durable ledger authorized by the user. Write the planned attempt entry before create; when none is authorized, keep the entry inline and stop before any split write.
2. Reconcile every `attempting`, `reconcile-required`, or `landed` entry. Only a `planned` entry with no prior non-repeatable attempt may create: persist `attempting`, then create the follow-up from the frozen title, body, assignee, predecessor link, and moved-requirement evidence map via `gh issue create --repo "$repository" --title "$successor_title" --body-file "$successor_body_path" --assignee @me`. Apply `file-issue`'s authoritative read-back contract; record an ambiguous create as `reconcile-required` without retry.
3. Record one authoritatively identified successor's stable ID, URL, frozen payload path and digest, and guards as non-repeatable `landed` partial state. On every re-entry, re-fetch that successor and continue from this step; creation is no longer eligible.
4. Apply the caller's source-currency gate, then render and freeze the original issue's comment with the complete investigation, complete evidence map, real successor URL, and moved scope. Record its digest plus current predecessor and successor guards.
5. Present those exact comment bytes and digest, both targets' guards, and the ordered comment → close actions with the expected comment guard transition for fresh explicit approval. Any changed guard, source evidence, payload byte, scope, verdict, recommendation, or fate invalidates approval. When semantics changed, stop with an explicit retain, edit, or close plan for the landed successor and return to Phase 4.
6. Invoke `preflight-mutations` for the approved comment, then post via `gh issue comment "$issue_number" --repo "$repository" --body-file "$split_comment_path"` only on `ready`.
7. Authoritatively read back the predecessor and prove the exact comment payload landed. Advance the predecessor guard to that returned expected transition; an unexpected transition invalidates the remaining approval.
8. Run the rendered closeout gate from the evidence reference against the original and successor, including their images.
9. Invoke `preflight-mutations` for the approved close using the advanced predecessor guard and current successor guard. Close the original via `gh issue close "$issue_number" --repo "$repository" --reason completed` only on `ready`, without reapproval while every other approved value remains current.

## Leave unchanged

Print `Report kept local. #<n> untouched.` and exit.

---

After any write, re-fetch the affected record as required by `preflight-mutations`, compare the landed payload and expected metadata, and advance the next step's guard only from that verified result. An expected `updatedAt` change caused by the landed write is part of the transition, not concurrent drift. At the end of a rewrite or split, run the evidence reference's full-set closeout before printing the affected URLs.

If any write fails or has an ambiguous result mid-execute, report exactly which steps authoritatively landed and mark unresolved attempts `reconcile-required` so the user is not left with a half-updated ticket or a duplicate retry.
