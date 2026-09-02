# Branch safety

### Ensure correct repo + branch (GitHub inputs only)

1. Parse `owner`, `repo`, `num` from the URL.
2. `gh repo view --json nameWithOwner -q .nameWithOwner`: compare with URL's `owner/repo`. Mismatch → fail fast and tell the user to `cd` into the right clone; the fix is theirs to make, so leave cloning and directory changes to them.
3. `gh pr view <url> --json headRefName,baseRefName -q .` → PR branch name + base branch.
4. `git branch --show-current` → current branch (returns empty string on detached HEAD).
5. Branch state handling:
   - **Empty output (detached HEAD)**: Use AskUserQuestion:

     Question:
       header: "Branch"
       text: "Detached HEAD detected. 'gh pr checkout <num>' will move you to the PR branch. Any uncommitted detached work may be lost."
       options:
         - label: "Checkout PR branch"
           description: "Run 'gh pr checkout <num>' to switch to the PR's head branch"
         - label: "Abort"
           description: "Stop here. I'll sort out my branch state manually"

     On "Checkout PR branch": run `gh pr checkout <num>`. On failure (conflicts, missing refs), surface the error and abort. On "Abort": exit.

   - **Different branch in the same repo**: Use AskUserQuestion:

     Question:
       header: "Branch"
       text: "You're on branch '<current>' but the PR uses '<pr-branch>'. Switch to the PR branch?"
       options:
         - label: "Switch branch"
           description: "Run 'gh pr checkout <num>' to move to the PR branch"
         - label: "Abort"
           description: "Stop. I'll checkout the right branch manually"

     On "Switch branch": run `gh pr checkout <num>`. On gh failure (conflicts, missing refs), surface the error and abort. On "Abort": exit.

   - **On the PR branch**: continue.

### Auto-stash uncommitted work (branch safety)

```bash
git status --porcelain
```

If non-empty, use AskUserQuestion:

   Question:
     header: "Stash"
     text: "Uncommitted changes detected. Auto-stash before applying fixes? Contents will be restored via 'git stash pop' at the end."
     options:
       - label: "Auto-stash"
         description: "Stash changes now. They'll be restored when the run completes"
       - label: "Abort"
         description: "Stop. I'll commit or stash my work manually first"

On "Auto-stash": run `git stash push -u -m "fix-pr-review auto-stash $(date +%s)"` and set `STASH_PUSHED=true`. If the run aborts, the user can find their work in `git stash list` as `fix-pr-review auto-stash <timestamp>`.
On "Abort": print "Commit or stash your uncommitted work first." and exit.
