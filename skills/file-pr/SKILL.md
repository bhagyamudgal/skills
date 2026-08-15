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
- **Publication mode** — bind the expected PR state and draft mode to the user's publication request. When the request does not name draft publication, use `OPEN` and `isDraft: false`.

**Gate:** branch, card presence, expected state, and draft mode each have a recorded result, and a failed one stops the PR.

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

For an initial publication card whose **Existing PR URL** is `not-applicable`, require `HEAD` to equal **Pre-verification head** and **Expected append-only commits** to be `none`. For a superseding existing-PR card, require the recorded append-only transition and post-commit content seal from `done` to match current `HEAD` and **Verified content snapshot**; another commit is forbidden. A changed request, base, unexpected head, or content snapshot makes the card stale. Return to `done` on any mismatch.

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

When **Existing PR URL** is present, skip commit, push, and create. Revalidate the remote branch at current `HEAD`, then read that exact URL directly with the `gh pr view` fields below before any list search. Reconcile its base, state, draft mode, head branch, and head SHA against the card and publication request; a mismatch stops or enters `done`'s explicit base-rebind path. Only a separately preflighted title/body edit may mutate it.

```bash
gh pr view "$existing_pr_url" --repo "$repository" --json url,title,body,baseRefName,baseRefOid,headRefName,headRefOid,state,isDraft
```

For an initial publication, immediately before `git-commit`, or before push when no commit is needed, repeat the branch, head, refreshed base ref and SHAs, mixed external read-back, and alternate-index snapshot checks from sections 1–2. Reuse the completed hunk accounting only when the snapshot is unchanged; a changed snapshot returns to `done`. When the verified snapshot differs from `HEAD^{tree}`, invoke `git-commit` for the verified request rows in sealed-index mode: pass **Verified content snapshot**, require the staged tree to equal it, and forbid another staging pass before commit. Record every SHA it creates. Run the append-only transition commands defined by `done`; their ancestry, merge, and exact ordered-list criteria must all pass. A rebase, merge, or unrecorded commit returns to `done`. Add the exact ordered list to **Expected append-only commits** in the publication evidence returned with the card.

For an initial publication, before pushing, require the active branch to still equal **Branch**, freshly re-fetch every mixed external target, and require its currency to still match. Then run `done`'s post-commit content seal. Record the exact outputs of `git status --porcelain=v1 --untracked-files=all` and `git rev-parse HEAD^{tree}`. The status output must be empty and the tree SHA must exactly equal **Verified content snapshot**; otherwise return to `done`.

For an initial publication, query `refs/heads/<card-branch>` directly and require exactly one current remote SHA or authoritative absence. When it exists, require that SHA to be an ancestor of local `HEAD`; this keeps the lease-guarded push fast-forward-only. Immediately before pushing, invoke `preflight-mutations` with one inline, single-item card. Its action is the exact local head SHA pushed to that ref; its guards include the exact remote SHA or confirmed absence, and its read-back is the exact `git ls-remote` query below. The authorized `file-pr` invocation under the global rule is the authorization source. Apply the result independently: continue only on `ready` while invalidators match; present `confirmation-required`; stop on `blocked`.

```bash
git push --force-with-lease="refs/heads/<card-branch>:<expected-remote-sha-or-empty>" origin "<exact-local-head-sha>:refs/heads/<card-branch>"
git ls-remote --heads origin "refs/heads/<card-branch>"
```

On an initial publication, require the remote branch SHA to equal local `HEAD` and record the landed push before changing local upstream configuration. Re-read the branch's current symbolic upstream and its SHA, then preflight a separate binding of `<card-branch>` to `origin/<card-branch>` guarded by the branch, local head, landed remote SHA, and exact observed upstream state. An already-matching upstream is an authoritative no-op. Otherwise bind and read it back:

```bash
git branch --set-upstream-to="origin/<card-branch>" "<card-branch>"
git rev-parse --abbrev-ref --symbolic-full-name "<card-branch>@{upstream}"
git rev-parse "<card-branch>@{upstream}"
```

Require the symbolic upstream to equal `origin/<card-branch>` and its SHA to equal local `HEAD`. If binding or read-back fails after the remote push landed, record `remote landed / upstream not bound` with both observed states and continue reconciliation without retrying the push. On the existing-PR branch, the revalidation at the start of this section supplies the remote-head evidence without another push.

Write the final body to a file and record its SHA-256 digest. Search the head branch across every base and state before deciding whether an earlier attempt exists:

```bash
gh pr list --repo "$repository" --head "$head_branch" --state all --limit 100 --json url,title,body,baseRefName,baseRefOid,headRefName,headRefOid,state,isDraft
```

Classify every returned candidate before create. Exactly 100 results means the search may be truncated: mark reconciliation `reconcile-required` and stop. When **Existing PR URL** is present, its direct read is the intended attempt; require its head name and SHA, base name, `state`, and `isDraft` to match the card and publication request before reuse.

Without **Existing PR URL**, reconcile every `OPEN` candidate for the branch. One open candidate must match local `HEAD`, then either match the requested base, state, and draft mode or enter the explicit base-rebind or publication-decision path; record its URL and return to `done` to bind it before any edit. Multiple open candidates are `reconcile-required`. A `CLOSED` or `MERGED` candidate whose `headRefOid` differs from local `HEAD` is historical and does not block branch reuse. A closed or merged candidate at local `HEAD` requires an explicit reopen, new-branch, or no-publication decision. Create only when the unsaturated all-state search finds no open candidate and no closed or merged candidate at local `HEAD`. Use the same head-only query when `gh pr create` returns no usable URL.

Immediately before creating the PR, invoke `preflight-mutations` with a new inline, single-item card. Its target is the exact repository; its action records the base, head branch and SHA, title, body path, body digest, expected `OPEN` state, and expected draft mode; its guards include the verified remote branch, recorded base tip, the unsaturated head-only search, and confirmed absence of an open candidate or same-head-SHA historical attempt; and its read-back is the exact `gh pr view` query below. Apply this result independently under the same result contract. A changed title, body path, digest, state, or draft mode invalidates the card; a non-ready PR card does not erase the landed push evidence.

Append `--draft` to the create command exactly when the bound draft mode is `isDraft: true`.

```bash
gh pr create --repo "$repository" --base "$base" --title "$title" --body-file "$body_path" [--draft]
gh pr view <pr-url> --repo "$repository" --json url,title,body,baseRefName,baseRefOid,headRefName,headRefOid,state,isDraft
```

Require the PR `title` and `body` to equal the frozen values, `headRefName` to equal **Branch**, `headRefOid` to equal local `HEAD`, and `baseRefOid` to equal **Remote base-tip commit**; require its URL, base name, `state`, and `isDraft` to match the publication request. Record the created URL as `landed` as soon as one PR is authoritatively identified. If only title or body differs while base, head, state, and draft mode still match, preflight an exact edit of that existing PR and read it back. A base mismatch enters `done`'s existing-PR rebind path with that URL and its observed values; never issue another create. A state or draft mismatch stops for an explicit publication decision; never silently reopen, close, convert, or create another PR. After `done` verifies a superseding card against the observed base, reuse only **Existing PR URL** and preflight any still-required title/body edit as its own exact mutation. Record both single-step cards, the landed push, the PR observations, the ordered commit list, and the exact commands as publication evidence for the next `done` run. If authoritative search cannot identify whether a PR was created, mark the create `reconcile-required` and do not retry.

Print the URL and return to `done` for CI, review, publication-lane, and final row evaluation. Never merge. Opening the PR is a publication transition, not overall task completion.

**Handoff:** the preconditions held, base currency and issue link came from real output, the title and body passed the cold read, the remote branch and PR matched the local publication, and the evidence was returned to `done` without claiming overall completion.
