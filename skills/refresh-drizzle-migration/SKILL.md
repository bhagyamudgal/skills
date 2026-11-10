---
name: refresh-drizzle-migration
description: "Refresh a branch's Drizzle migration after its base gained newer ones: merge the base, drop the stale migration, regenerate, check, push behind a preflight. Use when asked to merge main into a PR or branch and refresh or regenerate its migration, or when its journal entry or migration number trails the base's."
---

# Refresh a Drizzle migration

A migration is **stale** when the base branch gained migrations after the head branch generated its own, so the head's journal entry, snapshot chain, or folder timestamp no longer follows the base's latest. Every refresh drops the head's migration and regenerates it on top of the base.

`drizzle-kit generate` is the only drizzle-kit command this skill runs. The user's refresh request is the per-run permission for that one generate step. `migrate`, `push`, `pull`, `up`, `studio`, and any script that wraps them stay out of this run, because they touch a database or rewrite the migrations layout.

## 1. Record the starting point

Resolve the base branch the way `resolving-merge-conflicts` step 1 does. Fetch it, and use the remote-tracking ref `refs/remotes/<remote>/<base>` as `<base-ref>` in every command below; a local branch of the same name can lag the remote. When the base comes from the PR, require `<base-ref>` to equal the PR's `baseRefOid`. Require a clean worktree with the head branch checked out, as that skill does.

Find every Drizzle config: `git ls-files '*drizzle.config.*'`, plus every path a `package.json` script passes to `drizzle-kit` through `--config`. Read each config's `out` folder (default `./drizzle`) and resolve it against the config's own directory, so it works as a repo-root pathspec. Identify the layout per `out` folder:

- **Journal layout** (drizzle-kit 0.x): `meta/_journal.json`, `<idx>_<name>.sql`, `meta/<idx>_snapshot.json`.
- **Folder layout** (drizzle-kit v1): one `<timestamp>_<name>/` folder per migration holding `migration.sql` and `snapshot.json`, and no journal.

List the head's own migrations per `out` folder, before anything merges, with `git diff --name-only --diff-filter=A <base-ref>...HEAD -- <out>`. The stale SQL is readable at `HEAD` as it stands now, so record that SHA as the **stale commit**. When this lists nothing, an earlier merge may have dropped the files, so fall back to `git log --full-history --no-merges --diff-filter=A --name-only --format= <base-ref>..HEAD -- <out>`, and take each file's stale commit from `git log -1 --no-merges --format=%H --full-history --diff-filter=AM <base-ref>..HEAD -- <path>`, the last commit that wrote it, so a hand edit made after generate is the version step 5 compares.

Count migrations, not files: `.sql` files in the journal layout, distinct `<timestamp>_<name>/` folders in the folder layout. Leave alone every config whose `out` folder holds none. When one `out` folder holds two or more, stop: show them to the user and ask how to proceed, since one generate run can only produce one migration.

The step is done when every config is classified as untouched or as holding exactly one head migration, with its layout, stale SQL path, and stale commit recorded.

## 2. Merge the base

Skip this step when `git merge-base --is-ancestor <base-ref> HEAD` exits 0. Otherwise merge the base into the head branch through `resolving-merge-conflicts`, whose step 1 owns how a conflicted Drizzle `meta/` file resolves. That skill ends the merge with its own commit and readiness card, and leaves the push to step 6 here.

The step is done when `git merge-base --is-ancestor <base-ref> HEAD` exits 0 and `git status --porcelain` is empty.

## 3. Drop the stale migration

For each touched config, delete whatever of the head's migration is still present:

- **Journal layout**: the SQL file, its `meta/<idx>_snapshot.json` when the base does not own that name, and the journal entry whose `tag` equals the SQL file name without `.sql`.
- **Folder layout**: the whole migration folder.

The step is done when `git diff --name-only --diff-filter=A <base-ref> -- <out>`, which compares the working tree with the base, lists nothing, and the journal holds exactly the base's entries.

## 4. Regenerate

Read the `package.json` of the config's package and find the script that runs `drizzle-kit generate`. Run that script through the project's package manager only when it runs nothing but `drizzle-kit generate` and targets this config, through a `--config` that resolves to it or, with no `--config`, because this config is the package's default `drizzle.config.*`. Otherwise run the installed binary directly from the config's own directory, since drizzle-kit resolves `schema`, `out`, and `.env` from where it runs: `<bin> generate --config <absolute config path>`, where `<bin>` is the nearest `node_modules/.bin/drizzle-kit` from the package directory up to the repo root. When no such binary exists, stop and tell the user to install dependencies. Fetching drizzle-kit on the fly, through `npx`, `bunx`, or `npm exec`, pulls unreviewed code.

Run generate with stdin from `/dev/null` and a two-minute limit. drizzle-kit asks "created or renamed?" whenever a diff drops one column or table and adds another, and an agent shell has no TTY to answer it. When generate errors on a prompt or TTY, or hits the limit, stop and hand the user:

- the exact command, to run in their own terminal;
- the answer for each prompt, read from the stale SQL. A `RENAME` statement there means "renamed", and a matching `DROP` with `ADD` means "created".

Resume at step 5 once the user reports the new files exist.

The step is done when the `out` folder holds exactly one migration the base lacks, or generate reported no schema changes. With no changes, step 5 compares the stale SQL against an empty set.

## 5. Check the regenerated migration

Both checks must pass before anything is committed. A failure stops the run and shows the user the values or statements that failed.

**Order.** In the journal layout, the new entry's `idx` is one past the base's highest, its `when` is greater than every base entry's, and its snapshot's `prevId` equals the `id` of the base's latest snapshot. In the folder layout, the new folder's timestamp sorts after every base folder, and its snapshot's `prevIds` names the base's latest snapshot `id`.

**Same change.** Compare the stale SQL (`git show <stale commit>:<path>`) with the regenerated SQL as statement sets. Normalize both: split on `--> statement-breakpoint`, collapse whitespace, trim each trailing `;`. Order does not matter. A statement on only one side fails the check. A statement only in the stale file is hand-written SQL, a backfill, or a `--custom` migration that generate cannot reproduce. A statement only in the new file means the merged schema drifted from what the PR intended.

## 6. Verify, commit, push

Hand off to `done`, then commit the regenerated files through `git-commit`, separate from the merge commit.

Pushing updates a shared ref, and the branch may belong to a teammate. Push to `<head-remote>`, the remote that resolves to the PR's `headRepository`, or the branch's upstream when there is no PR; on a fork PR it differs from the base's remote. When no configured remote resolves to it, stop and ask. Invoke `preflight-mutations` immediately before the push, with the branch, `<head-remote>`, the local and remote SHAs, and the branch owner (the PR author, or the head repository's owner) in its ownership field. Apply its result. Push without force, then read the remote ref back with `git ls-remote <head-remote> refs/heads/<branch>` and confirm it equals local `HEAD`.

In the final report, tell the user what happens to a database that already applied the stale migration. Its next migrate runs the regenerated migration's DDL again, and it silently skips every base migration whose journal `when` is at or before the stale entry's, because the migrator only applies entries newer than the last one it recorded. Which databases those are, and how to repair them, is the user's call.
