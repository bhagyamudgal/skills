# Phase 5 — Execute the chosen fate

Multi-line bodies always go through `--body-file` with a temp file.

Render the original issue's `Investigation and successors` section and any successor evidence blocks from the source map in `${CLAUDE_SKILL_DIR}/references/ticket-evidence.md`. The caller has already run `preflight-mutations`; keep every write inside that approved fate batch.

## Update in place

1. Compose the status comment: the Phase 3 table, recommendation, required investigation section, and `Audited against <sha> on <date>`. Post via `gh issue comment <n> --body-file <tmp>`.
2. Compose the edited body: preserve the author's original intent/context paragraphs, then a task list — `- [x]` for done items, `- [ ]` with a one-line status for partial/not-done, `- [x] ~<text>~ (obsolete: <reason>)` for obsolete. Footer: `_Audited <date> against <sha>._`
3. Apply via `gh issue edit <n> --body-file <tmp>`.
4. Run the rendered closeout gate from the evidence reference against the edited issue.

## Sunset (close)

1. Post the reasoning comment with the table, required investigation section, and why this ticket no longer needs to exist via `--body-file`.
2. Run the rendered closeout gate from the evidence reference.
3. `gh issue close <n> --reason completed` when the work shipped, `--reason "not planned"` when it's obsolete.

## Split remainder

1. Create the follow-up: title `<original title> (remaining work)`, body = open items with their gaps plus the scoped evidence block and `Split from #<n> after audit (<sha>, <date>)`, via `gh issue create --title <t> --body-file <tmp> --assignee @me`.
2. Comment on the original with the complete investigation section, successor link, and what moved.
3. Run the rendered closeout gate from the evidence reference against the original and successor, including their images.
4. Close the original with `--reason completed` only after that gate passes.

## Leave unchanged

Print `Report kept local — #<n> untouched.` and exit.

---

After any write, re-fetch the affected record as required by `preflight-mutations`. At the end of a rewrite or split, run the evidence reference's full-set closeout before printing the affected URLs.

If `gh issue edit` or `close` fails mid-execute, report exactly which steps landed (comment posted? body edited?) so the user isn't left with a half-updated ticket unknowingly.
