---
name: file-pr
description: Open a GitHub pull request whose title and body a reviewer understands in one read. Use when opening a PR or publishing ready-to-publish work for review — never open one by hand.
---

# File a Pull Request

A PR is read by someone who has not seen the session, the diff, or the ticket. Every bar below exists so that reader understands the change in one pass.

## 1. Check preconditions

Read the branch and the current `done` readiness card.

- **Branch** — `git rev-parse --abbrev-ref HEAD` exactly equals **Branch** in the card and satisfies the branch-naming rule in `CLAUDE.md`. A rename or switch makes the card stale and returns to `done`.
- **Readiness card** — require the current Git card defined by `done`, including its request, currency, coverage, lane, evidence, verdict, and next-action fields. Its verdict must be `ready-to-publish`, with this skill as the exact next action. A missing field or another verdict returns to `done`; do not reconstruct it here.

**Gate:** branch and card presence each have a recorded result, and a failed one stops the PR.

## 2. Validate the base and resolve the issue link

Use the PR base ref already resolved by `done`. Refresh that exact known `origin` ref with the commands recorded in the card, then require its ref name, remote base-tip SHA, and merge-base SHA to match. Another base state or choice returns to `done` because it changes the verified diff.

Choose exactly one issue link:

- The diff fully resolves the issue — `Closes #N`
- It resolves part of one, a sub-task of an umbrella ticket or one slice of an epic — `Refs #N`, plus one line naming which part it covers and what stays open
- It was found while investigating an issue but does not fix it — `Refs #N`, and say that in the body

Never `Closes` an issue this diff does not finish.

**Gate:** the base ref, remote base tip, and merge base match the refreshed remote state, and the issue link comes from issue output rather than assumption.

### Revalidate card currency and handoff eligibility

Recompute the card instead of trusting its label:

- the active request scope matches **Originating request**;
- the active branch exactly matches **Branch**;
- the refreshed base ref, tip, and merge base match **PR base ref**, **Remote base-tip commit**, and **Merge-base commit**;
- fresh authoritative read-back of every mixed external target matches its recorded target, version, and fields; and
- the card satisfies `done`'s `ready-to-publish` rule.

Immediately before scope validation, run `done`'s alternate-index construction through `git write-tree`. Before its cleanup, run the candidate diff:

```bash
GIT_INDEX_FILE="$snapshot_index" git diff --cached --no-ext-diff <merge-base> --
```

Require the snapshot to match **Verified content snapshot**. Account every changed hunk or logical change to one verified request row; anything outside those rows is the stop-and-ask case in `CLAUDE.md`. Then run `done`'s index cleanup.

Before committing, require `HEAD` to equal **Pre-verification head** and **Expected append-only commits** to be `none`. A changed request, base, head, or content snapshot makes the card stale. Return to `done` on any mismatch.

**Gate:** the recomputed request, branch, base ref and SHAs, head, snapshot, external currency, candidate diff, and `ready-to-publish` verdict all match the card.

## 3. Compose the title

Form: `<type>(<module>): <description>`. Name the module the way it reads on the board, not the way the directory spells it.

The description names what someone **observes** — what broke, or what is now possible. Not what you edited.

Banned as the whole description: `improve`, `update`, `handle`, `refactor`, `fix logic`, `clean up`, `various fixes`.

| Mechanism — rewrite | Outcome — ship |
|---|---|
| `fix(portions): correct filter logic` | `fix(portions): portion totals skipped orders placed after cutoff` |
| `feat(auth): update session handling` | `feat(auth): stay signed in across browser restarts` |

**Tell:** name who observes the thing in the title. When the only honest answer is "someone reading the diff", the title names a mechanism — rewrite it.

**Gate:** the observer is named, and no banned word stands as the description.

## 4. Compose the body

Open with two to four sentences of plain prose answering **what was wrong, then what changed** — written to make sense to someone who never opens the diff. No heading above it, never a bullet list, never optional.

Then only the sections that carry real content:

- **What changed** — derive one outcome-focused bullet from each verified request row; do not infer additions from the diff
- **How to verify** — derive only from the evidence index's exact observations; include applicable `not-applicable` reasons and do not invent evidence
- **Risk or scope notes** — only when something is genuinely uncertain, migrated, or deliberately deferred
- The issue link from section 2

A heading with nothing under it comes out. A small PR is the lead paragraph, how to verify, and the link. Do not paste the internal readiness tables into the PR body.

The human-authored rule in `CLAUDE.md` governs the body's voice and its ban on agent, pipeline, and session references.

**Gate:** the lead paragraph stands alone without the diff, and every heading present carries content.

## 5. Cold-read the result

Read the composed title and body once as someone with no session context. Name a result for each bar:

- **Title** — who observes it
- **Lead** — states what was wrong and what changed, without the diff
- **Terms** — every file, flag, or term is introduced where it first appears
- **Back-references** — no "as mentioned", "the above", "the earlier issue"
- **Verification** — describes what ran, not what should work
- **Voice** — no stock phrases, no agent or session references

A bar you did not name is a bar you did not check. A failed bar is rewritten and re-read, never shipped as a noted exception.

**Gate:** all six bars have a named result and none is failing.

## 6. Commit and open it

Immediately before `git-commit`, or before push when no commit is needed, repeat the branch, head, refreshed base ref and SHAs, mixed external read-back, and alternate-index snapshot checks from sections 1–2. Reuse the completed hunk accounting only when the snapshot is unchanged; a changed snapshot returns to `done`. When the verified snapshot differs from `HEAD^{tree}`, invoke `git-commit` for the verified request rows and record every SHA it creates. Run the append-only transition commands defined by `done`; their ancestry, merge, and exact ordered-list criteria must all pass. A rebase, merge, or unrecorded commit returns to `done`. Add the exact ordered list to **Expected append-only commits** in the publication evidence returned with the card.

Before pushing, require the active branch to still equal **Branch**, freshly re-fetch every mixed external target, and require its currency to still match. Then run `done`'s post-commit content seal. Record the exact outputs of `git status --porcelain=v1 --untracked-files=all` and `git rev-parse HEAD^{tree}`. The status output must be empty and the tree SHA must exactly equal **Verified content snapshot**; otherwise return to `done`.

Immediately before pushing, invoke `preflight-mutations` with one inline, single-item card. Its action is the exact local head SHA pushed to `origin` at `refs/heads/<card-branch>`; its guards include the current remote SHA or confirmed absence, and its read-back is the exact `git ls-remote` query below. The authorized `file-pr` invocation under the global rule is the authorization source. Apply the result independently: continue only on `ready` while invalidators match; present `confirmation-required`; stop on `blocked`.

```bash
git push -u origin <card-branch>
git ls-remote --heads origin "refs/heads/<card-branch>"
```

Require the remote branch SHA to equal local `HEAD`. Record the landed push before proceeding.

Immediately before creating the PR, invoke `preflight-mutations` with a new inline, single-item card. Its target is the exact repository; its action records the base, head branch and SHA, title, and complete body; its guards include the verified remote branch and recorded base tip; and its read-back is the exact `gh pr view` query below. Apply this result independently under the same result contract. A non-ready PR card does not erase the landed push evidence.

```bash
gh pr create --base <base> --title "<title>" --body "<body>"
gh pr view <pr-url> --json url,baseRefName,headRefName,headRefOid,state
```

Require the PR `headRefName` to equal **Branch** and `headRefOid` to equal local `HEAD`; require its URL, base, and state to match the publication request. Record both single-step cards, the landed push, the PR observations, the ordered commit list, and the exact commands as publication evidence for the next `done` run.

Print the URL and return to `done` for CI, review, publication-lane, and final row evaluation. Never merge. Opening the PR is a publication transition, not overall task completion.

**Handoff:** the preconditions held, base currency and issue link came from real output, the title and body passed the cold read, the remote branch and PR matched the local publication, and the evidence was returned to `done` without claiming overall completion.
