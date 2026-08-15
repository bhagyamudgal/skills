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

Read `${CLAUDE_SKILL_DIR}/references/ticket-evidence.md` in full before extracting requirements. Build its source map alongside the requirement list so later rewrites and splits retain the original evidence.

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

For each, record: `id`, `text` (short quote), its supporting `E<n>` IDs from the source map, and `superseded_by` if a later comment amended it. Merge duplicates; a requirement restated in three comments is still one `Rn`, but retain each relevant source item under its own evidence ID.

If zero requirements are extractable (ticket is a vague one-liner), ask the user what specifically to verify before dispatching anything.

### Anchor the audit

Run `git rev-parse HEAD` and `git rev-parse HEAD^{tree}` and record the full commit and tree IDs. Audit the committed tree: every code search, file read, and line citation must use snapshot-aware Git commands such as `git grep <pattern> <tree-id>` and `git show <tree-id>:<path>`, or an isolated checkout of that exact tree. Leave staged, unstaged, and untracked user content untouched and outside the audit; name it as unexamined rather than hashing it into the repository object database.

Every verdict in the report is "as of `<full HEAD SHA>` at committed tree `<tree ID>`", so later commits and unrelated local work cannot silently change its evidence.

---

## Phase 2: Investigate (parallel subagents)

Dispatch **ONE `general-purpose` subagent PER requirement**, in parallel batches of 3-4. Main context is the orchestrator — it never greps for a verdict itself, which also keeps the verdicts independent. Share a subagent only when two requirements are the same edit to the same file (e.g., "add the column" + "expose it in the API response").

### Subagent prompt

```
You are verifying ONE requirement from a stale GitHub issue against one
frozen code snapshot. The ticket is old — code may have shipped, changed,
or made the requirement meaningless since it was written. Your job is a
verdict grounded in file:line evidence, not a guess.

## Ticket context
Issue: #<n> — <title> (opened <createdAt>)
Goal (1 sentence): <from body>
HEAD: <full Phase 1 SHA>
Content snapshot: <verified_content_snapshot tree hash>

## Requirement to verify
<Rn>: <requirement text>
Source: <body | comment | image>
<superseded_by note, if any>

## Your task
1. Search only the recorded content snapshot with snapshot-aware Git
   commands (`git grep <pattern> <tree>` and `git ls-tree -r <tree>`).
   Search by behavior keywords, not just the exact names the ticket uses.
2. Read matches with `git show <tree>:<path>` and derive line numbers from
   those bytes. Decide whether the requirement is implemented,
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

Verify each returned `file:line` exists in the recorded content snapshot before printing by reading the cited range from `git show <verified_content_snapshot>:<path>` — drop fabricated citations and downgrade that verdict's confidence to `low`.

Every `Rn` from Phase 1 appears exactly once in the table; N equals d + p + nd + o + u. A requirement with no returned verdict is `unverified`, not omitted. Put only evidence IDs in table cells, then render every complete `Rn → E<n>` edge in a block-form source map; code citations remain separate verdict evidence.

Then print:

```
# Ticket Audit: <title> (#<n>)

**State**: <open|closed> · opened <date> · last activity <date>
**Audited against**: <full HEAD SHA> at content snapshot <tree hash> on <today>
**Requirements**: <N> — <d> done / <p> partial / <nd> not done / <o> obsolete / <u> unverified
**Recommendation**: <one sentence — grounded in the verdict mix>

| # | Requirement | Source evidence | Verdict | Code evidence |
|---|-------------|-----------------|---------|---------------|
| R1 | <short text> | R1 → E1 | ✅ done | `<file:line>` |
| R2 | <short text> | R2 → E2, E4 | 🟡 partial | `<file:line>` — <gap, short> |
| R3 | <short text> | R3 → E3 | ❌ not done | — |
| R4 | <short text> | R4 → E5 | 🪦 obsolete | <reason, short> |

## Source evidence map

### R1 → E1
**Source**: <author> · <date> · <direct URL>

    <complete exact excerpt; indent every original line so multiline text and pipes remain intact>

<repeat one block for every Rn → E<n> edge>

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

For any rewrite or split, reread `${CLAUDE_SKILL_DIR}/references/ticket-evidence.md` before composing issue bodies and again for its rendered closeout gate. The chosen fate cannot close while required source evidence is missing.

Immediately before composing or freezing Phase 5 payloads, rerun `git rev-parse HEAD` and `git rev-parse HEAD^{tree}`, then compare both exact values with the Phase 1 commit and tree IDs. Leave the user's index and working tree untouched. When either value changed, identify every requirement whose code evidence or verdict the new committed bytes could affect, rerun those requirements through Phase 2 against the new tree, rebuild the Phase 3 report with both new identifiers, and return to Phase 4 for fresh approval. Rerun every requirement when the affected scope cannot be bounded.

Then re-fetch the full issue body and comments and re-download every retained attachment. Compare `updatedAt`, body, comment IDs and content, attachment URLs, and attachment digests with Phase 1. When any source changed or currency cannot be established, rebuild the source map, retain matching evidence IDs, append IDs for new evidence, and rerun every affected requirement through Phases 2 and 3. Stop when required evidence is unavailable. Apply both the code and source currency gates again before the split flow's post-create render. A changed audit commit or tree, requirement, verdict, recommendation, successor scope, or fate returns to Phase 4 for fresh approval.

Every frozen body or comment carries the `Rn → E<n>` mappings and block-form preserved excerpts for every requirement it mentions. Predecessor status, reasoning, edited-body, and split-comment payloads carry the complete map; a successor carries the map for its moved requirements.

For update-in-place or sunset, render every final body and comment before preflight. Present their exact frozen bytes and SHA-256 digests, current target guards, and ordered actions for fresh explicit approval. Bind approval to those values plus the source evidence, scope, verdicts, recommendation, and fate; any change invalidates it.

For a split, bind non-repeatable create state to an existing durable ledger that the user has already authorized for writes. Before create, write an attempt entry with an operation ID, frozen successor payload path and digest, predecessor guards, intended title and assignee, reconciliation status `planned`, and reserved stable successor ID, URL, and guard fields. If no authorized writable ledger exists, keep the proposed entry inline and stop before create; do not start the multi-card split.

First reconcile every `attempting`, `reconcile-required`, or `landed` entry. Render and preflight a create only from a `planned` entry with no prior non-repeatable attempt, after `file-issue`'s two-vocabulary duplicate search. Persist `attempting` immediately before `gh issue create`; an ambiguous result becomes `reconcile-required`, never a retry. Once authoritative read-back identifies the successor, fill its stable ID, URL, frozen payload digest, and guards, then mark the entry non-repeatable `landed` partial state. Every re-entry re-fetches and reuses that successor; it never targets create again.

For each mutation card, record every payload path and SHA-256 digest, exact title or command options, fresh target guards, and per-step expected guard transition. Pass the exact targets, audit commit and tree IDs, ordered actions, Phase 4 approval, and split metadata to `preflight-mutations` immediately before that card's first write. Before each later write, advance guards only from the prior write's authoritative read-back.

After the successor lands, apply the source-currency gate, then render and freeze the predecessor comment with the real successor URL. Obtain fresh explicit approval for its exact bytes and digest, the current predecessor and successor guards, and the ordered comment → close actions with the expected comment guard transition. After authoritative read-back proves the exact comment landed, advance to the returned expected guard and permit close without reapproval. Any unexpected transition or changed external guard, source evidence, payload byte, scope, verdict, recommendation, or fate invalidates approval. Reconcile the landed successor through an explicit retain, edit, or close plan and return to Phase 4 when semantics changed; never restart successor creation.

---

## Error handling

- **`gh` not installed/authed** → fail fast: `Run 'gh auth login' and retry.`
- **Issue not found / no access** → `Couldn't access issue #<n>. Check the number and repo access.`
- **Issue already closed** → still audit (the user may want to verify the close or reopen), note `State: closed` prominently in the report; on "Update in place", ask whether to also reopen.
