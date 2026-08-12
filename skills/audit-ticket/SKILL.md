---
name: audit-ticket
description: Audit a stale GitHub issue against the current codebase, then update or sunset it. Use when the user says "audit this ticket", or asks whether an old issue is still needed or should be sunset.
---

# /audit-ticket — Audit a Stale Issue Against Current Code

Takes a GitHub issue that was written weeks or months ago and checks every requirement in it against the codebase AS IT IS TODAY. Old tickets rot: half the items ship in unrelated PRs, some become obsolete after a refactor, and the rest silently block planning because nobody trusts the ticket anymore. This skill produces a per-item verdict with evidence, then lets the user decide the ticket's fate.

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
curl -fsSL -H "Authorization: token $(gh auth token)" -o /tmp/audit-ticket-<n>-img<i>.png "<url>"
```

`-f` is load-bearing: without it a 404 exits 0 and writes the error body into the `.png`, and you Read a non-image believing it is the spec. Check the exit code before the Read.

Screenshots and mockups often ARE the spec — a UI mock in the body can carry requirements no text mentions. Fold what the images show into the requirement list below. If the download exits non-zero, note `image <i> unavailable` in the report instead of pretending it didn't exist.

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

Dispatch **ONE `general-purpose` subagent PER requirement**, in parallel batches of 3-4. Main context is the orchestrator — it never greps for a verdict itself, which also keeps the verdicts independent. Share a subagent only when two requirements are the same edit to the same file (e.g., "add the column" + "expose it in the API response").

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
  confidence: low and explain what you'd need.
```

### Degraded-mode rule

A failed or empty subagent doesn't stop the audit — mark that requirement `unverified` in the report and continue. Abort only if ALL subagents fail.

---

## Phase 3: Report (main)

Verify each returned `file:line` exists before printing (quick `Read` of the cited range) — drop fabricated citations and downgrade that verdict's confidence to `low`.

Every `Rn` from Phase 1 appears exactly once in the table; N equals d + p + nd + o + u. A requirement with no returned verdict is `unverified`, not omitted.

Then print:

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

Phase 5 runs on the Phase 4 fate choice, and only on it — the report is always safe to print, but every `gh` write waits for that explicit choice. Read `${CLAUDE_SKILL_DIR}/references/execute.md` for the chosen fate's recipe.

Immediately before that recipe's first `gh` write, invoke `preflight-mutations` for the approved fate batch. Pass the exact issue URL and number; its current state, author, assignees, and audit SHA; the ordered comment/edit/close/create actions and their targets; the Phase 4 approval; and, for a split, the proposed successor title, body, assignee, and predecessor link. Apply its result contract before continuing.

---

## Error handling

- **`gh` not installed/authed** → fail fast: `Run 'gh auth login' and retry.`
- **Issue not found / no access** → `Couldn't access issue #<n>. Check the number and repo access.`
- **Issue already closed** → still audit (the user may want to verify the close or reopen), note `State: closed` prominently in the report; on "Update in place", ask whether to also reopen.
