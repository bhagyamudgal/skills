---
name: git-commit
description: Write a conventional commit. Use when the user asks to commit, or asks for a commit message to run themselves.
license: MIT
allowed-tools: Bash
---

# Git Commit with Conventional Commits

Analyze the actual diff to determine type, scope, and message. Never write the message from memory of the task.

## Message-Only Mode

When the user asks FOR a commit message ("give me a commit message", "commit message suggestion") rather than asking TO commit: analyze the diff as usual and print two variants for them to run, a one-liner and a detailed one.

## Workflow

### 1. Analyze Diff

```bash
git diff --staged        # if files are staged
git diff                 # if nothing staged
git status --porcelain
```

**Every file in `git status --porcelain` is classified into exactly one commit** before you write a message. A mixed diff becomes several commits, not one vague message.

### 2. Stage Files

Stage only files you have read in the diff. `.env`, `credentials.json`, and key files stay unstaged.

When the caller supplies a **Verified content snapshot**, record the branch, old head, and original index tree, then build the candidate commit in a disposable detached worktree at that head. Load the verified tree into that worktree's index and files, require `git write-tree` to equal the snapshot, and run the ordinary commit there so every hook still runs. Require the candidate commit's `HEAD^{tree}` to equal the snapshot; a hook failure or mismatch leaves the real branch untouched.

Before changing the real branch, prepare an isolated replacement index from the candidate commit and require its tree to equal the snapshot. Only after the candidate commit and replacement index are complete, acquire the real index lock exclusively. While holding it, copy the real index to an isolated path and require its tree to equal the recorded original index tree; a mismatch releases the lock and leaves the branch untouched. Atomically advance the recorded branch from the recorded old head to the candidate commit, write the prepared index bytes into the held lock, require that locked index's tree to equal the snapshot, and atomically install it as the real index without changing the worktree. Release the lock on every path and remove the disposable worktree. If index installation or read-back fails after the branch advances, report `branch advanced / index not refreshed` with the branch, candidate commit, recorded index tree, and recovery command; never retry the branch transition or hide the partial state. Never acquire the real index lock while hooks or another Git command still needs it, create the candidate commit on the real branch, or restage its live worktree.

### 3. Generate Commit Message

From the diff, determine the **type**, the **scope** (the area or module affected), and the **description**.

Subject: imperative, under 72 chars, explaining WHY rather than WHAT. The diff already shows what. Body uses `-` bullets for key changes, 3-5 max.

### 4. Commit

```bash
# Single line
git commit -m "<type>[scope]: <description>"

# Multi-line — one quoted -m string, newlines inside the quotes
git commit -m "<type>[scope]: <description>

<optional body>

<optional footer>"
```

One atomic change per commit.

Every git operation here is **append-only**. Stage, commit, and if a hook fails, fix it and land a new commit on top rather than amending.

Four things sit outside that word and need saying: leave `git config` alone, let hooks run (no `--no-verify`), keep `--force` and hard resets behind an explicit request, and never force-push `main`.
