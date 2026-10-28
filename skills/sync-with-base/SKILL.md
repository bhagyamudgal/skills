---
name: sync-with-base
description: "Merge a PR's base branch into the current feature branch, resolve conflicts without losing work, type-check, then push the current branch only. Use on 'sync my branch with its base', 'catch my branch up', 'my PR is behind its base', 'merge main/dev into my branch', or a branch that fell behind. Detects the base from the branch's PR; never pushes to it."
---

# sync-with-base

Bring the latest changes from the current feature branch's **base branch** into it, resolve conflicts without dropping anyone's work, verify the result compiles, then commit and push **the current branch only**.

The base branch is whatever this branch's PR targets (often `main`, but also `dev`, `staging`, or a release branch). This skill works out which one, rather than assuming.

## The one rule that can never break

**Never push to the base branch.** This skill fetches the base and merges it *into* the current branch. It pushes *the current branch* to its own upstream. It does not push to, force-push to, or otherwise mutate the shared base branch. If you ever find yourself about to run `git push ... <base>`, stop. That is not this skill.

The second rule: **lose no work.** A merge is done only when the intent of *both* sides survives. Textual conflicts are the visible risk; delete/modify conflicts and semantic breakage are the silent ones. Treat all three as data-loss risks.

## Workflow

### 1. Preflight: refuse unsafe starting states

Run these checks before touching anything. If any fails, stop and tell the user what's wrong; don't try to fix it silently.

```bash
git symbolic-ref --quiet --short HEAD  # current branch; fails on a detached HEAD
git status --porcelain                 # working-tree cleanliness
git remote -v                          # confirm origin exists
```

- **Not a git repo, or no `origin` remote** → stop, report.
- **Detached HEAD** (`git symbolic-ref --quiet --short HEAD` prints nothing and exits non-zero) → stop and ask the user to check out a branch. There is no branch to merge into or to push, and `git rev-parse --abbrev-ref HEAD` would misreport the literal string `HEAD` as the branch name.
- **Working tree is not clean** (`git status --porcelain` prints anything) → **stop and report.** List the uncommitted / untracked files and ask the user to commit or stash them first. Do not merge on top of a dirty tree. A conflict resolution could clobber work git isn't tracking, and that work is unrecoverable. Do not auto-stash unless the user explicitly asks you to.

Record the current branch name. Require it to match `^[A-Za-z0-9._/-]+$`, the same allowlist step 2 applies to the base, because step 8 interpolates it into a push command and git permits characters like `$`, `(`, and `)` in a ref. If it does not match, stop and ask the user to rename the branch. You'll need this name for the push, and it's your guard against ever pushing to the base.

### 2. Determine the base branch

Resolve the base in this order and **report which one you picked and how**:

1. **User named one.** If the user said "merge `main`", "sync with `staging`", etc., use that branch. Done.
2. **The branch's PR base.** Ask the PR that this branch is the head of:

   ```bash
   gh pr view --json baseRefName -q .baseRefName
   ```

   A non-empty result is the base. This is the normal path and the whole point of the skill. It merges what the PR actually targets. `gh pr view` with no selector resolves the PR from the current branch, which is not a unique identity: a PR-specific branch config or more than one open PR on this branch can make it return a different PR's base. If the branch maps to more than one candidate PR, or the selection is otherwise ambiguous, stop and have the user pass the specific PR number or URL rather than merging the wrong base.
3. **No PR yet (or `gh` is unavailable / unauthenticated).** Fall back to the repo's default branch and say so:

   ```bash
   git symbolic-ref --quiet refs/remotes/origin/HEAD   # e.g. refs/remotes/origin/main
   # or, if that is unset:
   gh repo view --json defaultBranchRef -q .defaultBranchRef.name
   ```

   Strip to the bare branch name.

**Never silently assume `dev` (or any fixed name).** If every method above comes up empty, stop and ask the user which branch to merge.

**Validate the name before any shell command uses it.** Require the resolved base to match `^[A-Za-z0-9._/-]+$`. Git permits characters like `$`, `(`, and `)` in a ref, and `git check-ref-format` accepts them, so an unchecked name such as `topic$(cmd)` can trigger a command substitution when it is interpolated into a shell command. If the name does not match, stop and ask the user for a valid branch name. Quote the name in every command that uses it.

**Resolve which remote hosts the base.** `gh pr view` returns only the base branch *name*, not the repository that holds it. In a single-remote setup that repository is `origin`. In a fork workflow the base lives in the upstream parent, usually the remote named `upstream`, and `origin` is your own fork whose copy of the base can be stale or absent. Pick the remote whose URL matches the PR's base repository, matching by URL rather than trusting the name, and call it `<base-remote>`. It may differ from the remote you push your branch to in step 8.

Now guard against a degenerate target:

- **The current branch *is* the resolved base** (you're on `main`/`dev`/`staging` itself) → stop. There is nothing to merge into, and pushing from here would target the shared branch. Ask the user which feature branch they meant.

Call the resolved base `<base>` and its remote `<base-remote>` for the rest of this workflow.

### 3. Fetch the latest base branch

```bash
git fetch "<base-remote>" "<base>"
```

Fetch only. Do not pull-with-rebase, do not `git pull` (which can pull the wrong tracking branch). You want `<base-remote>/<base>` up to date so the merge sees the real latest.

### 4. Merge the base into the current branch

```bash
git merge "<base-remote>/<base>"
```

Three outcomes:

- **"Already up to date"** → the branch already contains everything in the base, so there is nothing to merge. This does not mean the branch is pushed: it can still hold local commits its upstream lacks. Skip the merge-related steps, then in step 8 check whether the current branch is ahead of its upstream and push if it is. If it is already in sync, tell the user there was nothing to do and stop.
- **Clean merge (fast-forward or auto-merged)** → git created/moved the commit for you. Go to step 6 (verify). Verification there may still edit files, so do not assume there is nothing left to commit.
- **Conflicts** → git halts mid-merge. Go to step 5. **Never `git merge --abort`** to escape. Resolve it.

### 5. Resolve conflicts without losing data

Invoke the **resolving-merge-conflicts** skill for its conflict-resolution discipline: read both sides' history and intent, merge semantically, preserve both where possible, and place every hunk. That skill also runs the project's checks and finishes the merge with a commit. Do not hand those final stages to it here. `sync-with-base` owns verification (step 6) and the single merge commit (step 7), so stop once the conflicts are resolved and staged and return to this workflow. Otherwise the merge gets committed twice: once inside that skill and again at step 7, where the second `git commit` finds nothing to commit and fails.

This skill adds the data-loss gate on top:

**Preserve both intents by default.** When both sides changed nearby but compatible things, the resolution keeps both. That is not data loss. It is the normal, correct outcome, and you do not need to ask.

**Ask before discarding. This is the user's explicit requirement.** Some conflicts force a genuine either/or where keeping one side means dropping the other's work:

- The two sides changed the *same* lines in incompatible ways and there is no union that preserves both meanings.
- A **delete/modify** conflict: one side deleted a file/function the other side modified. Silently taking "deleted" throws away the modifications; silently taking "modified" resurrects something the other side intentionally removed.
- A rename/edit conflict where honoring one side orphans the other's edits.

For each of these, **do not pick for the user.** Show them, in plain language:
- which file and what the conflict is about,
- what `<base-remote>/<base>` did and why (commit message / PR intent),
- what their branch did and why,
- that the two cannot both survive, and which one your resolution would keep and which it would drop.

Then ask which to keep. Wait for the answer before writing the resolution. Losing work is exactly what the user asked to be consulted on.

After resolving, before staging, **show a short summary of every conflicted file and how it was resolved**, so the user can confirm nothing was dropped. Stage resolved files with `git add`.

### 6. Verify the merge compiles

A merge with zero textual conflicts can still break the branch. The base may have renamed or removed a symbol the current branch still uses. Catch that now, not after pushing.

Run the project's acceptance gate. Where the repository defines one (this repo's convention is `/done`), that is the gate: it selects the lanes the merge touched and verifies each one. It must use the `<base>` and `<base-remote>` resolved in step 2, with that base's tip and the merge-base, for its lane selection, diff, and review. A gate that picks its own base (for example one that only ever refreshes an `origin` ref) can verify a different change set than the one being merged, so if it selects or refreshes any other base or remote, stop and hand back to the user rather than committing. Scope it to verification and repair only: stop at its readiness card and take none of the handoffs it ends in. `sync-with-base` owns the merge commit (step 7) and the push (step 8), so do not let the gate hand off to `git-commit` or `file-pr`; that would commit or publish before steps 7-8 resume and break the single-commit-owner invariant. If the gate reports required pre-publication verification as blocked, stop and hand back to the user rather than committing a broken merge. When no such gate exists, fall back to the fastest check that proves the merge did not break the branch, typically the type-check:

```bash
pnpm type-check
```

- **Green** → continue.
- **Red** → the merge introduced breakage. Fix it at the root (usually adapting the current branch's code to the base's new shape, read the actual change, don't paper over it with `as any` or a null check). Re-run until green. If it stays red after a genuine attempt and you don't understand the type model, stop and hand it back to the user rather than pushing a broken branch.

Any fix you make here changes files that are not yet committed. Step 7 commits them, so note that the branch is not ready to push straight from a clean merge.

### 7. Commit the merge

What the tree needs to push depends on both the merge outcome and whether step 6 edited anything. Do not decide from the merge outcome alone: a clean merge that needed a verification repair still has uncommitted work that `git push` would otherwise leave behind.

- **You resolved conflicts (step 5).** The merge is staged but not committed. Stage any step-6 repairs with `git add` so they land in the same commit, then:

  ```bash
  git commit --no-edit
  ```

  `--no-edit` keeps git's default merge message (`Merge remote-tracking branch '<base-remote>/<base>' into <branch>`), the right conventional message here.

- **Clean or fast-forward merge, and step 6 edited files.** Git already made the merge commit, so the repairs are sitting uncommitted. Commit them on top so the pushed tree is the verified one, staging only the paths step 6 actually changed:

  ```bash
  git add <the files you repaired in step 6> && git commit -m "fix: adapt to <base> after merge"
  ```

  Do not use `git add -A`: verification can leave reports, QA evidence, or generated files in the tree, and those are out-of-scope content the `/done` contract says never to stage. If any path you did not repair is dirty, stop and report it rather than committing.

- **Clean or fast-forward merge with no step-6 edits.** There is genuinely nothing to commit. Go to step 8.

Confirm before moving on that `git status --porcelain` is empty, so no verified change is left behind in the working tree.

**Commit as the repo's own git identity.** Never add a `Co-Authored-By: Claude` trailer and never mention Claude / AI in the message.

### 8. Push the current branch

Push **the branch you recorded in step 1** to its own publication remote, never the base. That remote is the one you normally push this branch to, which may be `origin` or your fork. Call it `<branch-remote>`. It is independent of `<base-remote>`: a fork you can write to need not hold the authoritative base.

Bind the destination ref yourself; do not let git's config choose it. A bare `git push` follows `push.default` and `remote.<name>.push`, so with `push.default=upstream` a branch tracking `<base-remote>/<base>` would push straight to the base even though step 2's guard passed on the local branch name.

The destination is `<branch>`, the branch you recorded in step 1, pushed to the same name on `<branch-remote>`. Do not derive it from the tracking config or from a no-argument `gh pr view`: both follow the branch's upstream, which can point at an integration branch or the base, so either can silently resolve to a branch other than the one you are on. Two guards make this safe:

- **Refuse if `<branch>` equals `<base>`.** That is the never-push-base rule, and no config may override it.
- **Stop and ask when a signal disagrees.** If the branch's configured upstream, or the PR GitHub associates with this branch, names a remote branch other than `<branch>`, the destination is ambiguous. Ask the user which remote branch this work should update rather than guessing. Silently fast-forwarding an unrelated branch is exactly the failure to avoid.

With the destination confirmed, push the current branch to its own name:

```bash
git push "<branch-remote>" "<branch>:refs/heads/<branch>"
```

Do not use `--force` / `--force-with-lease`. A merge only adds history, so a normal push fast-forwards. If the remote rejects the push as non-fast-forward, someone else pushed to this branch meanwhile: stop and tell the user rather than forcing.

If step 4 reported "Already up to date", there was no merge, but the branch can still be ahead of its destination. Decide whether to push by comparing against `<branch-remote>/<branch>`: fetch it, and if that remote-tracking ref does not exist (an unpublished branch), treat it as zero remote commits and push. Otherwise count with `git rev-list --count "<branch-remote>/<branch>".."<branch>"` and push the same explicit refspec only when the branch is ahead. When it is already in sync, there is nothing to push.

### 9. Report

Tell the user, concretely:
- which base branch was merged and how it was resolved (PR base, explicit, or default-branch fallback),
- what merged (how many commits from the base, or "fast-forward"),
- which files conflicted and how each was resolved,
- anything you asked them to decide and what they chose,
- that type-check passed,
- that the current branch was pushed (name it), and that the base was untouched.

Per the project's honesty rule: if you skipped a check or only inspected something without running it, say so.

## Quick reference

```
git symbolic-ref --quiet --short HEAD        # 1. current branch; fails on detached HEAD
git status --porcelain                       # 1. must be empty, else STOP
gh pr view --json baseRefName -q .baseRefName  # 2. resolve <base> (PR target)
#   empty -> repo default branch; still empty -> ask. validate name; current branch must NOT be <base>
#   resolve <base-remote> (the remote hosting the PR base; upstream in a fork, not origin)
git fetch "<base-remote>" "<base>"           # 3. fetch only
git merge "<base-remote>/<base>"             # 4. merge into current branch
#   conflicts -> resolving-merge-conflicts skill (stop before it commits) + data-loss gate (5)
pnpm type-check                              # 6. acceptance gate (/done where defined, same <base>); green
#   7. commit: merge -> git commit --no-edit; clean merge + step-6 repairs -> git add <repaired paths> (never -A)
#      clean merge, no repairs -> nothing to commit, skip
git push "<branch-remote>" "<branch>:refs/heads/<branch>"  # 8. same name; never <base>; ask if config disagrees
```
