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

Make namespace reservation the first restore mutation. Give it a separate reversible card
whose target is one unique mode-`0700` child of `<STATE_DIR>`'s parent. On a current `ready`
verdict, allocate the child atomically, derive the move-aside path inside it, and persist both
exact paths plus the creation read-back in the mutation ledger.

```
umask 077
RESTORE_RESERVATION_DIR="$(mktemp -d "<STATE_DIR>.restore-XXXXXXXX")"
chmod 0700 "$RESTORE_RESERVATION_DIR"
BROKEN_STATE_DIR="$RESTORE_RESERVATION_DIR/original-state"
test -d "$RESTORE_RESERVATION_DIR"
test "$(find "$RESTORE_RESERVATION_DIR" -prune -type d -perm 0700 -print)" = "$RESTORE_RESERVATION_DIR"
test ! -e "$BROKEN_STATE_DIR"
printf '%s\n%s\n' "$RESTORE_RESERVATION_DIR" "$BROKEN_STATE_DIR"
```

Before Step 1, build the complete ordered restore plan and partition it into mutation cards
where `preflight-mutations` requires different reversibility or confirmation. Name the namespace
reservation, service transition, state move, archive extraction, every database replacement and
sidecar deletion, optional service-definition copy, restart, and final reservation deletion as
separate batch items with current guards, expected post-write guards, rollback, and authoritative
read-back. The final deletion belongs to its own irreversible card. Record the rollback's
restored-state deletion, exact child reversal, empty-reservation removal, and service restart as
contingent mutation-ledger items with their guards and read-backs before the reservation write.

Invoke each card immediately before its first write. Immediately before every later write in
that card, authoritatively re-read and compare the item's current guards, advancing an expected
guard only from the preceding write's read-back. Re-preflight only a card invalidated by a guard,
target, action, dependency, recovery, or authorization change. After every write, require the
authoritative read-back to match its expected post-write guard before continuing. An ambiguous
command result or read-back becomes `reconcile-required`: stop the dependent remainder, query
that exact item, and do not retry it until its external state is known. The database loop and
final deletion follow this contract item by item; they are not single unchecked shell steps.

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
mv <STATE_DIR> "$BROKEN_STATE_DIR"
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

Obtain the final deletion card's explicit confirmation. Re-read the persisted reservation root
and move-aside child, prove the root is mode `0700` and contains exactly that child with no other
entries, and continue only on a current `ready` verdict.

```
test "$BROKEN_STATE_DIR" = "$RESTORE_RESERVATION_DIR/original-state"
test -d "$BROKEN_STATE_DIR"
test "$(find "$RESTORE_RESERVATION_DIR" -prune -type d -perm 0700 -print)" = "$RESTORE_RESERVATION_DIR"
test "$(find "$RESTORE_RESERVATION_DIR" -mindepth 1 -maxdepth 1 -print | wc -l | tr -d ' ')" = "1"
test "$(find "$RESTORE_RESERVATION_DIR" -mindepth 1 -maxdepth 1 -print)" = "$BROKEN_STATE_DIR"
rm -rf -- "$RESTORE_RESERVATION_DIR"
```

Authoritatively confirm that the exact reservation root no longer exists. An indeterminate
result remains `reconcile-required` and must not be retried.

## Rolling back a failed restore

Activate the recorded rollback items, apply the same preflight and per-write ledger contract,
and use the persisted reservation root and child values.

```
rm -rf <STATE_DIR>
mv "$BROKEN_STATE_DIR" <STATE_DIR>
rmdir "$RESTORE_RESERVATION_DIR"
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
