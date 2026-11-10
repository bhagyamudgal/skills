---
name: file-pr
description: Open a GitHub pull request whose title and body a reviewer understands in one read. Use when opening a PR or publishing ready-to-publish work for review. Never open one by hand.
---

# File a pull request

The PR's reader has not seen the session, the diff, or the ticket. Every bar below exists so that reader understands the change in one pass.

## 1. Check preconditions

Read the branch and the current `done` readiness card.

- **Branch.** `git rev-parse --abbrev-ref HEAD` exactly equals **Branch** in the card and satisfies the branch-naming rule in `CLAUDE.md`. A rename or switch makes the card stale and returns to `done`.
- **Readiness card.** Require the current Git card defined by `done`, including its request, currency, coverage, lane, evidence, verdict, and next-action fields. Its verdict must be `ready-to-publish`, with this skill as the exact next action. A missing field or another verdict returns to `done`. Do not reconstruct it here.
- **Publication mode.** Bind the expected PR state and draft mode to the user's publication request. When the request does not name draft publication, use `OPEN` and `isDraft: false`.

**Gate.** Branch, card presence, expected state, and draft mode each have a recorded result, and a failed one stops the PR.

## 2. Validate the base and resolve the issue link

Use the PR base ref and exact base remote already resolved by `done`. Refresh that recorded `<base-remote>` ref with the card's exact commands, then require its remote name, ref name, remote base-tip SHA, and merge-base SHA to match. A hard-coded or substituted remote makes the card stale. Another base state or choice returns to `done` because it changes the verified diff.

Choose exactly one issue link:

- The diff fully resolves the issue: `Closes #N`
- It resolves part of one, a sub-task of an umbrella ticket or one slice of an epic: `Refs #N`, plus one line naming which part it covers and what stays open
- It was found while investigating an issue but does not fix it: `Refs #N`, and say that in the body

Never `Closes` an issue this diff does not finish.

When the user asked to batch several issues into one PR, each issue arrives as its own commit, verified by its own `done` run before the next issue starts. Before writing more than one `Closes #N`, confirm for each issue that the card holds a `verified` request row for it and that the row's evidence names its own commit: a SHA in `git log <merge-base>..HEAD` that no other batched issue's row names. At most one batched issue may instead rely on the sealed commit section 6 will create for its row. An issue missing either gets `Refs #N`, and the final report names which is missing. The body carries one link line per issue: `Closes #N` for every issue the diff finishes that passed this check, and the list above for any other.

When you choose `Refs #N` over a closing keyword, the final report says the issue will not show as linked in GitHub's Development panel, which lists only closing-keyword links, and names the reason from the list above.

### Record what is left after this merges

From the same issue output, list the work this PR leaves open. Each linked issue supplies its `- [ ]` items when it has them, and otherwise each distinct outcome its body asks for, such as under "What should happen instead", "Done looks like", or "Acceptance criteria", minus anything it marks out of scope. The user's original prompt in the conversation supplies anything else it asked for, since the card's **Originating request** often covers only this PR's part. When that prompt is out of view, as in a dispatched subagent or after compaction, use the card in place of the prompt and end the line with `(original prompt not visible)`, even after `none`. An item is left when no request row on the card finishes it, where a row finishes its item when it is `verified` or `pending` only on a `PR-dependent` gap. Every issue linked with `Refs #N` appears, with its open part, or as `#N (finished, close by hand)` when the batch rule alone kept it from `Closes`. Name each item in a few words, tagged `#N` or `prompt`. An issue the prompt names that this PR does not link appears once, as a whole:

```text
Left after this merges: #101 export button; #102 (not started); prompt: rename the CLI flag
```

With nothing left, the line reads `Left after this merges: none`. Record the line in the publication evidence returned to `done`.

**Gate.** The base ref, remote base tip, and merge base match the refreshed remote state, the issue link comes from issue output, not assumption, every batched `Closes #N` has a `verified` card row and its own commit, with at most one sealed in section 6, and the leftover line names exactly the issue and visible prompt items that no card row finishes, plus every `Refs #N` issue.

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

Require the snapshot to match **Verified content snapshot**. Account every changed hunk or logical change to one verified request row. Anything outside those rows is the stop-and-ask case in `CLAUDE.md`. Then run `done`'s index cleanup.

For an initial publication card whose **Existing PR URL** is `not-applicable`, require `HEAD` to equal **Pre-verification head** and **Expected append-only commits** to be `none`. For a superseding existing-PR card, require the recorded append-only transition and post-commit content seal from `done` to match current `HEAD` and **Verified content snapshot**. Another commit is forbidden. A changed request, base, unexpected head, or content snapshot makes the card stale. Return to `done` on any mismatch.

**Gate.** The recomputed request, branch, base ref and SHAs, head, snapshot, external currency, candidate diff, and `ready-to-publish` verdict all match the card.

## 3. Compose the title

Form: `<type>(<module>): <description>`. Name the module the way it reads on the board, not the way the directory spells it.

The description names what someone observes: what broke, or what is now possible. Not what you edited.

Banned as the whole description: `improve`, `update`, `handle`, `refactor`, `fix logic`, `clean up`, `various fixes`.

| Mechanism: rewrite | Outcome: ship |
|---|---|
| `fix(portions): correct filter logic` | `fix(portions): portion totals skipped orders placed after cutoff` |
| `feat(auth): update session handling` | `feat(auth): stay signed in across browser restarts` |

Name who observes the thing in the title. When the only honest answer is "someone reading the diff", the title names a mechanism, so rewrite it.

**Gate.** The observer is named and no banned word stands as the description.

## 4. Compose the body

Open with two to four sentences of plain prose answering what was wrong, then what changed. Write it to make sense to someone who never opens the diff. No heading above it, never a bullet list, never optional.

Then include only the sections that have content:

- **What changed.** Derive one outcome-focused bullet from each verified request row. Do not infer additions from the diff.
- **Before and after, and QA test results.** When the change alters UI or API behavior, the card's Browser facet names `.qa/pr-evidence.md` from `browser-qa`. Paste it here verbatim, except for embed lines left out on the user's first choice when push access is missing. Its SHA-256 must equal the recorded digest. A missing fragment, another digest, or a cold-read bar that fails inside the fragment returns to `done` with the failure named, because `done` regenerates the fragment through `browser-qa`.
- **How to verify.** Derive only from the evidence index's exact observations. Include applicable `not-applicable` reasons and do not invent evidence. A PR without the fragment says here in one line why browser QA does not apply, for example `No UI or API behavior changed, so there is no browser QA.` When the card's Code lane records a `parallel-review` member as `unavailable(<reason>)`, say here which review coverage did not run and why, named by the work it covers, for example `No accessibility review ran on this diff because the review tool was rate limited.` Name no agent, tool, or member. It does not block the PR. The final report names the member and its reason.
- **Risk or scope notes.** Only when something is uncertain, migrated, or deferred on purpose.
- **Not filed.** Only when `converge-reviews` left proposed follow-up issues unfiled: one line each with the finding and why it was not filed.
- The issue link from section 2.

The attach list is the target of every `![...](...)` embed in the fragment outside code, each once, in fragment order, and each file's SHA-256 must equal the digest the Browser facet recorded. A PR with no fragment attaches nothing. The data approval covers the whole fragment, its text as well as its files: paste and attach only when it holds synthetic or redacted data or the user explicitly approved publishing it. Without that approval, stop before any push, create, or body-edit side effect and ask the user to approve the listed files and text, or return to `done` to regenerate on synthetic data. Attaching requires gh v2.99.0 or later; confirm the floor with `gh --version` before any push or create side effect. When the install is older, return to `done` for a gh upgrade instead of publishing a UI or API PR without its evidence. Publish bare only on explicit user decision, then upload the fragment's files through section 6's `gh pr edit --attach` step after upgrading; `done` holds Browser `deferred` until they land.

Uploading also needs push access to the base repository. With a non-empty attach list, resolve the base repository from the card's base remote through `gh repo view --json nameWithOwner`, as section 6 does, and read `gh api repos/<nameWithOwner> --jq .permissions.push` before any push, create, or body-edit side effect. When it is not `true`, no upload from this account can replace a local path in the body, so stop before any side effect and ask the user to choose:

- **Publish without the files.** The fragment's embed lines come out of the body, the frozen attach list is empty for every lane, and the left-out paths with their digests go into the publication evidence. `done` holds Browser `deferred`.
- **Leave it to someone with push access.** Return to `done`, which sets Browser `blocked` and names the `.qa/` files and digests that publication needs.

When an older gh and missing push access both apply, this choice governs.

A heading with nothing under it comes out. A small PR is the lead paragraph, how to verify, and the link. Do not paste the internal readiness tables into the PR body.

The human-authored rule in `CLAUDE.md` governs the body's voice and its ban on agent, pipeline, and session references.

**Gate.** The lead paragraph stands alone without the diff and every heading present carries content.

## 5. Cold-read the result

Read the composed title and body once as someone with no session context. Name a result for each bar:

- **Title.** Who observes it.
- **Lead.** States what was wrong and what changed, without the diff.
- **Terms.** Every file, flag, or term is introduced where it first appears.
- **Back-references.** No "as mentioned", "the above", "the earlier issue".
- **Verification.** Describes what ran, not what should work.
- **Voice.** No stock phrases, no em or en dashes, no agent or session references.
- **Evidence.** A UI or API change carries the fragment; any other PR carries the one-line reason.

A bar you did not name is a bar you did not check. Rewrite a failed bar and re-read it. Never ship one as a noted exception.

**Gate.** All seven bars have a named result and none is failing.

## 6. Commit and open it

Resolve `$repository` through authenticated `gh repo view ... --json id,nameWithOwner` and record it as the base repository. A valid remote has ordered complete fetch and push sets from `git remote get-url --all <remote>` and `git remote get-url --push --all <remote>` whose credential-free normalized endpoints all resolve through authenticated `gh repo view ... --json id,nameWithOwner` to one common repository ID and `nameWithOwner`. An endpoint whose scheme is not HTTPS or SSH is invalid even when it resolves, since credentials would cross the wire in cleartext. When resolution follows a redirect, the final host, owner, and repository must equal the intended target or the remote is invalid. When push output mentions a redirect, resolve that final URL the same way and require HTTPS with the intended host, owner, and repository before recording the push as landed. Retain only ordered normalized sets or their digests and resolved IDs, never credentials.

When **Existing PR URL** is present, skip commit, push, and create, and load `${CLAUDE_SKILL_DIR}/references/existing-pr-reuse.md` before enumerating remotes. It owns that branch's remote selection, revalidation, candidate search, and title or body edits.

Without **Existing PR URL**, inspect the current branch's configured upstream before selecting a remote. A fully configured, resolvable upstream whose branch ref matches the publication branch selects its named remote only when that remote is valid. A malformed, partial, or unresolvable configured upstream is `reconcile-required`. When upstream is authoritatively absent, enumerate valid remotes. Auto-select a single one. When several remain, use AskUserQuestion with concrete `<remote>: <nameWithOwner> (<id>)` options, paginating disjoint option sets when needed. Stop with `Configure one valid publication remote or bind the branch upstream, then rerun file-pr.` when none remain. The selected valid remote establishes the head repository identity and `<head-owner>`. It may equal or differ from the base repository.

Record the selected remote's ordered complete endpoint sets plus separate base and head identities as guards and invalidators. Re-enumerate immediately before each push and authoritative read-back. Any addition, removal, reorder, resolution failure, or head-repository mismatch is `reconcile-required`. The named-remote push may target its configured complete push set only while that frozen set still matches.

For an initial publication, immediately before `git-commit`, or before push when no commit is needed, repeat the branch, head, refreshed base ref and SHAs, mixed external read-back, and alternate-index snapshot checks from sections 1-2. Reuse the completed hunk accounting only when the snapshot is unchanged. A changed snapshot returns to `done`. When the verified snapshot differs from `HEAD^{tree}`, invoke `git-commit` for the verified request rows in sealed-index mode: pass **Verified content snapshot**, require the staged tree to equal it, and forbid another staging pass before commit. Record every SHA it creates. Run the append-only transition commands defined by `done`. Their ancestry, merge, and exact ordered-list criteria must all pass. A rebase, merge, or unrecorded commit returns to `done`. Add the exact ordered list to **Expected append-only commits** in the publication evidence returned with the card.

For an initial publication, before pushing, require the active branch to still equal **Branch**, freshly re-fetch every mixed external target, and require its currency to still match. Then run `done`'s post-commit content seal. Record the exact outputs of `git status --porcelain=v1 --untracked-files=all` and `git rev-parse HEAD^{tree}`. The status output must be empty and the tree SHA must exactly equal **Verified content snapshot**. Otherwise return to `done`.

For an initial publication, freeze **push-attempt SHA** only after `git symbolic-ref --quiet HEAD` equals `refs/heads/<card-branch>` and that branch ref and `HEAD` resolve to the same SHA. Query the exact remote ref and require one SHA or authoritative absence. When present, require that SHA to be an ancestor of **push-attempt SHA**. Immediately before pushing, invoke `preflight-mutations` with one inline, single-item card. Its action pushes **push-attempt SHA** to the exact ref. Its guards and invalidators include the active symbolic ref, branch-ref SHA, `HEAD` SHA, selected-remote name, ordered complete fetch and push endpoint sets and repository IDs, separate base and head repository IDs, exact remote SHA or absence, and mixed external currency. Its read-back is the exact `git ls-remote` query below. The authorized `file-pr` invocation under the global rule is the authorization source. Apply the result independently: continue only on `ready` while every invalidator matches, present `confirmation-required`, and stop on `blocked`. Re-read the active symbolic ref, branch ref, `HEAD`, and selected-remote identity immediately before the command. Any movement invalidates the attempt.

```bash
git push --force-with-lease="refs/heads/<card-branch>:<expected-remote-sha-or-empty>" "<push-remote>" "<push-attempt-sha>:refs/heads/<card-branch>"
git ls-remote --heads "<push-remote>" "refs/heads/<card-branch>"
```

After every push attempt, including a nonzero or ambiguous command result, recheck the selected-remote identity and run the exact `git ls-remote` read-back once. Record **landed-push SHA** only when that authoritative SHA equals **push-attempt SHA**. An old or unexpected SHA, unavailable read-back, or changed remote identity is `reconcile-required`: stop publication and never retry from the push command result alone.

On an initial publication, recheck the active symbolic ref, branch-ref SHA, and `HEAD` against the frozen attempt. Local movement invalidates the remaining publication even when the remote read-back succeeded. Then load `${CLAUDE_SKILL_DIR}/references/upstream-binding.md` and bind the branch upstream as it directs.

Write the final body to a file and record its SHA-256 digest. Before deciding whether an earlier attempt exists, fetch every PR in the base repository through an authoritative paginated REST query:

```bash
gh api --paginate --slurp "repos/$repository/pulls?state=all&per_page=100"
```

Require every page to return successfully and parse completely. Any page error, unavailable continuation, or partial pagination is `reconcile-required`. Filter the complete result locally by exact `head.repo.id == <selected-head-repository-id>` and `head.ref == <head-branch>`, then map the retained records to the existing candidate fields, deriving `MERGED` from non-null `merged_at` and otherwise preserving `OPEN` or `CLOSED`.

Without **Existing PR URL**, recheck the active symbolic ref, branch-ref SHA, and `HEAD` against **landed-push SHA**, then reconcile every retained candidate across all states. Any `OPEN` candidate with a wrong head SHA or multiple open candidates is `reconcile-required`, and creation stops. One valid open candidate either matches the requested base, state, and draft mode or enters the explicit base-rebind or publication-decision path. Record its URL and return to `done` to bind it before any edit. A `CLOSED` or `MERGED` candidate at a different head SHA is historical and does not block branch reuse. A closed or merged candidate at **landed-push SHA** requires an explicit reopen, new-branch, or no-publication decision. Create only when the complete all-state result contains no open candidate and no closed or merged candidate for the current attempt. Use the same full paginated query and exact local filter when a create attempt returns no usable URL.

Require authoritative repository metadata to show that the selected head is the base repository or belongs to its fork network. An unrelated head blocks creation. Freeze one creation lane before preflight: same-repository heads use `gh pr create --head <branch>`. When the selected head repository is not the base repository, load `${CLAUDE_SKILL_DIR}/references/fork-creation-lanes.md` before freezing the lane. It holds both fork lanes and the ownership check that blocks any other relation. Immediately before creating the PR, invoke `preflight-mutations` with a new inline, single-item card. Its target is the exact base repository and selected head repository. Its action records the frozen creation lane, base, head repository and branch, **landed-push SHA**, title, body path and digest, the attach list with its data approval and each path's SHA-256 digest and byte size when one is frozen, expected `OPEN` state, and expected draft mode. Its guards include both complete endpoint sets and their repository IDs, separate base and head repository IDs, the active symbolic ref, branch-ref SHA and `HEAD` still at **landed-push SHA**, the verified remote branch, recorded base tip, the complete paginated candidate result and exact filter, and confirmed absence of an open candidate or same-head-SHA current attempt. Its read-back is the exact `gh pr view` query below. Apply this result independently under the same result contract. A changed local ref, `HEAD`, endpoint set, base or head identity, creation lane, title, body path, digest, attach list, approval, any attached file's digest or size, state, or draft mode invalidates the card. A non-ready PR card does not erase the landed push evidence.

Append `--draft` to the create command exactly when the bound draft mode is `isDraft: true`.

Same repository:

```bash
gh pr create --repo "$repository" --base "$base" --head "$head_branch" --title "$title" --body-file "$body_path" [--attach "<attach-list path>" ...] [--draft]
```

`--attach` uploads each file to GitHub, WebM included, at most 50 per command. It replaces every body reference that resolves to the same absolute path as an argument with that file's URL, so run it from the repository root, where the fragment's paths are relative. Video cap is 10 MB on Free plans, 100 MB on paid, and the plan is often not readable, so use 10 MB unless the user confirmed a paid plan. Immediately before creating with `--attach`, recompute every attach-list SHA-256 and byte size, require each to match the frozen card values, and require each video to be within the cap. An over-cap video returns to `done`.

Read back every lane identically with this ten-field query:

```bash
gh pr view <pr-url> --repo "$repository" --json url,title,body,baseRefName,baseRefOid,headRefName,headRefOid,headRepository,state,isDraft
```

Execute only the frozen lane. The other examples are not fallbacks after an ambiguous result.

Require the PR `title` to equal the frozen value. When nothing was attached, require `body` to equal the frozen body exactly. When files were attached, require the frozen body with each attach-list reference rewritten to a `https://github.com/user-attachments/assets/` URL and no other change: an image keeps its `![alt](...)` with only the path swapped, and a video embed alone in its paragraph becomes the bare URL. Preserve those URLs through any reconciliation instead of editing the body back to the frozen bytes.

When an upload fails gh still creates the PR and exits nonzero. The paths left to upload are exactly the attach-list paths whose local embed still appears in the read-back body. Upload each through a preflighted `gh pr edit <pr-url> --attach <path>`, once per path, read the body back the same way, and never issue another create. A path that still fails is `reconcile-required`.

Require `headRepository.id` to equal the selected head repository ID, `headRefName` to equal **Branch**, `headRefOid` to equal **landed-push SHA**, and `baseRefOid` to equal **Remote base-tip commit**. Require its URL, base name, `state`, and `isDraft` to match the publication request. Recheck the active symbolic ref, branch-ref SHA, and `HEAD` against **landed-push SHA** before accepting the publication. Record the created URL as `landed` as soon as one PR is authoritatively identified.

When only title or body differs while repository, base, head, state, and draft mode still match, preflight an exact edit of that existing PR and read it back. A base mismatch enters `done`'s existing-PR rebind path with that URL and its observed values. Never issue another create. A state or draft mismatch stops for an explicit publication decision. Never silently reopen, close, convert, or create another PR. Record both single-step cards, the landed push, the PR observations, the ordered commit list, and the exact commands as publication evidence for the next `done` run. When authoritative search cannot identify whether a PR was created, mark the create `reconcile-required` and do not retry.

End the final report with the URL, then the leftover line from section 2 as its last line. Return to `done` for CI, review, publication-lane, and final row evaluation. Never merge. Opening the PR is a publication transition, not overall task completion.

The handoff holds when the preconditions held, base currency and issue link came from real output, the title and body passed the cold read, the remote branch and PR matched the local publication, and the evidence went back to `done` without claiming overall completion.
