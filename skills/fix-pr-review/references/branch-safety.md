# Branch safety

### Ensure correct repo + branch (GitHub inputs only)

1. Parse `owner`, `repo`, `num` from the URL.
2. Run `gh repo view --json nameWithOwner -q .nameWithOwner` and compare it with the URL `owner/repo`. On mismatch, fail fast and tell the user to `cd` into the right clone. Cloning and directory changes stay with them, since the fix is theirs to make.
3. Run `gh pr view <url> --json headRefName,baseRefName,headRefOid,baseRefOid,headRepository -q .` to get the PR branch name, the base branch, the head SHA, the base OID, and the head repository identity. Record all five, including the base OID as `PINNED_BASE_OID`. When the head repository differs from the URL repository, the PR comes from a fork: continue only when `gh pr checkout <num>` lands exactly the recorded head SHA (`git rev-parse HEAD` must equal it), otherwise abort. A same-named local branch from another fork is never an acceptable stand-in.
4. Run `git branch --show-current` to get the current branch. It returns an empty string on detached HEAD.
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

     On "Checkout PR branch", run `gh pr checkout <num>`, then verify `git rev-parse HEAD` equals the recorded head SHA and abort on mismatch. On failure from conflicts or missing refs, surface the error and abort. On "Abort", exit.

   - **Different branch in the same repo**: Use AskUserQuestion:

     Question:
       header: "Branch"
       text: "You're on branch '<current>' but the PR uses '<pr-branch>'. Switch to the PR branch?"
       options:
         - label: "Switch branch"
           description: "Run 'gh pr checkout <num>' to move to the PR branch"
         - label: "Abort"
           description: "Stop. I'll checkout the right branch manually"

     On "Switch branch", run `gh pr checkout <num>`, then verify `git rev-parse HEAD` equals the recorded head SHA and abort on mismatch. On gh failure from conflicts or missing refs, surface the error and abort. On "Abort", exit.

   - **On the PR branch.** Verify `git rev-parse HEAD` equals the recorded head SHA. On match, continue. On mismatch, the branch name matches but the commit does not, so this is another fork's branch or a stale tracking branch. Use AskUserQuestion:

     Question:
       header: "Branch"
       text: "You're on '<pr-branch>' but HEAD is not the PR head commit. Switch to the PR branch?"
       options:
         - label: "Checkout PR branch"
           description: "Run 'gh pr checkout <num>' to move to the PR's head commit"
         - label: "Abort"
           description: "Stop. I'll sort out my branch state manually"

     On "Checkout PR branch", run `gh pr checkout <num>`, then re-verify the SHA and abort on a second mismatch. On "Abort", exit.

