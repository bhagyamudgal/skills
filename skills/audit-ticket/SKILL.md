---
name: audit-ticket
description: Audit a stale GitHub issue against the current codebase, then update or sunset it. Use when the user says "audit this ticket", or asks whether an old issue is still needed or should be sunset.
---

# /audit-ticket: audit a stale issue against current code

I take a GitHub issue written weeks or months ago and check every requirement in it against the codebase as it is today. Old tickets rot. Half the items ship in unrelated PRs, some turn obsolete after a refactor, and the rest silently block planning because nobody trusts the ticket anymore. I produce a per-item verdict with evidence, then the user decides the ticket fate. I would rather do this audit once, properly, than argue about the ticket for another quarter.

## Usage

```
/audit-ticket 123
/audit-ticket https://github.com/owner/repo/issues/123
/audit-ticket            # no arg → ask for the issue number or URL
```

When no issue is given, I ask for the number or URL. I never infer from the current branch, recent commits, or open issues. Auditing the wrong ticket wastes a full subagent fan-out.

When the URL points at a different repo than cwd, I pass `--repo <owner>/<repo>` to every `gh` call. When the issue repo differs from the code being audited, I stop and confirm which working tree to ground against.

---

## Phase 1: Intake (main)

I read `${CLAUDE_SKILL_DIR}/references/ticket-evidence.md` in full before extracting requirements. I build its source map alongside the requirement list so later rewrites and splits retain the original evidence.

### Fetch the full ticket

```bash
gh issue view <n> --comments --json number,title,body,state,author,createdAt,updatedAt,labels,assignees,comments,url
```

I fetch ALL comments, not just the body. Later comments routinely amend, narrow, or drop requirements from the original body. When a comment contradicts the body, the comment wins. It is newer.

### Download attached images

I extract attachment URLs from the body AND every comment.

- `https://github.com/user-attachments/assets/<id>`
- `https://user-images.githubusercontent.com/...`

For each, I download with auth, since private-repo attachments 404 without it, then Read the file to actually look at it.

```bash
curl -fsSL -H "Authorization: token $(gh auth token)" -o /tmp/audit-ticket-<n>-img<i>.png "<url>"
```

`-f` is load-bearing. Without it a 404 exits 0 and writes the error body into the `.png`, and I Read a non-image believing it is the spec. I check the exit code before the Read.

Screenshots and mockups often ARE the spec. A UI mock in the body can carry requirements no text mentions. I fold what the images show into the requirement list below. When the download exits non-zero, I note `image <i> unavailable` in the report instead of pretending it did not exist.

### Extract the requirement list

I walk body plus comments in chronological order and enumerate every discrete requirement or claim, numbered `R1..Rn`.

- Task-list items, meaning `- [ ]` and `- [x]`. I carry over their checked state as the ticket OWN claim, to be verified, not trusted.
- Imperative statements like "add X" or "fix Y" or "should Z" or "migrate to W".
- Acceptance criteria and follow-up asks buried in comments.
- Requirements implied by attached mocks and screenshots.

For each, I record `id`, `text` as a short quote, its supporting `E<n>` IDs from the source map, and `superseded_by` when a later comment amended it. I merge duplicates. A requirement restated in three comments is still one `Rn`, but I retain each relevant source item under its own evidence ID.

When zero requirements are extractable, for example the ticket is a vague one-liner, I ask the user what specifically to verify before dispatching anything.

### Anchor the audit

I run `git rev-parse HEAD` and `git rev-parse HEAD^{tree}` and record the full commit and tree IDs. I audit the committed tree. Every code search, file read, and line citation must use snapshot-aware Git commands such as `git grep <pattern> <tree-id>` and `git show <tree-id>:<path>`, or an isolated checkout of that exact tree. I leave staged, unstaged, and untracked user content untouched and outside the audit. I name it as unexamined rather than hashing it into the repository object database.

Every verdict in the report reads "as of `<full HEAD SHA>` at committed tree `<tree ID>`", so later commits and unrelated local work cannot silently change its evidence.

---

## Phase 2: Investigate (parallel subagents)

I dispatch one `general-purpose` subagent per requirement, in parallel batches of 3-4. The main context is the orchestrator. It never greps for a verdict itself, which also keeps the verdicts independent. I share a subagent only when two requirements are the same edit to the same file, for example "add the column" plus "expose it in the API response".

### Subagent prompt

```
You are verifying ONE requirement from a stale GitHub issue against one
frozen code snapshot. The ticket is old. Code may have shipped, changed,
or made the requirement meaningless since it was written. Your job is a
verdict grounded in file:line evidence, not a guess.

## Ticket context
Issue: #<n>, <title> (opened <createdAt>)
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
   partially implemented, absent, or no longer applicable, meaning the code it
   targeted was removed or rewritten, or a different approach shipped.

## Output format (exactly this)
verdict: done | partially-done | not-done | obsolete
confidence: high | medium | low
evidence:
  - <file:line>: <what this line shows, one clause>
  - ...
gaps: <REQUIRED for partially-done/not-done. What's still missing, specific>
obsolete_reason: <REQUIRED for obsolete. What changed and where (file:line)>

## Rules
- Every done/partially-done verdict MUST cite at least one file:line.
- "obsolete" needs evidence of the superseding change, not a hunch.
- If you genuinely cannot determine it, say verdict: not-done with
  confidence: low and explain what you'd need.
```

### Degraded-mode rule

A failed or empty subagent does not stop the audit. I mark that requirement `unverified` in the report and continue. I abort only when ALL subagents fail.

---

## Phase 3: Report (main)

I verify each returned `file:line` exists in the recorded content snapshot before printing, by reading the cited range from `git show <verified_content_snapshot>:<path>`. I drop fabricated citations and downgrade that verdict confidence to `low`.

Every `Rn` from Phase 1 appears exactly once in the table. N equals d + p + nd + o + u. A requirement with no returned verdict is `unverified`, not omitted. I put only evidence IDs in table cells, then render every complete `Rn → E<n>` edge in a block-form source map. Code citations remain separate verdict evidence.

The audit is read by whoever inherits this ticket, and Phase 5 may post it to GitHub unchanged. I write it with no em or en dashes. `unslop` carries the rest of the rules where it is installed.

Then I print this.

```
# Ticket audit: <title> (#<n>)

**State**: <open|closed> · opened <date> · last activity <date>
**Audited against**: <full HEAD SHA> at content snapshot <tree hash> on <today>
**Requirements**: <N> total, <d> done / <p> partial / <nd> not done / <o> obsolete / <u> unverified
**Recommendation**: <one sentence, grounded in the verdict mix>

| # | Requirement | Source evidence | Verdict | Code evidence |
|---|-------------|-----------------|---------|---------------|
| R1 | <short text> | E1 | ✅ done | `<file:line>` |
| R2 | <short text> | E2, E4 | 🟡 partial | `<file:line>`: <gap, short> |
| R3 | <short text> | E3 | ❌ not done | none |
| R4 | <short text> | E5 | 🪦 obsolete | <reason, short> |

## Source evidence map

### R1 → E1
**Source**: <author> · <date> · <direct URL>

    <complete exact excerpt; indent every original line so multiline text and pipes remain intact>

<repeat one block for every Rn → E<n> edge>

## Details
<per-item: full gaps, obsolete reasons, low-confidence notes, unavailable images>
```

My recommendation logic runs like this.

- **Everything done or obsolete** → I recommend sunset, closing as `completed` when mostly done or `not planned` when mostly obsolete.
- **Mix of done and open items** → I recommend update-in-place, a comment plus an edited body.
- **Nothing done, still valid** → I recommend update-in-place with a "still fully open, re-triaged <date>" note, or I leave unchanged when the ticket body is already accurate.

---

## Phase 4: Decide (AskUserQuestion)

```
header: "Ticket fate"
text: "Audit of #<n>: <d> done, <p> partial, <nd> not done, <o> obsolete. What should happen to it?"
options:
  - "Update in place (Recommended)": Post the audit as a status comment and edit the body into an accurate current checklist
  - "Sunset (close)": Post the audit reasoning as a comment and close as <completed | not planned>
  - "Split remainder": File a follow-up issue with only the open items (assigned to you), link it, close this one
  - "Leave unchanged": Keep the report local; ticket untouched
```

When every requirement is done or obsolete, I reorder. "Sunset (close)" goes first and takes the "(Recommended)" marker. Updating a body that has no remaining work is churn.

---

## Phase 5: Execute (gh)

Phase 5 runs on the Phase 4 fate choice, and only on it. The report is always safe to print, but every `gh` write waits for that explicit choice. I read `${CLAUDE_SKILL_DIR}/references/execute.md` for the chosen fate recipe.

For any rewrite or split, I reread `${CLAUDE_SKILL_DIR}/references/ticket-evidence.md` before composing issue bodies and again for its rendered closeout gate. The chosen fate cannot close while required source evidence is missing.

Immediately before composing or freezing Phase 5 payloads, I rerun `git rev-parse HEAD` and `git rev-parse HEAD^{tree}`, then compare both exact values with the Phase 1 commit and tree IDs. I leave the user index and working tree untouched. When either value changed, I identify every requirement whose code evidence or verdict the new committed bytes could affect, rerun those requirements through Phase 2 against the new tree, rebuild the Phase 3 report with both new identifiers, and return to Phase 4 for fresh approval. I rerun every requirement when the affected scope cannot be bounded.

Then I re-fetch the full issue body and comments and re-download every retained attachment. I compare `updatedAt`, body, comment IDs and content, attachment URLs, and attachment digests with Phase 1. When any source changed or currency cannot be established, I rebuild the source map, retain matching evidence IDs, append IDs for new evidence, and rerun every affected requirement through Phases 2 and 3. I stop when required evidence is unavailable. I apply both the code and source currency gates again before the split flow post-create render. A changed audit commit or tree, requirement, verdict, recommendation, successor scope, or fate returns to Phase 4 for fresh approval.

Every frozen body or comment carries the `Rn → E<n>` mappings and block-form preserved excerpts for every requirement it mentions. Predecessor status, reasoning, edited-body, and split-comment payloads carry the complete map. A successor carries the map for its moved requirements.

For update-in-place or sunset, I render every final body and comment before preflight. I present their exact frozen bytes and SHA-256 digests, current target guards, and ordered actions for fresh explicit approval. I bind approval to those values plus the source evidence, scope, verdicts, recommendation, and fate. Any change invalidates it.

For a split, I bind non-repeatable create state to an existing durable ledger that the user has already authorized for writes. Before create, I write an attempt entry with an operation ID, frozen successor payload path and digest, predecessor guards, intended title and assignee, reconciliation status `planned`, and reserved stable successor ID, URL, and guard fields. When no authorized writable ledger exists, I keep the proposed entry inline and stop before create. I do not start the multi-card split.

First I reconcile every `attempting`, `reconcile-required`, or `landed` entry. I render and preflight a create only from a `planned` entry with no prior non-repeatable attempt, after `file-issue` two-vocabulary duplicate search. I persist `attempting` immediately before `gh issue create`. An ambiguous result becomes `reconcile-required`, never a retry. Once authoritative read-back identifies the successor, I fill its stable ID, URL, frozen payload digest, and guards, then mark the entry non-repeatable `landed` partial state. Every re-entry re-fetches and reuses that successor. It never targets create again.

For each mutation card, I record every payload path and SHA-256 digest, exact title or command options, fresh target guards, and per-step expected guard transition. I pass the exact targets, audit commit and tree IDs, ordered actions, Phase 4 approval, and split metadata to `preflight-mutations` immediately before that card first write. Before each later write, I advance guards only from the prior write authoritative read-back.

After the successor lands, I apply the source-currency gate, then render and freeze the predecessor comment with the real successor URL. I obtain fresh explicit approval for its exact bytes and digest, the current predecessor and successor guards, and the ordered comment to close actions with the expected comment guard transition. After authoritative read-back proves the exact comment landed, I advance to the returned expected guard and permit close without reapproval. Any unexpected transition or changed external guard, source evidence, payload byte, scope, verdict, recommendation, or fate invalidates approval. I reconcile the landed successor through an explicit retain, edit, or close plan and return to Phase 4 when semantics changed. I never restart successor creation.

---

## Error handling

- `gh` not installed. I fail fast with `Install gh CLI: https://cli.github.com` and stop.
- `gh` installed but not authed. I fail fast with `Run 'gh auth login' and retry.`
- Issue not found or no access. I report `Couldn't access issue #<n>. Check the number and repo access.`
- Issue already closed. I still audit, since the user may want to verify the close or reopen, and I note `State: closed` prominently in the report. On "Update in place", I ask whether to also reopen.
