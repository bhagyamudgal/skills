# Phase 5 — Execute the chosen fate

Multi-line bodies always go through the frozen `--body-file` paths recorded by the caller. Recheck every payload digest and the current step's protected issue fields immediately before its write; do not regenerate approved content inside this recipe.

Use the already-rendered `Investigation and successors` section and successor evidence blocks frozen by the caller from `${CLAUDE_SKILL_DIR}/references/ticket-evidence.md`. The caller has already run `preflight-mutations`; keep every write inside that approved fate batch.

## Update in place

1. Post the frozen status comment containing the Phase 3 table, recommendation, required investigation section, and `Audited against <sha> on <date>` via `gh issue comment "$issue_number" --repo "$repository" --body-file "$status_comment_path"`.
2. Use the frozen edited body that preserves the author's original intent/context paragraphs, then a task list — `- [x]` for done items, `- [ ]` with a one-line status for partial/not-done, `- [x] ~<text>~ (obsolete: <reason>)` for obsolete. Its footer is `_Audited <date> against <sha>._`
3. Apply that body via `gh issue edit "$issue_number" --repo "$repository" --body-file "$edited_body_path"`.
4. Run the rendered closeout gate from the evidence reference against the edited issue.

## Sunset (close)

1. Post the frozen reasoning comment with the table, required investigation section, and why this ticket no longer needs to exist via `gh issue comment "$issue_number" --repo "$repository" --body-file "$reasoning_comment_path"`.
2. Run the rendered closeout gate from the evidence reference.
3. `gh issue close "$issue_number" --repo "$repository" --reason completed` when the work shipped, `--reason "not planned"` when it's obsolete.

## Split remainder

1. Create the follow-up from the frozen title, body, assignee, and predecessor link after the caller's duplicate searches remain current: `gh issue create --repo "$repository" --title "$successor_title" --body-file "$successor_body_path" --assignee @me`. Apply `file-issue`'s authoritative create read-back and `reconcile-required` contract; do not retry an ambiguous create.
2. Comment on the original with the frozen complete investigation section, successor link, and what moved via `gh issue comment "$issue_number" --repo "$repository" --body-file "$split_comment_path"`.
3. Run the rendered closeout gate from the evidence reference against the original and successor, including their images.
4. Close the original via `gh issue close "$issue_number" --repo "$repository" --reason completed` only after that gate passes.

## Leave unchanged

Print `Report kept local — #<n> untouched.` and exit.

---

After any write, re-fetch the affected record as required by `preflight-mutations`, compare the landed payload and expected metadata, and advance the next step's guard only from that verified result. An expected `updatedAt` change caused by the landed write is part of the transition, not concurrent drift. At the end of a rewrite or split, run the evidence reference's full-set closeout before printing the affected URLs.

If any write fails or has an ambiguous result mid-execute, report exactly which steps authoritatively landed and mark unresolved attempts `reconcile-required` so the user is not left with a half-updated ticket or a duplicate retry.
