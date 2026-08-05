---
name: openclaw-backup
description: Verified, restorable backup of an OpenClaw install, with a restore runbook written for that install.
disable-model-invocation: true
---

Every step ends on a **gate** — a check that produces evidence. A gate you did not run is a
gate that failed. The failure this skill is built against is **silent**: an archive that
writes cleanly, verifies cleanly, and turns out to be missing the thing you needed.

## Input

- **Nothing** — the OpenClaw install on the current machine.
- **A host** — `user@host`. Prefix every command with your SSH invocation; the steps are
  otherwise identical.

Detect what you can. Ask only for the backup destination (default
`~/backups/<date>-preflight`) and whether to pull a copy off-box.

## Step 0: Preflight

```bash
STATE_DIR="${OPENCLAW_STATE_DIR:-$HOME/.openclaw}"
[ -d "$STATE_DIR" ] || { echo "FAIL: no OpenClaw state dir at $STATE_DIR"; exit 1; }

openclaw --version
node --version                      # v22+ carries node:sqlite, needed in Step 3
du -sh "$STATE_DIR"
df -h "$STATE_DIR"
find "$STATE_DIR" -name '*.sqlite' -not -path '*/node_modules/*' | sort
```

Discover the databases with `find` on every run. OpenClaw relocates them between versions —
2026.7 moved the memory database from `memory/main.sqlite` to
`agents/<id>/agent/openclaw-agent.sqlite`, so a hardcoded path silently finds nothing.

Locate the workspace, which may sit outside the state dir: check `OPENCLAW_WORKSPACE_DIR`
and `agents.defaults.workspace` in the config. A workspace outside the state dir is a
separate archive source.

Identify how the gateway runs — systemd user unit (`openclaw-gateway.service`), system unit,
pm2, Docker, or launchd — by inspecting the host. A **user** unit needs `systemctl --user`
on every command; plain `systemctl` reports "unit not found", which reads as stopped while
the service is still writing.

**Gate:** free space is at least 2x the state dir, and the database list is non-empty.

## Step 1: Read capabilities from `--help`

```bash
openclaw backup --help
openclaw backup create --help
```

`--help` is the source of truth for this install. `docs.openclaw.ai` documents a
`backup sqlite` subcommand that shipped builds may lack, so the docs site describes a
capability the binary may not have.

**Gate:** the subcommand list is recorded. If `sqlite` is present, prefer it over Step 3 and
say so in the report.

## Step 2: Choose the downtime mode

Ask the user. Default to zero-downtime: Step 3 snapshots the databases transactionally, and
the databases are the only part that cannot tolerate a live copy.

| Mode | Cost |
|---|---|
| Zero-downtime (default) | Files rewritten mid-tar may be torn in the raw archive. Databases are covered separately. |
| Brief stop | Minutes of downtime, messages in that window missed. Every artifact quiescent. |

If stopping: confirm the process is gone with `pgrep -af openclaw` before archiving, and
confirm it returned healthy afterwards.

## Step 3: Snapshot every SQLite database

Load `${CLAUDE_SKILL_DIR}/references/sqlite-snapshot.md` and follow it — the `VACUUM INTO`
script, and why a live WAL database needs it.

**Gate:** every database reports `integrity_check` = `ok` on **both** source and snapshot,
and the count reads `N/N`. A database failing either check stops the run; report which one
and what it said.

## Step 4: Official archive

```bash
cd "$HOME" && openclaw backup create --verify --output "$BACKUP_DIR/official"
```

Large installs take minutes — run it in the background and poll.

This archive omits live-mutation files: `.jsonl`, `.log`, `.json`, `.tmp`, `.sock`, `.pid`
under sessions, logs and delivery queues. Session transcripts are `.jsonl`, which is why
Step 5 follows.

**Gate:** the run ends with `Archive verification: passed`, and the `Skipped N volatile
files` count is recorded for the report. Without that verification line the archive counts
as unverified.

## Step 5: Raw archive — the one holding the transcripts

```bash
tar --use-compress-program="zstd -3 -T0" \
    --exclude='*/node_modules' \
    --warning=no-file-changed \
    -cf "$BACKUP_DIR/raw/openclaw-state-raw.tar.zst" \
    -C "$(dirname "$STATE_DIR")" "$(basename "$STATE_DIR")"
echo "EXIT=$?"
```

`node_modules` is excluded as reinstallable and often a third of the total. Everything else
stays: the volatile files Step 4 dropped are the point of this step.

Then produce the evidence:

```bash
zstd -t "$BACKUP_DIR/raw/openclaw-state-raw.tar.zst"
tar --use-compress-program="zstd -d" -tf "$BACKUP_DIR/raw/openclaw-state-raw.tar.zst" > /tmp/rawlist.txt
wc -l < /tmp/rawlist.txt
grep -c 'sessions/.*\.jsonl' /tmp/rawlist.txt
grep -c 'node_modules' /tmp/rawlist.txt
```

**Gate:** `zstd -t` passes and the session `.jsonl` count is greater than zero on an install
with conversation history. A zero count means the exclude pattern is wrong — fix it and
re-run. `tar` exits non-zero when a file changes mid-read; on a hot backup record that as a
warning in the report.

## Step 6: Metadata

Capture each of these into `meta/`:

- Service unit file **and its drop-in directory** — overrides live in the drop-ins
- Environment files the unit references
- `openclaw --version`, `node --version`, global npm packages
- Listening ports, running OpenClaw processes, crontab
- `du -sh` of each state subdirectory, for size-checking a later restore

**Gate:** every item above is present in `meta/` or named in the report as unavailable, with
the reason.

## Step 7: Manifest and RESTORE.md

```bash
cd "$BACKUP_DIR" && find . -type f ! -name MANIFEST.sha256 -print0 \
  | sort -z | xargs -0 sha256sum > MANIFEST.sha256
chmod -R go-rwx "$BACKUP_DIR"
```

Apply the permission change: these archives carry API tokens, messaging pairing data and
OAuth refresh tokens.

Render `${CLAUDE_SKILL_DIR}/references/restore-template.md` into `$BACKUP_DIR/RESTORE.md`,
substituting the real paths, service name and database list from Step 0.

**Gate:** `MANIFEST.sha256` lists every artifact, the backup directory is mode `0700`, and
the rendered `RESTORE.md` contains no remaining `<PLACEHOLDER>` tokens.

## Step 8: Off-box copy

A backup on the same disk as the thing it protects survives config mistakes, not disk loss.
If the user wants a copy elsewhere:

```bash
rsync -avh --partial -e ssh <source> <destination>
```

Verify on the receiving side against the manifest:

```bash
grep -v ' \./official/' MANIFEST.sha256 > /tmp/check.sha256   # if official/ was not pulled
sha256sum -c /tmp/check.sha256    # macOS: shasum -a 256 -c
```

Confirm the checksum output covers a non-empty file list before reading it as a pass — a
verifier fed an empty list reports success having checked nothing.

**Gate:** every checked file reports `OK`. A mismatch fails the step; re-transfer that file.
`--partial` makes a re-run resume.

Omitting the official archive from the pull is reasonable — its contents are a subset of the
raw archive. State that omission in the report.

## Step 9: Report

```
OPENCLAW BACKUP — <host or "local">

Install:  OpenClaw <version>, state dir <path> (<size>)
Service:  <unit/manager>, <running|stopped during backup>
Mode:     <zero-downtime | brief stop>

Artifacts (<total size>, mode 0700):
  official/<name>.tar.gz     <size>   verification: <passed|NOT VERIFIED>
  raw/<name>.tar.zst         <size>   <N> entries, <M> session transcripts
  sqlite/                    <size>   <X>/<X> databases, integrity ok source + snapshot
  meta/                      <size>   unit + drop-ins, env, inventory
  MANIFEST.sha256 + RESTORE.md

Official archive skipped <N> volatile files — covered by the raw archive.

VERIFIED:  <what was run, and the evidence each produced>
ASSUMED:   <what was inspected but not executed>
NOT DONE:  restore has not been rehearsed against this backup

VERDICT: <BACKUP COMPLETE | INCOMPLETE — reason>
```

**Gate:** every gate from Steps 0-8 appears under `VERIFIED` with its evidence, or under
`ASSUMED` with the reason it was not run. `BACKUP COMPLETE` requires all of them verified.

Two claims to keep accurate:

- A backup with unverified checksums reads `INCOMPLETE`.
- The restore stays under `NOT DONE` until it has actually been performed against a
  throwaway target. Running the backup proves the archives exist, not that they restore.
