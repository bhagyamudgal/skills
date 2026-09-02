---
name: git-commit
description: Write a conventional commit. Use when the user asks to commit, or asks for a commit message to run themselves.
allowed-tools: Bash
---

# Git commit with conventional commits

I read the actual diff to find the type, scope, and message. I never write the message from memory of the task.

## Message-only mode

When I get asked for a message, phrases like "give me a commit message" or "commit message suggestion", instead of getting asked to commit, I analyze the diff as usual and print two variants to run, a one-liner and a detailed one.

## Workflow

### 1. Analyze diff

```bash
git diff --staged        # if files are staged
git diff                 # if nothing staged
git status --porcelain
```

I classify every file in `git status --porcelain` into exactly one commit before I write a message. A mixed diff becomes several commits, not one vague message.

### 2. Stage files

I stage only files I have read in the diff. I leave `.env`, `credentials.json`, and key files unstaged.

When the caller supplies a Verified content snapshot, I record the branch, old head, and original index tree, then build the candidate commit in a disposable detached worktree at that head. I load the verified tree into that worktree index and files, require `git write-tree` to equal the snapshot, and run the ordinary commit there so every hook still runs. I require the candidate commit `HEAD^{tree}` to equal the snapshot. A hook failure or mismatch leaves the real branch untouched.

Before I touch the real branch, I prepare an isolated replacement index from the candidate commit and require its tree to equal the snapshot. Only after the candidate commit and replacement index are complete do I acquire the real index lock exclusively. While I hold it, I copy the real index to an isolated path and require its tree to equal the recorded original index tree. A mismatch releases the lock and leaves the branch untouched. I atomically advance the recorded branch from the recorded old head to the candidate commit, write the prepared index bytes into the held lock, require that locked index tree to equal the snapshot, and atomically install it as the real index without changing the worktree. I release the lock on every path and remove the disposable worktree. If index installation or read-back fails after the branch advances, I report `branch advanced / index not refreshed` with the branch, candidate commit, recorded index tree, and recovery command. I never retry the branch transition or hide the partial state. I never acquire the real index lock while hooks or another Git command still need it, create the candidate commit on the real branch, or restage its live worktree.

### 3. Generate commit message

I read the type, the scope, meaning the area or module affected, and the description from the diff.

I keep the subject imperative, under 72 chars, and about WHY instead of WHAT. The diff already shows what. The body uses `-` bullets for key changes, 3-5 max.

I write the message for whoever runs `git log` a year from now. I use no em or en dashes in it. `unslop` carries the rest of the rules where it is installed.

### 4. Commit

```bash
# Single line
git commit -m "<type>[scope]: <description>"

# Multi-line: one quoted -m string, newlines inside the quotes
git commit -m "<type>[scope]: <description>

<optional body>

<optional footer>"
```

I land one atomic change per commit.

Every git operation here stays append-only. I stage, commit, and when a hook fails I fix it and land a new commit on top instead of amending.

Four things sit outside that word and I say them plainly. I leave `git config` alone, I let hooks run with no `--no-verify`, I keep `--force` and hard resets behind an explicit request, and I never force-push `main`.
