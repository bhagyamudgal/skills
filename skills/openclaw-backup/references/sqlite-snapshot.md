# Consistent SQLite snapshots of a live OpenClaw install

## Why a live WAL database needs `VACUUM INTO`

Every OpenClaw database runs in WAL mode. Committed rows live partly in `<db>.sqlite` and
partly in `<db>.sqlite-wal`, and the gateway writes to both. `cp` reads them at different
instants, so the copied pair can describe two different points in time. The copy succeeds,
the file opens, and it fails later, usually during the restore you were relying on.

`VACUUM INTO '<path>'` runs inside a single read transaction against the live database and
writes a fresh, consistent file. Three properties earn it:

- **No service stop.** Readers do not block the gateway's writes.
- **No `sqlite3` CLI.** Node 22+ ships `node:sqlite`, and the binary is often absent.
- **Compacted output.** Free pages left by past deletes are dropped, so a snapshot is
  routinely smaller than its source. Expect the size drop; it is reclamation, not loss.

## Why the snapshot is re-opened

`integrity_check` on the source establishes the input was healthy and nothing more. The
script re-opens each snapshot as an independent database and re-runs the check there, so
the output is established on its own evidence. A snapshot that fails that second check is
counted as a failure.

## Why the destination is guarded

Call a one-argument version of this script with two arguments and the destination silently
becomes the source: every `VACUUM INTO` then targets the live database. SQLite refuses to
overwrite an existing file, so the damage stops there, but the guard below fails the run
before it starts, which is where it belongs.

## The script

Write to a temp path on the target machine and run with two arguments: the state directory
and the destination directory.

```javascript
import { DatabaseSync } from "node:sqlite";
import { execFileSync } from "node:child_process";
import { mkdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";

const [stateArg, destinationArg] = process.argv.slice(2);

if (!stateArg || !destinationArg) {
    console.error("usage: node snapshot-sqlite.mjs <state-dir> <destination-dir>");
    process.exit(2);
}

const stateDir = resolve(stateArg);
const destinationDir = resolve(destinationArg);

if (destinationDir === stateDir || destinationDir.startsWith(stateDir + "/")) {
    console.error(`FAIL: destination ${destinationDir} is inside the state dir ${stateDir}`);
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
        entry.snapshotIntegrity = scalar(verification.prepare("PRAGMA integrity_check").get());
        entry.objects = verification
            .prepare("SELECT count(*) AS total FROM sqlite_master")
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
            ? `${megabytes(entry.sourceBytes)} -> ${megabytes(entry.snapshotBytes)}  ${entry.objects} objects  ${entry.journalMode}`
            : (entry.error ?? entry.integrity ?? "");
    console.log(`[${entry.status.padEnd(15)}] ${entry.relativePath}  ${detail}`);
}

const failures = results.filter((entry) => entry.status !== "OK");
console.log(`\n${results.length - failures.length}/${results.length} databases snapshotted successfully`);

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

Some Node 22 builds keep `node:sqlite` behind a flag; on an import failure retry with
`node --experimental-sqlite`. Filter `ExperimentalWarning` out of stderr so it reads as the
warning it is.

## Reading the output

Every line starts `[OK`, and the final count reads `N/N`. Other statuses stop the backup:

- `SOURCE_CORRUPT`: the live database is already damaged. That is a finding about the
  install; report it and name the database.
- `SNAPSHOT_CORRUPT`: the source was healthy and the copy is not. Usually free space.
- `ERROR`: most often a locked or unreadable file; the message names which.

A run finding zero databases exits 1, because an empty result almost always means a wrong
path rather than an install with no data.

## Verifying a snapshot preserves extensions

OpenClaw's memory database uses the `vec0` vector-search extension. Row-counting its virtual
tables needs the extension loaded, which a plain Node process lacks, so use `sqlite_master`
to compare object inventories instead, which needs no extension:

```javascript
db.prepare("SELECT type, name FROM sqlite_master ORDER BY type, name").all()
```

Equal inventories between source and snapshot establish that the virtual-table definitions
and their shadow tables survived.
