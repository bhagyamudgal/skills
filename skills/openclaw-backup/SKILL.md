---
name: openclaw-backup
description: Take a verified, restorable backup of an OpenClaw install — official archive, consistent SQLite snapshots, a raw archive covering the session transcripts the official tool drops, a checksum manifest, and a per-install RESTORE.md. Run before upgrades, config surgery, or any risky change to a live box.
disable-model-invocation: true
---

## Input

- **Nothing** — assume the OpenClaw install on the current machine.
- **A host** — `user@host`, or "the box we're SSH'd into". Prefix every command with your
  SSH invocation; the steps are otherwise identical.

Ask only what you cannot detect: where to write the backup (default `~/backups/<date>-preflight`)
and whether a copy should be pulled off-box.

## The three traps this skill exists for

Encode these as checks, not memory. Each one produces a backup that looks fine and is not.

1. **The docs site runs ahead of shipped builds.** `docs.openclaw.ai` documents
   `openclaw backup sqlite create`. Builds in the wild may have only `create` and `verify`.
   Probe the binary in Step 1 — never assume a subcommand exists because it is documented.
2. **`openclaw backup create` silently drops live-mutation files** — `.jsonl`, `.log`,
   `.json`, `.tmp`, `.sock`, `.pid` under sessions, logs and delivery queues. Session
   transcripts are `.jsonl`, so the official archive alone **does not restore chat history**.
   Step 5 exists solely to cover this.
3. **Every OpenClaw SQLite DB runs in WAL mode.** Committed data lives partly in
   `<db>.sqlite` and partly in `<db>.sqlite-wal`. `cp` reads the two at different instants,
   so the pair can be mutually inconsistent — it copies clean and fails later. Step 3 is
   the fix.

## Step 0: Preflight

```bash
STATE_DIR="${OPENCLAW_STATE_DIR:-$HOME/.openclaw}"
[ -d "$STATE_DIR" ] || { echo "FAIL: no OpenClaw state dir at $STATE_DIR"; exit 1; }

openclaw --version
node --version                      # need v22+ for node:sqlite in Step 3
du -sh "$STATE_DIR"
df -h "$STATE_DIR"
find "$STATE_DIR" -name '*.sqlite' -not -path '*/node_modules/*' | sort
find "$STATE_DIR" -name '*-wal' -not -path '*/node_modules/*' | sort
```

Also locate the workspace, which may sit outside the state dir — check
`OPENCLAW_WORKSPACE_DIR` and `agents.defaults.workspace` in the config. If it is outside,
it is a separate backup source and must be archived too.

**Gate:** free space must be at least 2x the state dir. Below that, stop and report the
numbers rather than filling the disk of a live box.

Identify how the gateway runs — a systemd user unit (`openclaw-gateway.service`), a system
unit, pm2, Docker, or launchd. Do not assume. For a **user** unit every command needs
`systemctl --user`; without the flag systemd reports "unit not found" and you will believe
the service is stopped while it is still writing.

## Step 1: Probe the binary, not the docs

```bash
openclaw backup --help
openclaw backup create --help
```

Record which subcommands and flags actually exist. If a `sqlite` subcommand is present,
prefer it over Step 3's script and say so in the report. If it is absent, Step 3 is the
only thing standing between you and torn databases.

## Step 2: Choose the downtime mode

Ask the user. Default to zero-downtime — it is sufficient because Step 3 snapshots the
databases transactionally, and the databases are the only part that cannot tolerate a
live copy.

| Mode | What happens | Cost |
|---|---|---|
| Zero-downtime (default) | Gateway keeps running. Steps 3-5 all run hot. | Files rewritten mid-tar may be torn in the raw archive; the DBs are covered separately, and the official archive is written by the tool itself. |
| Brief stop | Stop the service, run Steps 3-6, start it. | Minutes of downtime; messages arriving in the window may be missed. Nothing is writing, so every artifact is quiescent. |

If stopping: confirm the process is actually gone (`pgrep -af openclaw`) before archiving,
and confirm it came back healthy afterwards.

## Step 3: Snapshot every SQLite database

Load `${CLAUDE_SKILL_DIR}/references/sqlite-snapshot.md` and follow it. It writes a short
Node script that uses `VACUUM INTO` — consistent against a live WAL database, no service
stop, and no `sqlite3` CLI needed (it is frequently not installed).

**Gate:** every database must report `integrity_check` = `ok` on **both** the source and
the resulting snapshot. Checking only the source proves the input was fine and says nothing
about whether the output was written correctly. Any database that fails either check stops
the run — report which one and why, do not continue and hope.

## Step 4: Official archive

```bash
cd "$HOME" && openclaw backup create --verify --output "$BACKUP_DIR/official"
```

Large installs take minutes; run it in the background and poll rather than blocking.

Capture the line reading `Skipped N volatile files`. That number is the justification for
Step 5 — quote it in the report. Confirm the run ends with `Archive verification: passed`;
absent that line, the archive is unverified and must be reported as such.

## Step 5: Raw archive — the one that holds the transcripts

```bash
tar --use-compress-program="zstd -3 -T0" \
    --exclude='*/node_modules' \
    --warning=no-file-changed \
    -cf "$BACKUP_DIR/raw/openclaw-state-raw.tar.zst" \
    -C "$(dirname "$STATE_DIR")" "$(basename "$STATE_DIR")"
echo "EXIT=$?"
```

`node_modules` is excluded because it is reinstallable and can be a third of the total.
Nothing else is excluded — the volatile files the official archive dropped are the entire
point of this step.

Then prove it, rather than assuming:

```bash
zstd -t "$BACKUP_DIR/raw/openclaw-state-raw.tar.zst"
tar --use-compress-program="zstd -d" -tf "$BACKUP_DIR/raw/openclaw-state-raw.tar.zst" > /tmp/rawlist.txt
wc -l < /tmp/rawlist.txt
grep -c 'sessions/.*\.jsonl' /tmp/rawlist.txt
grep -c 'node_modules' /tmp/rawlist.txt
```

**Gate:** the session `.jsonl` count must be greater than zero. If it is zero on an install
that has conversation history, the exclude pattern is wrong — fix it and re-run. `tar` exits
non-zero when a file changes mid-read; on a hot backup treat that as a warning to record,
not a silent pass.

## Step 6: Metadata

Enough to rebuild the environment, not just the data:

- Service unit file **and its drop-in directory** — overrides live in the drop-ins and are
  invisible if you only copy the main unit
- Environment files referenced by the unit
- `openclaw --version`, `node --version`, global npm packages
- Listening ports, running OpenClaw processes, crontab
- `du -sh` of each state subdirectory, so a later restore can be size-checked

## Step 7: Manifest and RESTORE.md

```bash
cd "$BACKUP_DIR" && find . -type f ! -name MANIFEST.sha256 -print0 \
  | sort -z | xargs -0 sha256sum > MANIFEST.sha256
chmod -R go-rwx "$BACKUP_DIR"
```

The permission change is not optional. These archives contain API tokens, messaging
pairing data and OAuth refresh tokens.

Then render `${CLAUDE_SKILL_DIR}/references/restore-template.md` into `$BACKUP_DIR/RESTORE.md`,
substituting the real paths, service name and database list discovered in Step 0. A generic
template helps nobody at 3am — the emitted file must name this install's actual paths.

## Step 8: Off-box copy

A backup on the same disk as the thing it protects survives config mistakes, not disk loss.
If the user wants a copy elsewhere:

```bash
rsync -avh --partial -e ssh <source> <destination>
```

Then verify on the receiving side against the manifest:

```bash
grep -v ' \./official/' MANIFEST.sha256 > /tmp/check.sha256   # if official/ was not pulled
sha256sum -c /tmp/check.sha256    # macOS: shasum -a 256 -c
```

**Gate:** a checksum mismatch is a FAIL, not a warning. Re-transfer the affected file.
`--partial` makes a re-run resume rather than restart.

Skipping the redundant official archive on the pull is reasonable — its contents are a
subset of the raw archive. Say so explicitly rather than leaving the omission unexplained.

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

VERIFIED:  <what was actually run and checked>
ASSUMED:   <what was inspected but not executed>
NOT DONE:  restore has not been rehearsed against this backup

VERDICT: <BACKUP COMPLETE | INCOMPLETE — reason>
```

Rules for the report:

- A backup whose checksums were never verified is not a backup. Say `INCOMPLETE`.
- If Step 5 was skipped for any reason, state plainly that chat history is not covered.
- Never claim the restore works. It has not been tested unless it was actually performed
  against a throwaway target — say so under `NOT DONE`.

## Reference files

| File | Holds |
|---|---|
| `references/sqlite-snapshot.md` | The `VACUUM INTO` snapshot script and why a live WAL database cannot be copied with `cp` |
| `references/restore-template.md` | The RESTORE.md template rendered in Step 7, including the WAL-sidecar ordering trap |
