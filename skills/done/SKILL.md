---
name: done
description: MANDATORY post-task acceptance verification. Fire before reporting ANY task complete. Route code, UI, documentation, global configuration or skills, external metadata or data, and publication or deployment to their user-facing boundaries.
---

# Post-Task Verification (/done)

`done` is the single completion entry point. Route verification to the surfaces the user will experience; repository checks are evidence only for surfaces they exercise.

## 1. Bind the run and select acceptance lanes

Record the originating request as a stable, complete summary. Preserve later user corrections in that summary before continuing.

For an initial Git run, record the exact outputs of `git rev-parse --abbrev-ref HEAD` as the branch and `git rev-parse HEAD` as the pre-verification head. A branch rename or switch invalidates the card. A post-publication run resumes the same card and preserves its branch, pre-verification head, base, and verified snapshot, except for the explicit existing-PR base-rebind path below.

For PR-bound work, resolve the intended base once here. Apply an explicit repository policy when one exists. Otherwise inspect the default and integration candidates:

```bash
gh repo view --json defaultBranchRef -q .defaultBranchRef.name
git ls-remote --heads origin 'refs/heads/dev*' 'refs/heads/develop*'
```

Choose the single unambiguous active `dev` or `develop` integration branch; use the default when none exists. Stop and ask when multiple candidates remain plausible. Refresh only the exact chosen `origin` ref, then record its name, remote base-tip SHA, merge-base SHA, and exact commands used:

```bash
git fetch --no-tags origin "+refs/heads/<base-ref>:refs/remotes/origin/<base-ref>"
git rev-parse "refs/remotes/origin/<base-ref>"
git merge-base HEAD "refs/remotes/origin/<base-ref>"
```

For external-only work, bind currency to the authoritative targets instead: record each stable target ID or URL, environment, version or revision when the system exposes one, and the exact read-back ledger. Git fields and commits are not applicable. Mixed Git and external work records both forms of currency.

Infer the required lanes from the originating request, changed artifacts, and actions already performed. Show the six-lane selection before running checks, with one reason for every required or not-applicable lane. Continue without requiring routine confirmation; apply any user correction before the final verdict.

| Lane | Select when |
|---|---|
| Code | Source, tests, scripts, build behavior, or runtime logic changed |
| UI | A user-visible interface or interaction changed |
| Documentation | A document, generated artifact, link, asset, or navigation path changed |
| Global configuration or skills | Agent rules, configuration, registration, discovery, or invocation changed |
| External metadata or data | A board, issue, PR, database, remote record, or computed external result changed |
| Publication or deployment | A release, deploy, push, published package, hosted artifact, or live consumer changed |

An unselected lane is `not-applicable`, with its exclusion reason. A selected lane is required even when its boundary is unavailable.

**Gate:** request summary and applicable currency are exact; all six lanes have a selection and reason; and every user-requested outcome maps to every lane that applies to that outcome. Do not require unrelated lanes.

## 2. Verify each required lane

Use the narrowest check that reaches the actual acceptance boundary. Do not run code checks for a task with no code lane or use an internal proxy as proof of another lane.

When Code or Global configuration or skills is required, run `simplify` once after the applicable review and parse checks. If it edits content, invalidate every acceptance observation that depends on the changed content across all lanes and evidence facets. Rerun affected code and global checks, review coverage, browser/UI flows, rendered documents/assets/links, external data or metadata read-backs, and publication or live-consumer checks. Route affected review coverage through `converge-reviews` before assigning any affected lane `verified`.

| Lane | Minimum boundary evidence |
|---|---|
| Code | Run the affected repository-native type, lint, build, and test checks. Use `fix-ts-errors` when TypeScript applies; a scoped first pass is allowed, but always run the full workspace check at least once. Run `parallel-review`, apply its `converge-reviews` result, and account for the request against the diff. `simplify`'s added-comment scan is blocking here: a comment narrating WHAT the code does, JSDoc on an obvious function, or a section divider still in the diff leaves this lane unverified. Run `reuse-first` in sweep mode and record what it returned, including nothing: `simplify` is scoped by its own gate to duplication *introduced by the change*, so duplication that already existed is invisible to every other check in this lane. |
| UI | Run the affected flow through `browser-qa`; require every affected step to pass and record browser output, screenshots, network results, and console state. |
| Documentation | Inspect the rendered or generated final artifact and exercise affected links, assets, and navigation. Source text alone does not verify rendered output. |
| Global configuration or skills | Parse the final configuration, verify registration and discovery, then check picker visibility, manual invocation, or actual consumer behavior wherever the change affects them. |
| External metadata or data | Freshly re-fetch every changed target from the authoritative system and compare exact IDs, fields, counts, or totals with the request and mutation ledger. |
| Publication or deployment | Inspect the published consumer or live target at the exact version and environment; a successful upload or deploy command alone is insufficient. |

For the code lane, fix Critical and Serious review findings and apply `converge-reviews`: continue only on `continue`, proceed on `converged`, stop on `blocked-at-cap`, and present any `follow-up-proposed` approval boundary. Re-run only checks invalidated by a fix.

For a completed shared-state mutation, reuse the exact authoritative read-back plan and landed-item ledger produced by its execution workflow. When a lane conclusion depends on inference rather than direct observation, run `verify-claims` and preserve its evidence ceiling.

Repair a failed check and re-run only its invalidated evidence. If it remains unresolved, assign the lane `blocked`.

**Gate:** every required lane has direct boundary evidence or a concrete gap; every check named by an applicable lane has a recorded result.

## 3. Assign states

Use this vocabulary for every request item, lane, and evidence facet:

- `verified` — the minimum boundary evidence supports the requested outcome.
- `pending` — required work or evidence has not been attempted or is waiting on an unmet prerequisite. PR-dependent CI or review before a PR exists is `pending`.
- `assumed` — only indirect evidence supports the outcome; name the assumption.
- `deferred` — verification was intentionally postponed; name who or what resumes it and when.
- `blocked` — a prerequisite-ready action was attempted and failed or cannot proceed; name the blocker.
- `not-applicable` — allowed only for a lane or evidence facet genuinely outside the request and changed surfaces; repeat the exclusion reason. Request items never use this state.

Unavailable boundary evidence creates an evidence ceiling. It never becomes `verified` because another lane passed.

**Gate:** each state follows from recorded evidence, and every non-verified required row names its exact gap and next action.

## 4. Build the readiness card

For Git work, first enumerate the dirty worktree content without changing the user's index:

```bash
git diff --name-status -z HEAD --
git ls-files --others --exclude-standard -z
git diff --no-ext-diff --find-renames HEAD --
```

Draft the originating-request rows described below before snapshot construction. Normalize the tracked status records, including both paths for every rename or copy, and union them with the non-ignored untracked paths. Split that set: a path bound to at least one verified request row is **declared**; every other path is out-of-scope. Record the out-of-scope paths in **Out-of-scope worktree content** and exclude them from every step below — unrelated dirty content is reported, never staged, and never blocks the card. Then read the full tracked diff for the declared paths. For each declared untracked path, inspect its filesystem kind before reading it: use the link text for a symbolic link, the complete bytes for a regular file, and fail closed for any other file kind. Bind every changed hunk or logical change inside a declared path to a verified request row, including separate changes that share one file. Treat a binary-file delta as a logical change and record the evidence used to scope it. An unbound hunk or logical change inside a declared path is unrelated content the snapshot would carry: stop, report it, and do not record a verified snapshot. An empty or incomplete path, diff, kind, or content inventory also fails closed.

Seal the declared set as a complete manifest of paths, Git modes, and prospective blob IDs, computed without writing objects:

```bash
git hash-object -- "<declared-regular-file>"
printf '%s' "$(readlink -- "<declared-symlink>")" | git hash-object -t blob --stdin
```

A declared path absent from the worktree is a deletion and carries no mode or blob. Immediately after creating the snapshot below, derive the same manifest from its immutable tree with `git ls-tree -r -z <tree> -- <declared paths>` and require an exact match — every declared present path at its manifest mode and blob, every declared deletion absent — before accepting the tree hash. A path, mode, or blob mismatch means content changed after scope accounting: discard the snapshot result and restart this section from the new bytes.

An empty declared set means the task changed no Git content: skip the construction below and set **Verified content snapshot** to `not-applicable`. Otherwise, after the reverse scope check passes, compute a deterministic content snapshot from `HEAD` plus the declared paths alone. From the repository root, create a temporary directory, use a nonexistent index path inside it for every index operation, and pass the declared paths as the function's arguments:

```bash
create_verified_snapshot() (
  test "$#" -gt 0 || return 1
  snapshot_directory=$(mktemp -d) || return 1
  snapshot_index="$snapshot_directory/index"
  cleanup_snapshot() {
    cleanup_status=0
    test ! -e "$snapshot_index" || unlink "$snapshot_index" || cleanup_status=1
    test ! -e "$snapshot_index.lock" || unlink "$snapshot_index.lock" || cleanup_status=1
    rmdir -- "$snapshot_directory" || cleanup_status=1
    return "$cleanup_status"
  }
  trap 'snapshot_status=$?; trap - EXIT; cleanup_snapshot || snapshot_status=1; exit "$snapshot_status"' EXIT

  GIT_INDEX_FILE="$snapshot_index" git read-tree HEAD || return 1

  for declared_path in "$@"; do
    if [ -L "$declared_path" ]; then
      declared_mode=120000
      link_target=$(readlink -- "$declared_path") || return 1
      blob_id=$(printf '%s' "$link_target" | git hash-object -w -t blob --stdin) || return 1
    elif [ -f "$declared_path" ]; then
      if [ -x "$declared_path" ]; then declared_mode=100755; else declared_mode=100644; fi
      blob_id=$(git hash-object -w -- "$declared_path") || return 1
    elif [ -e "$declared_path" ]; then
      return 1
    else
      GIT_INDEX_FILE="$snapshot_index" git update-index --force-remove -- "$declared_path" || return 1
      continue
    fi
    test -n "$blob_id" || return 1
    GIT_INDEX_FILE="$snapshot_index" git update-index --add \
      --cacheinfo "$declared_mode,$blob_id,$declared_path" || return 1
  done

  snapshot=$(GIT_INDEX_FILE="$snapshot_index" git write-tree) || return 1
  test -n "$snapshot" || return 1

  cleanup_snapshot || return 1
  trap - EXIT
  printf '%s\n' "$snapshot" || return 1
)

if ! verified_content_snapshot=$(create_verified_snapshot "${declared_paths[@]}"); then
  echo "Could not create an isolated verified-content snapshot" >&2
  exit 1
fi
```

Record `$verified_content_snapshot` only after the reverse scope check passes for every declared path and every changed hunk or logical change within it. Every index operation uses the isolated temporary index, so the real index remains untouched. `GIT_INDEX_FILE` redirects the index but not the object database, which is shared: only the declared paths are ever hashed with `git hash-object -w`, so undeclared worktree content is never written into the repository. The command fails closed if setup, hashing, staging, tree creation, or cleanup fails; its exit trap removes the temporary index on both success and failure. The snapshot is `HEAD` plus exactly the declared paths — their current bytes where they exist, their removal where they were deleted. External-only work uses its target currency and read-back ledger instead of a Git snapshot.

Render the drafted mapping with every originating request item exactly once, in request order, and name all lanes that apply to it:

```markdown
| Request item | Applicable lanes | Implementation/deliverable | Acceptance evidence | State | Gap/next action |
|---|---|---|---|---|---|
| <one requested outcome> | <every applicable lane> | <exact behavior, path, or external record> | <direct observation> | verified / pending / assumed / deferred / blocked | <none or exact gap/action> |
```

Then report all six lanes:

```markdown
| Lane | Required | Acceptance boundary | Evidence | State | Gap / next action |
|---|---|---|---|---|---|
| Code | yes / no | <surface> | <observation and command or artifact> | verified / pending / assumed / deferred / blocked / not-applicable | <none or exact gap and next action> |
```

Add this fixed evidence index. Each observation states what ran or was directly inspected, including exact commands, artifacts, URLs, versions, counts, or results:

```markdown
| Evidence facet | Exact evidence | State | Gap / next action |
|---|---|---|---|
| Tests | <observation> | <state> | <gap/action> |
| Browser | <observation> | <state> | <gap/action> |
| Database | <observation> | <state> | <gap/action> |
| CI | <observation> | <state> | <gap/action> |
| Review | <observation> | <state> | <gap/action> |
```

Preserve every required subcheck inside its facet. Aggregate to the weakest state in this order: `blocked`, `deferred`, `assumed`, `pending`, then `verified`; ignore only allowed `not-applicable` subchecks. The Review row names `Local review` and `PR review` separately. Before a PR, required local review may be `verified` while PR review is `pending`, making Review `pending`; after publication, both required subchecks must be `verified` for Review to become `verified`.

Subject only to the `ready-to-publish` exception below, set final **Readiness** to `ready` only when every request row and required lane is `verified` and every evidence facet is `verified` or `not-applicable`. Any required `pending`, `assumed`, `deferred`, or `blocked` row yields `not ready` and sets the **Evidence ceiling**.

For Git work whose only remaining evidence requires a PR to exist, `ready-to-publish` is allowed when every pre-publication request, lane, and evidence row is `verified` or an allowed `not-applicable`, and every unresolved required row is `pending` with an explicit `PR-dependent` gap. Any unresolved `assumed`, `deferred`, or `blocked` row prevents this transition. `ready-to-publish` authorizes only `file-pr`; it is not task completion and must not be reported as such.

For `not ready`, set **Exact next action** to the first dependency-ready unresolved action, naming its target. Do not select a later task whose prerequisite remains unresolved. For `ready-to-publish`, name invocation of `file-pr` for the recorded branch. For `ready`, use `none`.

Render the card with the applicable currency header before the three tables. Git work uses:

```markdown
## Readiness card

- **Originating request:** <complete stable summary>
- **Branch:** <exact branch name>
- **PR base ref:** <ref or not-applicable when no PR is intended>
- **Existing PR URL:** <landed PR URL or not-applicable>
- **Base refresh commands:** <exact commands run for the recorded base, or not-applicable>
- **Remote base-tip commit:** <SHA or not-applicable>
- **Merge-base commit:** <fixed diff baseline SHA>
- **Pre-verification head:** <SHA>
- **Verified content snapshot:** <Git tree hash, or not-applicable when the task declares no Git paths>
- **Out-of-scope worktree content:** <dirty non-ignored paths excluded from the snapshot, or none>
- **Expected append-only commits:** <ordered SHA list or none>
- **External targets:** <stable IDs or URLs and environments, or not-applicable>
- **Verified external target versions:** <revisions, timestamps, ETags, checksums, exact fields, or not-applicable>
- **External read-back ledger:** <authoritative observations or not-applicable>
- **Readiness:** <not ready / ready-to-publish / ready>
- **Evidence ceiling:** <weakest required states or none>
- **Exact next action:** <dependency-ready action or none>
```

External-only work uses:

```markdown
## Readiness card

- **Originating request:** <complete stable summary>
- **Currency mode:** external
- **Authoritative targets:** <stable IDs or URLs and environments>
- **Verified target versions:** <revisions, timestamps, ETags, checksums, or exact fields>
- **Read-back ledger:** <authoritative observations>
- **Readiness:** <not ready / ready>
- **Evidence ceiling:** <weakest required states or none>
- **Exact next action:** <dependency-ready action or none>
```

`file-pr` accepts only a current Git card with `ready-to-publish`. It commits verified content when needed, publishes, records the remote and PR read-back, then returns to `done`.

When `file-pr` authoritatively identifies the landed PR but observes that its base advanced, create a superseding verification card for the same request, branch, head, content, and **Existing PR URL**. Bind its base tip and merge base to the observed PR, then rerun every base-dependent diff, request-accounting, test, and review check. Preserve the landed PR identity and create evidence; invalidate the old base and every conclusion derived from it. The superseding card may return to `file-pr` only for that existing PR and can never authorize another create.

On the ordinary post-publication run, or after that rebind completes, validate the recorded commit transition with:

```bash
git merge-base --is-ancestor <pre-verification-head> HEAD
git rev-list --merges <pre-verification-head>..HEAD
git rev-list --first-parent --reverse <pre-verification-head>..HEAD
```

The first command must succeed, the merge list must be empty, and the ordered first-parent list must exactly equal **Expected append-only commits**. A failed ancestry check is a rebase; a merge or unrecorded commit makes the card stale. For PR-bound work, refresh the recorded base again and require its ref, base-tip SHA, and merge-base SHA to match the card. Freshly re-fetch every mixed external target and compare its recorded version and read-back. Consume `file-pr`'s authoritative publication evidence, verify required CI and review evidence, and re-evaluate every row. Only PR-bound work uses this post-publication run before final `ready`.

Before final `ready`, repeat the post-commit content seal:

```bash
git status --porcelain=v1 --untracked-files=all
git rev-parse HEAD^{tree}
```

The status output must list exactly the recorded **Out-of-scope worktree content** paths and nothing else — empty when that field is `none` — and the tree SHA must exactly equal **Verified content snapshot**. Record both observations; any other remaining or newly introduced content makes the card stale. A `not-applicable` snapshot means no Git content was declared, so no commit and no content seal apply.

For Git work with no PR publication, set PR base ref, remote base tip, and merge base to `not-applicable`. When a commit is requested, leave only that request row `pending` after every other request row and required lane is `verified` and every evidence facet is `verified` or `not-applicable`. Set the exact next action to `git-commit` and pass **Verified content snapshot** into its sealed-index mode. Require its staged tree to equal that snapshot before it commits without restaging, record its SHAs as **Expected append-only commits**, and require the ordered transition plus clean-status and exact-tree content seal to pass. Then mark the commit request row `verified` and derive final readiness. When repository policy calls for an unrequested discrete-unit commit, use the same transition without adding a request row. No post-publication run applies. External-only work never creates a commit through `done`.

**Done:** card currency is recorded, every request item appears once with every applicable lane, all six lanes and five evidence facets are reported, the exact next action is dependency-ready, and the verdict does not exceed the weakest required row. `ready-to-publish` hands off to `file-pr`; only `ready` permits reporting task completion.
