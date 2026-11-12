---
name: refresh-drizzle-migration
description: "Refresh a branch's Drizzle migration after its base gained newer ones: merge the base, drop the stale migration, regenerate, check, push behind a preflight. Use when asked to merge main into a PR or branch and refresh or regenerate its migration, or when its journal entry or migration number trails the base's."
---

# Refresh a Drizzle migration

A migration is **stale** when the base branch gained migrations after the head branch generated its own, so the head's journal entry, snapshot chain, or folder timestamp no longer follows the base's latest.

`drizzle-kit generate` is the only drizzle-kit command this skill runs. The user's refresh request is the per-run permission for that one generate step. `migrate`, `push`, `pull`, `up`, `studio`, and any script that wraps them stay out of this run, because they touch a database or rewrite the migrations layout.

## 1. Record the starting point

Resolve the base branch the way `resolving-merge-conflicts` step 1 does. Fetch it, and use the remote-tracking ref `refs/remotes/<remote>/<base>` as `<base-ref>` in every command below. When the base comes from the PR, require `<base-ref>` to equal the PR's `baseRefOid`. Require a clean worktree with the head branch checked out, as that skill does.

Find every Drizzle config: `git ls-files '*drizzle.config.*'`, plus every path a `package.json` script passes to `drizzle-kit` through `--config`. Record each config's **generate script**, the `package.json` script that runs `drizzle-kit generate` for it, and its **generate directory**, where drizzle-kit runs when that script runs. That is the script's `package.json` directory unless the script changes directory first (`cd`, `--filter`, `--prefix`, `--cwd`, `-C`). With no script, it is the nearest directory, from the config's own up to the repo root, where `out` resolves to a tracked folder; with none, the config is untouched. Resolve a script's `--config` path against the generate directory too. When scripts give one config different generate directories or different commands, stop and ask which one the project uses. drizzle-kit resolves `out`, `schema`, and `.env` from the directory it runs in, not from the config's. Read each config's `out` folder (default `./drizzle`) and resolve it against the generate directory, so it works as a repo-root pathspec. Identify the layout per `out` folder:

- **Journal layout** (drizzle-kit 0.x): `meta/_journal.json`, `<idx>_<name>.sql`, `meta/<idx>_snapshot.json`.
- **Folder layout** (drizzle-kit v1): one `<timestamp>_<name>/` folder per migration holding `migration.sql` and `snapshot.json`, and no journal.

List the head's own migrations per `out` folder, before anything merges, with `git diff --name-only --diff-filter=A <base-ref>...HEAD -- <out>`. The stale SQL is readable at `HEAD` as it stands now, so record that SHA as the **stale commit**. When this lists nothing, an earlier merge may have dropped the files, so fall back to `git log --full-history --no-merges --diff-filter=A --name-only --format= <base-ref>..HEAD -- <out>`, and take each file's stale commit from `git log -1 --no-merges --format=%H --full-history --diff-filter=AM <base-ref>..HEAD -- <path>`, the last commit that wrote it, so a hand edit made after generate is the version step 5 compares.

Then run `git diff --name-only --no-renames --diff-filter=MD <base-ref>...HEAD -- <out>`. Git prints these paths from the repo root. Any path other than `<out>/meta/_journal.json` and the head migration's own `<out>/meta/<idx>_snapshot.json`, which an earlier hand merge may have resolved to the head side, means the head edited, renamed, or deleted a migration the base already has, which a refresh cannot repair, so stop and show those paths to the user.

Count migrations, not files: `.sql` files in the journal layout, distinct `<timestamp>_<name>/` folders in the folder layout. Leave alone every config whose `out` folder holds none. When one `out` folder holds two or more, stop: show them to the user and ask how to proceed, since one generate run can only produce one migration.

The step is done when every config is classified as untouched or as holding exactly one head migration, with its layout, stale SQL path, and stale commit recorded.

## 2. Merge the base

Skip this step when `git merge-base --is-ancestor <base-ref> HEAD` exits 0. Otherwise merge the base into the head branch through `resolving-merge-conflicts`, whose step 1 owns how a conflicted Drizzle `meta/` file resolves. That skill ends the merge with its own commit, skips its own `done` run when the merge dropped the head's migration because step 6 here runs it after regeneration, and leaves the push to step 6 here.

The step is done when `git merge-base --is-ancestor <base-ref> HEAD` exits 0 and `git status --porcelain` is empty.

## 3. Drop the stale migration

For each touched config, return every path the head's migration occupies to the base's version, using `git restore --source=<base-ref> -- <path>` when the base has that path and deleting the path otherwise. A path both branches added belongs to the base.

- **Journal layout**: `meta/_journal.json`, which always comes back from the base, plus the SQL file and its `meta/<idx>_snapshot.json`.
- **Folder layout**: the migration folder.

The step is done when `git diff --name-only <base-ref> -- <out>`, which compares the working tree with the base, lists nothing.

## 4. Regenerate

Take the generate script step 1 recorded for this config, if any. Run that script through the project's package manager only when all three hold. It runs nothing but `drizzle-kit generate`. It targets this config, through a `--config` that resolves to it or, with no `--config`, because this config is the first of `drizzle.config.ts`, `.js`, and `.json` in the generate directory, the only names drizzle-kit reads without one. Its `package.json` has no `pre<script>` or `post<script>` entry for it, since npm runs those hooks with the script. Otherwise run the installed binary directly from the config's generate directory, recorded in step 1: `<bin> generate --config <absolute config path>`, where `<bin>` is the nearest `node_modules/.bin/drizzle-kit` from the generate directory up to the repo root. When no such binary exists, stop and tell the user to install dependencies; `npx`, `bunx`, and `npm exec` fetch unreviewed code.

Run generate with stdin from `/dev/null` and a two-minute limit. When it errors on a prompt or TTY, or hits the limit, read `${CLAUDE_SKILL_DIR}/references/rename-prompts.md` and follow it.

The step is done when the `out` folder holds exactly one migration the base lacks, or generate reported no schema changes. With no changes, step 5 compares the stale SQL against an empty set.

## 5. Check the regenerated migration

Both checks must pass before anything is committed. A failure stops the run and shows the user the values or statements that failed.

**Order.** In the journal layout, the new entry's `idx` is one past the base's highest, its `when` is greater than every base entry's, and its snapshot's `prevId` equals the `id` of the base's latest snapshot. In the folder layout, the new folder's timestamp sorts after every base folder, and its snapshot's `prevIds` names the base's latest snapshot `id`.

**Same change.** Compare the stale SQL (`git show <stale commit>:<path>`) with the regenerated SQL as statement sets. Normalize both: split on `--> statement-breakpoint`, drop `--` comments outside quoted spans, collapse whitespace outside quoted spans while leaving quoted text byte-exact, then trim each statement and strip one trailing `;`. A quoted span is single-quoted, double-quoted, or dollar-quoted (`$$` or `$tag$`, closed only by the same tag, with quote characters inside it opening nothing). Order does not matter. A statement on only one side fails the check. A statement only in the stale file is hand-written SQL, a backfill, or a `--custom` migration that generate cannot reproduce. A statement only in the new file means the merged schema drifted from what the PR intended.

## 6. Verify, commit, push

Hand off to `done`. When it changes any file, probe each touched config with step 4's generate command alone: stdin from `/dev/null`, the two-minute limit, and no prompt handoff. A probe that writes a migration, stops on a prompt, or hits the limit means `done` changed that config's schema. Then delete every migration this run generated for it (journal layout: each SQL file and its `meta/<idx>_snapshot.json`; folder layout: each folder), restore its journal from `<base-ref>`, require `git diff --name-only <base-ref> -- <out>` and `git ls-files --others --exclude-standard -- <out>` to list nothing, and rerun steps 4 and 5 and `done`. When a probe after such a rerun again writes a migration, stops on a prompt, or hits the limit, stop and show the user its SQL or output. Then commit through `git-commit`, separate from the merge commit: first `done`'s fixes for merge damage outside the migrations folder, then the regenerated files.

Pushing updates a shared ref, and the branch may belong to a teammate. Push to `<head-remote>`, the remote that resolves to the PR's `headRepository`, or the branch's upstream when there is no PR; on a fork PR it differs from the base's remote. When no configured remote resolves to it, stop and ask. Invoke `preflight-mutations` immediately before the push, with the branch, `<head-remote>`, the local and remote SHAs, and the branch owner (the PR author, or the head repository's owner) in its ownership field. Apply its result. Push without force, then read the remote ref back with `git ls-remote <head-remote> refs/heads/<branch>` and confirm it equals local `HEAD`.

In the final report, tell the user what happens to a database that already applied the stale migration. Its next migrate runs the regenerated migration's DDL again. In the journal layout, the 0.x migrator also silently skips every base migration whose journal `when` is at or before the stale entry's, because it only applies entries newer than the last one it recorded. For the folder layout, say this skill has not established which base migrations such a database skips. Which databases those are, and how to repair them, is the user's call.
