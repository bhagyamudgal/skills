# Readiness card


For Git work, first enumerate the dirty worktree content without changing the user's index:

```bash
git diff --name-status -z HEAD --
git ls-files --others --exclude-standard -z
git diff --no-ext-diff --find-renames HEAD --
```

Draft the originating-request rows described below before snapshot construction. Normalize the tracked status records, including both paths for every rename or copy, and union them with the non-ignored untracked paths. Split that set: a path bound to at least one verified request row is **declared**; every other path is out-of-scope. Record the out-of-scope paths in **Out-of-scope worktree content** and exclude them from every step below. Unrelated dirty content is reported, never staged, and never blocks the card. Then read the full tracked diff for the declared paths. For each declared untracked path, inspect its filesystem kind before reading it: use the link text for a symbolic link, the complete bytes for a regular file, and fail closed for any other file kind. Bind every changed hunk or logical change inside a declared path to a verified request row, including separate changes that share one file. Treat a binary-file delta as a logical change and record the evidence used to scope it. An unbound hunk or logical change inside a declared path is unrelated content the snapshot would carry: stop, report it, and do not record a verified snapshot. An empty or incomplete path, diff, kind, or content inventory also fails closed.

Seal the declared set as a complete manifest of paths, Git modes, and prospective blob IDs, computed without writing objects:

```bash
git hash-object -- "<declared-regular-file>"
printf '%s' "$(readlink -- "<declared-symlink>")" | git hash-object -t blob --stdin
```

A declared path absent from the worktree is a deletion and carries no mode or blob. Immediately after creating the snapshot below, derive the same manifest from its immutable tree with `git ls-tree -r -z <tree> -- <declared paths>` and require an exact match: every declared present path at its manifest mode and blob, every declared deletion absent, before accepting the tree hash. A path, mode, or blob mismatch means content changed after scope accounting: discard the snapshot result and restart this section from the new bytes.

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

Record `$verified_content_snapshot` only after the reverse scope check passes for every declared path and every changed hunk or logical change within it. Every index operation uses the isolated temporary index, so the real index remains untouched. `GIT_INDEX_FILE` redirects the index but not the object database, which is shared: only the declared paths are ever hashed with `git hash-object -w`, so undeclared worktree content is never written into the repository. The command fails closed if setup, hashing, staging, tree creation, or cleanup fails; its exit trap removes the temporary index on both success and failure. The snapshot is `HEAD` plus exactly the declared paths: their current bytes where they exist, their removal where they were deleted. External-only work uses its target currency and read-back ledger instead of a Git snapshot.

Every prose cell below is read by someone deciding what to do next. Write it with no em or en dashes. `unslop` carries the rest of the rules where it is installed.

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

The status output must list exactly the recorded **Out-of-scope worktree content** paths and nothing else, empty when that field is `none`, and the tree SHA must exactly equal **Verified content snapshot**. Record both observations; any other remaining or newly introduced content makes the card stale. A `not-applicable` snapshot means no Git content was declared, so no commit and no content seal apply.

For Git work with no PR publication, set PR base ref, remote base tip, and merge base to `not-applicable`. When a commit is requested, leave only that request row `pending` after every other request row and required lane is `verified` and every evidence facet is `verified` or `not-applicable`. Set the exact next action to `git-commit` and pass **Verified content snapshot** into its sealed-index mode. Require its staged tree to equal that snapshot before it commits without restaging, record its SHAs as **Expected append-only commits**, and require the ordered transition plus clean-status and exact-tree content seal to pass. Then mark the commit request row `verified` and derive final readiness. When repository policy calls for an unrequested discrete-unit commit, use the same transition without adding a request row. No post-publication run applies. External-only work never creates a commit through `done`.

