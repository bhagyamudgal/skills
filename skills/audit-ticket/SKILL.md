---
name: audit-ticket
description: Audit a stale GitHub issue/ticket against the current codebase — what's done, what's left, is it still needed? Then update or sunset it. Use when user says "audit this ticket", "is this ticket still needed", "update this old ticket", "what's done and what's left on this issue", or "should we sunset this issue".
---

# /audit-ticket — Audit a Stale Issue Against Current Code

Takes a GitHub issue that was written weeks or months ago and checks every requirement in it against the codebase AS IT IS TODAY. Old tickets rot: half the items ship in unrelated PRs, some become obsolete after a refactor, and the rest silently block planning because nobody trusts the ticket anymore. This skill produces a per-item verdict with evidence, then lets the user decide the ticket's fate.

**Use AskUserQuestion for the ticket-fate decision** — cursor-selectable, options concrete, strongest first marked "(Recommended)". Never present the choice as a numbered prose list, and never touch the ticket without that explicit choice.

## Usage

```
/audit-ticket 123
/audit-ticket https://github.com/owner/repo/issues/123
/audit-ticket            # no arg → ask for the issue number or URL
```

If no issue is given, ask for the number or URL. Don't infer from the current branch, recent commits, or open issues — auditing the wrong ticket wastes a full subagent fan-out.

If the URL points at a different repo than cwd, pass `--repo <owner>/<repo>` to every `gh` call. If the ISSUE repo differs from the CODE being audited, stop and confirm which working tree to ground against.

---

## Phase 1: Intake (main)

### Fetch the full ticket

```bash
gh issue view <n> --comments --json number,title,body,state,author,createdAt,updatedAt,labels,assignees,comments,url
```

Fetch ALL comments, not just the body — later comments routinely amend, narrow, or drop requirements from the original body. When a comment contradicts the body, the comment wins (it's newer).

### Download attached images

Extract attachment URLs from the body AND every comment:

- `https://github.com/user-attachments/assets/<id>`
- `https://user-images.githubusercontent.com/...`

For each, download with auth (private-repo attachments 404 without it), then Read the file to actually look at it:

```bash
curl -sL -H "Authorization: token $(gh auth token)" -o /tmp/audit-ticket-<n>-img<i>.png "<url>"
```

Screenshots and mockups often ARE the spec — a UI mock in the body can carry requirements no text mentions. Fold what the images show into the requirement list below. If a download fails, note `image <i> unavailable` in the report instead of pretending it didn't exist.

### Extract the requirement list

Walk body + comments in chronological order and enumerate every discrete requirement or claim, numbered `R1..Rn`:

- Task-list items (`- [ ]` / `- [x]`) — carry over their checked state as the ticket's OWN claim, to be verified, not trusted
- Imperative statements ("add X", "fix Y", "should Z", "migrate to W")
- Acceptance criteria and follow-up asks buried in comments
- Requirements implied by attached mocks/screenshots

For each, record: `id`, `text` (short quote), `source` (body | comment by <author> on <date> | image <i>), and `superseded_by` if a later comment amended it. Merge duplicates; a requirement restated in three comments is still one `Rn`.

If zero requirements are extractable (ticket is a vague one-liner), ask the user what specifically to verify before dispatching anything.

### Anchor the audit

```bash
git rev-parse --short HEAD
```

Record the sha — every verdict in the report is "as of `<sha>`", so the audit stays meaningful after the next merge.

---

## Phase 2: Investigate (parallel subagents)

Dispatch **ONE `general-purpose` subagent PER requirement**, in parallel batches of 3-4. Main context is the orchestrator — it never greps the codebase for a verdict itself. Trivially-coupled requirements (e.g., "add the column" + "expose it in the API response") may share one subagent; unrelated ones never do.

### Subagent prompt

```
You are verifying ONE requirement from a stale GitHub issue against the
CURRENT codebase. The ticket is old — code may have shipped, changed, or
made the requirement meaningless since it was written. Your job is a
verdict grounded in file:line evidence, not a guess.

## Ticket context
Issue: #<n> — <title> (opened <createdAt>)
Goal (1 sentence): <from body>

## Requirement to verify
<Rn>: <requirement text>
Source: <body | comment | image>
<superseded_by note, if any>

## Your task
1. Search the codebase (Grep, Glob, Read) for the feature/change this
   requirement describes. Search by behavior keywords, not just the
   exact names the ticket uses — code written later rarely matches the
   ticket's vocabulary.
2. Read the matches. Decide whether the requirement is implemented,
   partially implemented, absent, or no longer applicable (the code it
   targeted was removed/rewritten, or a different approach shipped).

## Output format (exactly this)
verdict: done | partially-done | not-done | obsolete
confidence: high | medium | low
evidence:
  - <file:line> — <what this line shows, one clause>
  - ...
gaps: <REQUIRED for partially-done/not-done — what's still missing, specific>
obsolete_reason: <REQUIRED for obsolete — what changed and where (file:line)>

## Rules
- Every done/partially-done verdict MUST cite at least one file:line.
- "obsolete" needs evidence of the superseding change — not a hunch.
- If you genuinely cannot determine it, say verdict: not-done with
  confidence: low and explain what you'd need. Do NOT invent evidence.
```

### Degraded-mode rule

A failed or empty subagent doesn't stop the audit — mark that requirement `unverified` in the report and continue. Abort only if ALL subagents fail.

---

## Phase 3: Report (main)

Verify each returned `file:line` exists before printing (quick `Read` of the cited range) — drop fabricated citations and downgrade that verdict's confidence to `low`. Then print:

```
# Ticket Audit: <title> (#<n>)

**State**: <open|closed> · opened <date> · last activity <date>
**Audited against**: <sha> on <today>
**Requirements**: <N> — <d> done / <p> partial / <nd> not done / <o> obsolete / <u> unverified
**Recommendation**: <one sentence — grounded in the verdict mix>

| # | Requirement | Verdict | Evidence |
|---|-------------|---------|----------|
| R1 | <short text> | ✅ done | `<file:line>` |
| R2 | <short text> | 🟡 partial | `<file:line>` — <gap, short> |
| R3 | <short text> | ❌ not done | — |
| R4 | <short text> | 🪦 obsolete | <reason, short> |

## Details
<per-item: full gaps, obsolete reasons, low-confidence notes, unavailable images>
```

Recommendation logic:

- **Everything done or obsolete** → recommend sunset (close as `completed` if mostly done, `not planned` if mostly obsolete)
- **Mix of done and open items** → recommend update-in-place (comment + edited body)
- **Nothing done, still valid** → recommend update-in-place with a "still fully open, re-triaged <date>" note — or leave unchanged if the ticket body is already accurate

---

## Phase 4: Decide (AskUserQuestion)

```
header: "Ticket fate"
text: "Audit of #<n>: <d> done, <p> partial, <nd> not done, <o> obsolete. What should happen to it?"
options:
  - "Update in place (Recommended)" — Post the audit as a status comment and edit the body into an accurate current checklist
  - "Sunset (close)" — Post the audit reasoning as a comment and close as <completed | not planned>
  - "Split remainder" — File a follow-up issue with only the open items (assigned to you), link it, close this one
  - "Leave unchanged" — Keep the report local; ticket untouched
```

When every requirement is done or obsolete, reorder: "Sunset (close)" goes first and takes the "(Recommended)" marker — updating a body that has no remaining work is churn.

---

## Phase 5: Execute (gh)

Multi-line bodies always go through `--body-file` with a temp file — never heredoc, never inline `-b` with embedded quoting.

### Update in place

1. Compose the status comment: the Phase 3 table + recommendation + `Audited against <sha> on <date>`. Post via `gh issue comment <n> --body-file <tmp>`.
2. Compose the edited body: preserve the author's original intent/context paragraphs, then a task list — `- [x]` for done items, `- [ ]` with a one-line status for partial/not-done, `- [x] ~<text>~ (obsolete: <reason>)` for obsolete. Footer: `_Audited <date> against <sha>._`
3. Apply via `gh issue edit <n> --body-file <tmp>`.

### Sunset (close)

1. Post the reasoning comment (table + why this ticket no longer needs to exist) via `--body-file`.
2. `gh issue close <n> --reason completed` when the work shipped, `--reason "not planned"` when it's obsolete.

### Split remainder

1. Create the follow-up: title `<original title> (remaining work)`, body = open items with their gaps + `Split from #<n> after audit (<sha>, <date>)`, via `gh issue create --title <t> --body-file <tmp> --assignee @me`.
2. Comment on the original linking the new issue and listing what moved.
3. Close the original with `--reason completed`.

### Leave unchanged

Print `Report kept local — #<n> untouched.` and exit.

After any write, print the affected URLs (`gh` echoes them) so the result is one click away.

---

## Error handling

- **`gh` not installed/authed** → fail fast: `Run 'gh auth login' and retry.`
- **Issue not found / no access** → `Couldn't access issue #<n>. Check the number and repo access.`
- **Issue already closed** → still audit (the user may want to verify the close or reopen), note `State: closed` prominently in the report; on "Update in place", ask whether to also reopen.
- **No extractable requirements** → ask the user what to verify; don't dispatch blind subagents.
- **Image download fails** → note it in the report; never claim an image showed nothing when it couldn't be fetched.
- **Subagent failure** → mark `unverified`, continue; abort only if all fail.
- **`gh issue edit`/`close` fails mid-execute** → report exactly which steps landed (comment posted? body edited?) so the user isn't left with a half-updated ticket unknowingly.

## Rules

- **NEVER** close, edit, comment on, or create an issue without the explicit Phase 4 choice — the report itself is always safe; writes never are.
- **NEVER** trust the ticket's own checkboxes — a `- [x]` in a stale body is a claim to verify, not a verdict.
- **NEVER** emit a done/partial verdict without file:line evidence that survived the Phase 3 citation check.
- **NEVER** audit requirements inline in main context — one subagent per requirement keeps main free for orchestration and keeps verdicts independent.
- **NEVER** use heredoc for `gh` bodies — `--body-file` with a temp file, always.
- **ALWAYS** read the full comment thread — the last comment often rewrites the ticket.
- **ALWAYS** anchor the audit to a commit sha so "done" means something next month.
