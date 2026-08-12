# RESTORE.md template

Render this into `$BACKUP_DIR/RESTORE.md` at Step 7. Replace every placeholder with the
value discovered in Step 0 — a template that still says `<STATE_DIR>` is useless to whoever
opens it during an incident.

| Placeholder | Source |
|---|---|
| `<DATE>` | Date the backup was taken |
| `<VERSION>` | `openclaw --version` |
| `<STATE_DIR>` | Resolved state directory |
| `<BACKUP_DIR>` | Where the artifacts were written |
| `<SERVICE_CTL>` | Real control command, e.g. `systemctl --user`, `systemctl`, `pm2`, `docker compose` |
| `<SERVICE_NAME>` | Unit or process name |
| `<RAW_ARCHIVE>` | Filename of the raw archive |
| `<OFFICIAL_ARCHIVE>` | Filename of the official archive |
| `<DB_COUNT>` | Number of databases snapshotted |

Keep the explanatory sentences. They are what stops someone skipping the sidecar deletion
in step 4 and corrupting a database they just restored.

---

## Template body

# OpenClaw restore point — `<DATE>`

Taken with the gateway `<running | stopped>`. Restores the install to its state as of
`<DATE>`.

| | |
|---|---|
| OpenClaw version | `<VERSION>` |
| State dir | `<STATE_DIR>` |
| Service | `<SERVICE_CTL> <SERVICE_NAME>` |

## Contents

| Path | What it is |
|---|---|
| `official/<OFFICIAL_ARCHIVE>` | `openclaw backup create --verify` output. Manifest-verified. **Excludes live-mutation files, including every session transcript.** |
| `raw/<RAW_ARCHIVE>` | Byte-for-byte archive of `<STATE_DIR>`, `node_modules` excluded. **Includes the session transcripts.** The primary restore artifact. |
| `sqlite/` | `VACUUM INTO` snapshots of `<DB_COUNT>` databases. Transactionally consistent. **Use these in preference to the database files inside either archive.** |
| `meta/` | Service unit and drop-ins, environment files, version and port inventory. |
| `MANIFEST.sha256` | SHA256 of every artifact. |

### Why three overlapping artifacts

The database files inside both archives were read while the service was writing, so they
may be torn. The `sqlite/` snapshots cannot be. The correct restore is **raw archive for
the file tree, then overwrite the databases from `sqlite/`**.

## Restore

Steps 1-3 are reversible. Step 4 is the commit point.

Immediately before Step 1 mutates the live install, invoke `preflight-mutations`. Pass the
exact host, service manager/name and current health, state directory and move-aside target,
raw archive and snapshot paths, database overwrite targets, dependent channels, rollback
commands, and explicit restore approval. Apply its result contract before continuing.

### 1. Stop the service

```
<SERVICE_CTL> stop <SERVICE_NAME>
pgrep -af "openclaw" || echo "clear"
```

For a systemd **user** unit the `--user` flag is required on every command. Without it
systemd reports "unit not found" and you will believe the service is stopped while it is
still running and writing.

### 2. Move the current state aside — do not delete it

```
mv <STATE_DIR> <STATE_DIR>.broken-$(date +%Y%m%d-%H%M%S)
```

A failed restore is recoverable only if the thing you replaced still exists.

### 3. Extract the raw archive

```
tar --use-compress-program="zstd -d" -xf <BACKUP_DIR>/raw/<RAW_ARCHIVE> -C $(dirname <STATE_DIR>)
```

### 4. Overwrite the databases with the consistent snapshots

```
cd <BACKUP_DIR>/sqlite
find . -name '*.sqlite' | while read -r db; do
  target="<STATE_DIR>/${db#./}"
  cp -f "$db" "$target"
  rm -f "${target}-wal" "${target}-shm"
  echo "restored $target"
done
```

Deleting the `-wal` and `-shm` sidecars is not optional. A `VACUUM INTO` snapshot has no
WAL of its own. If a `-wal` from the previous database is left beside it, SQLite replays
those frames against a file they do not belong to and corrupts a database that was intact
a moment earlier.

### 5. Restore the service definition only if it changed

```
cp -a <BACKUP_DIR>/meta/systemd/. <unit directory>/
<SERVICE_CTL> daemon-reload
```

Copy the drop-in directory too, not just the unit file — overrides live there.

### 6. Start and verify

```
<SERVICE_CTL> start <SERVICE_NAME>
<SERVICE_CTL> status <SERVICE_NAME>
openclaw doctor
```

Confirm a message round-trip on at least one channel before calling the restore good. A
process that is up is not the same as a gateway that works.

### 7. Only once verified

```
rm -rf <STATE_DIR>.broken-<timestamp>
```

## Rolling back a failed restore

```
rm -rf <STATE_DIR>
mv <STATE_DIR>.broken-<timestamp> <STATE_DIR>
<SERVICE_CTL> start <SERVICE_NAME>
```

## Falling back to the official archive

Use only if the raw archive is unavailable. It will **not** restore session transcripts.
Verify it first with `openclaw backup verify <archive>`; its payload sits under
`<archive-root>/payload/`.

## Caveats

- **These archives are credential material** — API tokens, OAuth refresh tokens, and
  channel pairing data. Keep them mode `0700` on the machine that made them, plus one
  encrypted off-box copy; treat any other location as a disclosure.
- **`node_modules` was excluded.** Reinstall through the normal path if needed.
- **This restore procedure has not been rehearsed** unless it was actually run against a
  throwaway target. It is derived from the install's real layout, not tested end to end.
