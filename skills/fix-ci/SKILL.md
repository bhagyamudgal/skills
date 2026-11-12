---
name: fix-ci
description: "Fix a failing CI check on an existing GitHub PR: read the failing log, rerun once only for a flake, fix forward, verify with done, push behind a preflight, and watch the next run. Use when asked to fix ci, when ci is failing or a check is red on a PR or PR URL, or when a check goes red after file-pr."
---

# Fix failing CI on a PR

This skill owns what happens when a check goes red on a PR, whether the PR is the user's own, a teammate's, or one `file-pr` just opened. A red check is a finding about the change. The goal is a green run that still checks what it checked before.

The stop-and-ask conditions in the global rules' "Commit and PR autonomy" section still apply on every round.

## 1. Bind the PR

Take the PR from the URL or number the user gave, or from the current branch with `gh pr view`. Record:

```bash
gh pr view <pr> --json url,number,author,baseRefName,headRefName,headRefOid,headRepository,headRepositoryOwner,isCrossRepository,maintainerCanModify
gh api user -q .login
gh api repos/<head-owner>/<head-repo> -q .permissions.push
```

The **branch owner** is the PR author. The **head is writable** when the last command prints `true`, or when the PR is cross-repository and `maintainerCanModify` is `true`. The **expected remote SHA** starts as `headRefOid`; step 7 updates it after each push. Resolve `<head-remote>`, the configured remote whose URL points at `headRepository`; on a fork PR it differs from the base's remote. When no remote points there, stop and ask.

Check out the head branch in a clean worktree and require local `HEAD` to equal `headRefOid`. On a mismatch, stop, show both SHAs, and ask. Someone may have pushed since, or the local branch carries unpublished work.

## 2. Read the failing log before touching anything

```bash
gh pr checks <pr> --json name,state,bucket,link,workflow
gh run view <run-id> --log-failed
```

Take the run ID from each failed check's `link`. Read the log of every failed job before any rerun, edit, or push. For each one, record the job name, run ID, and the first error line.

Classify each failure. The class decides what comes next.

- **Code**: the error points at a test, lint rule, type check, or build step.
- **Flake or infrastructure**: a timeout, network or registry error, lost runner, rate limit, or cache service failure, where the error points at nothing in the diff.
- **External check**: a status from an app with no Actions run, so `gh run view` has no log. Report its name and link, and leave it out of the fix.

Send every Code and Flake failure through step 3 before acting on it. The step is done when every failed check has a class and a quoted error line.

## 3. Check whether the base is red too

For each failed job, read the base branch's latest completed run of the same workflow:

```bash
gh run list --branch <base> --workflow <workflow> --status completed --limit 1 --json databaseId,conclusion,headSha,url
gh run view <base-run-id> --log-failed
```

The failure is **base breakage** when the same job failed there with the same first error line. A same-named job that failed for another reason does not count. When no completed base run exists, as with a workflow that runs only on `pull_request`, the base is unchecked: continue, and say so in the report.

On base breakage the PR did not cause the failure. Stop. Report the PR's run URL and the base run URL, and propose filing the breakage through `file-issue`. File it only when the user says yes. Do not fix base breakage on the PR, because it mixes an unrelated change into someone's PR and leaves the base broken for every other branch.

Otherwise a Code failure goes to step 5 and a Flake failure to step 4. When a run has both, fix the Code failures first, since their push starts a new run that retries the flakes too. Rerun only when every remaining failure is a Flake.

## 4. Rerun a flake at most once per run

```bash
gh run view <run-id> --json attempt -q .attempt
```

Attempt `1` allows exactly one `gh run rerun <run-id> --failed`, then go to step 8. Attempt `2` or higher means someone already reran it, so no rerun is left. Treat the failure as code and go to step 5. A rerun that fails again is real: investigate the code instead of rerunning again.

## 5. Fix forward

Reproduce the failure locally with the failing job's own command when the project can run it. Then fix the change, not the check. Never reach green by deleting or skipping the failing test, loosening a threshold, adding an ignore directive, or dropping a file from lint. When the test is right and the change is wrong, fix the change. When the test is genuinely wrong, fix it deliberately and say so in the commit message and the report.

Fix forward with new commits on the same branch. Never amend, rebase, or force-push a published commit, including `--force-with-lease`. Some remotes reject it outright, and a teammate's checkout breaks when it lands.

The step is done when the failing command passes locally, or when the report says why it cannot run locally.

## 6. Verify and commit

Run `done` on the fix as an initial run, with the PR's base as its base. Continue on its `ready-to-publish` verdict, with only the Publication or deployment lane and the CI and Review facets pending. This skill takes that verdict in place of `file-pr`, because the PR already exists. Commit through `git-commit` in sealed-index mode against the card's **Verified content snapshot**, and record each SHA it creates in the card's **Expected append-only commits**, as `file-pr` does. Then push in step 7.

When step 1 found the head not writable, stop here. Report the local branch, the fix commit's SHA, and a suggested review comment the contributor can apply. Nothing gets pushed.

## 7. Push behind a preflight

Pushing changes a shared ref. Invoke `preflight-mutations` immediately before the push. Give it the branch, `<head-remote>`, the local SHA, the remote SHA from `git ls-remote <head-remote> refs/heads/<branch>`, and the branch owner in its ownership field.

- When the branch owner is not the user, the card's verdict is `confirmation-required`. Show `git log --oneline <remote-sha>..HEAD` and the diff stat, and wait for a yes before each push.
- When the owner is the user, the fix request authorizes the push.

When the remote SHA differs from the expected remote SHA, someone pushed meanwhile. Stop and ask. Push without force:

```bash
git push <head-remote> HEAD:refs/heads/<branch>
git ls-remote <head-remote> refs/heads/<branch>
```

When the remote rejects the push for lack of access, stop and report as step 6 does for a head that is not writable. The step is done when the read-back SHA equals local `HEAD`. That SHA becomes the expected remote SHA for the next round.

## 8. Watch the next run, two rounds at most

Start `gh pr checks <pr> --watch --fail-fast` as a background command, and wait for it through the host's background wait rather than a blocking call. A round is one pushed fix, and only a push advances the count. When the run goes green, rerun `done` on the same card as its post-publication run, with step 7's read-back as the publication evidence and the green run as the CI evidence, then report. When a rerun with no push goes red, return to step 2 in the same round. When a pushed fix's run goes red, start the next round from step 2 on the new run. When round two's run is still red, stop. Do not stack a third patch. Report what failed, what each round tried, and what to try next.

## Report

Always state the CI state with run URLs. "Pushed a fix" without the check result is an unfinished report. For each round, give the failure class, the quoted error line, the fix commit SHA, and the push read-back. Name every external check left out and every base breakage proposed for `file-issue`.
