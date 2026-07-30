# Phase 5 — Execute the chosen fate

Multi-line bodies always go through `--body-file` with a temp file.

## Update in place

1. Compose the status comment: the Phase 3 table + recommendation + `Audited against <sha> on <date>`. Post via `gh issue comment <n> --body-file <tmp>`.
2. Compose the edited body: preserve the author's original intent/context paragraphs, then a task list — `- [x]` for done items, `- [ ]` with a one-line status for partial/not-done, `- [x] ~<text>~ (obsolete: <reason>)` for obsolete. Footer: `_Audited <date> against <sha>._`
3. Apply via `gh issue edit <n> --body-file <tmp>`.

## Sunset (close)

1. Post the reasoning comment (table + why this ticket no longer needs to exist) via `--body-file`.
2. `gh issue close <n> --reason completed` when the work shipped, `--reason "not planned"` when it's obsolete.

## Split remainder

1. Create the follow-up: title `<original title> (remaining work)`, body = open items with their gaps + `Split from #<n> after audit (<sha>, <date>)`, via `gh issue create --title <t> --body-file <tmp> --assignee @me`.
2. Comment on the original linking the new issue and listing what moved.
3. Close the original with `--reason completed`.

## Leave unchanged

Print `Report kept local — #<n> untouched.` and exit.

---

After any write, print the affected URLs so the result is one click away.

If `gh issue edit` or `close` fails mid-execute, report exactly which steps landed (comment posted? body edited?) so the user isn't left with a half-updated ticket unknowingly.
