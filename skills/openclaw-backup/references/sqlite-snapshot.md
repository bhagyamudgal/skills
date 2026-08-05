# Consistent SQLite snapshots of a live OpenClaw install

## Why `cp` is wrong here

Every OpenClaw database runs in WAL mode. Committed rows live partly in `<db>.sqlite` and
partly in `<db>.sqlite-wal`, and the gateway is writing to both. `cp` reads them at
different instants, so the copied pair can describe two different points in time. The copy
succeeds, the file opens, and it fails much later — usually when you are restoring it.

`VACUUM INTO '<path>'` avoids this. It runs inside a single read transaction against the
live database and writes a fresh, fully consistent file. Three properties matter:

- No service stop. Readers do not block the gateway's writes.
- No `sqlite3` CLI. Node 22+ ships `node:sqlite`, and the binary is often not installed.
- The output is compacted — free pages left by past deletes are not carried over, so
  snapshots are routinely smaller than their sources. A large size drop is expected, not
  a sign of data loss.

## Why the snapshot is re-opened afterwards

Running `integrity_check` on the source proves the input was healthy. It says nothing about
whether the output was written correctly. The script below re-opens each snapshot as an
independent database and re-runs the check there. A snapshot that cannot be verified is
not counted as a success.

## The script

Write this to a temp path on the target machine and run it with two arguments: the state
directory and the destination directory.

```javascript
import { DatabaseSync } from "node:sqlite";
import { execFileSync } from "node:child_process";
import { mkdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";

const [stateDir, destinationDir] = process.argv.slice(2);

if (!stateDir || !destinationDir) {
    console.error("usage: node snapshot-sqlite.mjs <state-dir> <destination-dir>");
    process.exit(2);
}

function findDatabases() {
    const found = execFileSync(
        "find",
        [stateDir, "-name", "*.sqlite", "-not", "-path", "*/node_modules/*"],
        { encoding: "utf8" },
    );
    return found.split("\n").filter(Boolean).sort();
}

function scalar(row) {
    return Object.values(row)[0];
}

function megabytes(bytes) {
    return (bytes / 1024 / 1024).toFixed(1) + "M";
}

function snapshot(source) {
    const relativePath = relative(stateDir, source);
    const destination = join(destinationDir, relativePath);
    const entry = { relativePath, destination };

    mkdirSync(dirname(destination), { recursive: true });

    // readOnly so a backup can never mutate live state. VACUUM INTO only reads
    // the source, so it is safe against a database the gateway is writing to.
    const database = new DatabaseSync(source, { readOnly: true });
    try {
        entry.integrity = scalar(database.prepare("PRAGMA integrity_check").get());
        entry.journalMode = scalar(database.prepare("PRAGMA journal_mode").get());

        if (entry.integrity !== "ok") {
            entry.status = "SOURCE_CORRUPT";
            return entry;
        }

        database.exec(`VACUUM INTO '${destination.replace(/'/g, "''")}'`);
    } finally {
        database.close();
    }

    const verification = new DatabaseSync(destination, { readOnly: true });
    try {
        entry.snapshotIntegrity = scalar(
            verification.prepare("PRAGMA integrity_check").get(),
        );
        entry.tables = verification
            .prepare("SELECT count(*) AS total FROM sqlite_master WHERE type='table'")
            .get().total;
    } finally {
        verification.close();
    }

    entry.sourceBytes = statSync(source).size;
    entry.snapshotBytes = statSync(destination).size;
    entry.status = entry.snapshotIntegrity === "ok" ? "OK" : "SNAPSHOT_CORRUPT";
    return entry;
}

const results = findDatabases().map((source) => {
    try {
        return snapshot(source);
    } catch (error) {
        return { relativePath: relative(stateDir, source), status: "ERROR", error: error.message };
    }
});

for (const entry of results) {
    const detail =
        entry.status === "OK"
            ? `${megabytes(entry.sourceBytes)} -> ${megabytes(entry.snapshotBytes)}  ${entry.tables} tables  ${entry.journalMode}`
            : (entry.error ?? entry.integrity ?? entry.snapshotIntegrity ?? "");
    console.log(`[${entry.status.padEnd(15)}] ${entry.relativePath}  ${detail}`);
}

const failures = results.filter((entry) => entry.status !== "OK");
console.log(
    `\n${results.length - failures.length}/${results.length} databases snapshotted successfully`,
);

if (results.length === 0) {
    console.error("FAIL: no databases found — check the state directory path");
    process.exit(1);
}
if (failures.length > 0) {
    console.error(JSON.stringify(failures, null, 2));
    process.exit(1);
}
```

## Running it

```bash
node /tmp/snapshot-sqlite.mjs "$STATE_DIR" "$BACKUP_DIR/sqlite"
```

`node:sqlite` is behind an experimental flag on some Node 22 builds. If the import fails,
retry with `node --experimental-sqlite`. Filter the `ExperimentalWarning` from stderr so it
does not read as an error in the report.

## Reading the output

Every line must start `[OK`. The final count must read `N/N`. Anything else stops the
backup:

- `SOURCE_CORRUPT` — the live database is already damaged. This is a finding about the
  install, not about the backup. Report it; do not silently skip the database.
- `SNAPSHOT_CORRUPT` — the source was fine and the copy is not. Usually disk space. Check
  free space and re-run.
- `ERROR` — most often a locked or unreadable file. The message names which.

An exit code of 0 with `0/0 databases` is impossible by construction; the script exits 1
when it finds nothing, because "no databases" almost always means a wrong path rather than
an install with no data.
