#!/usr/bin/env python3
"""Load the frozen /review-pr benchmark and flatten independently-produced schemas into one record shape.

The benchmark was produced by adjudication runs that never agreed a schema. Anchors alone
arrive as `file` + `line`, as `path` + `lines`/`lines_original`, as a free-text `file`
that may hold two paths or a glob, and as `path` + `line` with nulls. Claim text is
`claim` in some corpora and `title` in others. Severity has three vocabularies.

So nothing here dispatches on a filename. Every file is sniffed for its shape and read
through one field-aliasing normaliser, which means a fifth corpus with a sixth schema
loads without a code change — and, just as importantly, no repo or corpus name from the
private data is baked into this public file. Corpus labels are derived from the file
stems at runtime.

Records the loader cannot anchor are kept with a degraded `anchor_quality` rather than
dropped: a silently dropped record inflates every rate computed downstream.
"""
import hashlib
import json
import pathlib
import re

# The benchmark's NORMALIZATION.md §3 forbids silently mapping one source's severity onto
# another's, so severity is never translated. Each source gets its own high-tier predicate
# and the report labels the pair a stated crosswalk, not an equivalence.
HIGH_TIER = {
    "review-pr-skill": {"critical", "serious"},
    "coderabbit": {"critical", "major"},
    "gold": {"critical", "serious", "high"},
}

# CORRECT_TRIVIAL is true-of-the-code, so it is not a false positive. UNVERIFIABLE
# cannot be graded either way and leaves the denominator entirely.
FALSE_VERDICTS = {"FALSE_POSITIVE", "HALLUCINATION"}
TRUE_VERDICTS = {"CORRECT", "CORRECT_TRIVIAL"}

ID_KEYS = ("id", "fid", "finding_key")
PATH_KEYS = ("path", "file", "file_path")
# `lines` is GitHub's line at CURRENT head; `lines_original` is the line the comment was
# actually posted against. A replay reads the recorded commit, so the original anchor is
# the only one that can line up — it has to win wherever both exist.
LINE_KEYS = ("lines_original", "lines", "line", "line_start")
CLAIM_KEYS = ("claim", "title", "issue", "finding_label", "label")
SEVERITY_KEYS = ("severity", "severity_raw", "sev")

_PATH_RE = re.compile(r"[\w.\-\[\]@/]*[\w\-\[\]]\.[A-Za-z0-9]{1,5}")
_LINES_RE = re.compile(r"(\d+)(?:\s*-\s*(\d+))?")
_TICKET_PR_RE = re.compile(r"PR\s*#(\d+)")
_TICKET_ISSUE_RE = re.compile(r"#(\d+)")


def _pick(row, keys):
    for k in keys:
        if row.get(k) not in (None, ""):
            return row[k]
    return None


def _norm_severity(raw):
    if raw is None:
        return None
    return re.sub(r"[^a-z]", "", str(raw).lower()) or None


def _tier(source, severity):
    return "high" if severity in HIGH_TIER.get(source, set()) else "low"


def _norm_source(row):
    raw = str(row.get("source") or "")
    if raw.startswith("coderabbit"):
        return "coderabbit", ("body" if raw.endswith("-body") else "inline")
    if raw:
        return "review-pr-skill", "inline"
    # No explicit source. A CodeRabbit export carries its own finding id prefix and an
    # emoji severity vocabulary; nothing else in the benchmark does.
    sev = str(_pick(row, SEVERITY_KEYS) or "")
    if row.get("fid") or any(ord(c) > 0x2500 for c in sev):
        return "coderabbit", "inline"
    return "review-pr-skill", "inline"


def _split_lines(value):
    if value is None:
        return None, None
    m = _LINES_RE.search(str(value))
    if not m:
        return None, None
    start = int(m.group(1))
    return start, int(m.group(2)) if m.group(2) else start


def _parse_free_anchor(text):
    """Pull a path and line range out of a free-text location field.

    Values range from a clean `pkg/route.ts:92-115` to `a.tsx:1 and b.tsx:2` to a glob or
    a brace expansion. Returns the FIRST concrete path and flags the rest, so a multi-site
    or pattern anchor is visibly weaker evidence at match time instead of quietly matching
    on its first path as though it were precise.
    """
    if not text:
        return None, None, None, "none"
    raw = str(text)
    is_pattern = "*" in raw or "{" in raw
    paths = [p for p in _PATH_RE.findall(raw) if "/" in p or p.count(".") == 1]
    if not paths:
        # A glob is a real anchor this parser cannot resolve to one file. Saying "glob"
        # rather than "none" keeps apart "no location was recorded" and "a location
        # covering many files was".
        return None, None, None, "glob" if is_pattern else "none"
    if is_pattern:
        quality = "glob"
    elif len(paths) > 1 or " and :" in raw:
        quality = "multi"
    else:
        quality = "exact"
    head = raw[raw.index(paths[0]) + len(paths[0]):]
    start = end = None
    if head.startswith(":"):
        tail = head[1:].split()
        start, end = _split_lines(tail[0] if tail else None)
    return paths[0], start, end, quality


def _normalize(row, corpus, index):
    raw_path = _pick(row, PATH_KEYS)
    path, start, end, quality = _parse_free_anchor(raw_path)
    explicit = _pick(row, LINE_KEYS)
    if explicit is not None:
        start, end = _split_lines(explicit)
    source, channel = _norm_source(row)
    severity = _norm_severity(_pick(row, SEVERITY_KEYS))
    return {
        "id": _pick(row, ID_KEYS) or f"{corpus}-{row.get('pr')}-{row.get('idx', index)}",
        "corpus": corpus, "source": source, "channel": channel, "pr": row.get("pr"),
        "path": path, "line_start": start, "line_end": end, "anchor_quality": quality,
        "claim": _pick(row, CLAIM_KEYS) or "", "severity_raw": _pick(row, SEVERITY_KEYS),
        "severity": severity, "tier": _tier(source, severity),
        "verdict": row.get("verdict"),
    }


def _rows_of(doc):
    """Every benchmark file is either an array of findings or an object wrapping one."""
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        for key in ("findings", "results", "verdicts"):
            if isinstance(doc.get(key), list):
                return doc[key]
    return []


def _dedup_key(row):
    """Identity of a finding independent of which file it was exported in.

    `(pr, idx)` where the export numbered its findings, otherwise the anchor plus a claim
    prefix. This is what lets subsumed re-exports be detected by content instead of by a
    filename list in this file.

    Row position is deliberately not part of the key. A consolidated export numbers its
    rows differently from the per-PR files it was built from, so a key that moves with
    row order cannot see that one file covers the other — which is the entire job here.
    """
    if row.get("idx") is not None:
        return ("idx", row.get("pr"), row["idx"])
    return ("anchor", row.get("pr"), str(_pick(row, PATH_KEYS))[:120],
            str(_pick(row, LINE_KEYS)), str(_pick(row, CLAIM_KEYS))[:80])


def load_verdicts(root):
    """Return (records, notes). Notes carry every divergence worth reporting."""
    vdir = pathlib.Path(root) / "verdicts"
    if not vdir.is_dir():
        raise SystemExit(f"no verdicts/ under {root}")

    per_file, notes = {}, []
    for f in sorted(vdir.glob("*.json")):
        rows = _rows_of(json.loads(f.read_text()))
        if not rows:
            notes.append(f"SKIP {f.name} — no findings array found")
            continue
        per_file[f.name] = rows

    # Several corpora ship both a consolidated export and the per-PR files it was built
    # from. Loading both double-counts every finding in the overlap, which halves the
    # apparent FP rate. Detected by content subsumption, not by filename, so a re-export
    # under any name is still caught.
    keys = {name: {_dedup_key(r) for r in rows} for name, rows in per_file.items()}

    # Largest key set first, ties broken by name, and the test is `<=` rather than `<`.
    # A strict subset test cannot see two byte-identical exports — neither is a proper
    # subset of the other, so both load and every finding in them is counted twice.
    # Visiting supersets first is what makes `<=` safe: of two equal sets exactly one is
    # already kept by the time the other is judged.
    kept, subsumed = [], {}
    for name in sorted(keys, key=lambda n: (-len(keys[n]), n)):
        covering = next((k for k in kept if keys[name] <= keys[k]), None)
        if covering is None:
            kept.append(name)
        else:
            subsumed[name] = covering
            notes.append(f"{name}: {len(keys[name])} records subsumed by {covering} — "
                         f"excluded to avoid double counting")

    records = []
    for name in sorted(kept):
        corpus = pathlib.Path(name).stem
        records.extend(_normalize(r, corpus, i) for i, r in enumerate(per_file[name]))
        notes.append(f"{name}: {len(per_file[name])} records")

    # Whole-file subsumption cannot see a PARTIAL overlap: two corpora sharing some
    # findings but neither covering the other both load, and the intersection is counted
    # twice. Nothing downstream can spot it — ids are built from the corpus stem, so the
    # duplicates get distinct ids, inflate the denominators, narrow the Wilson intervals
    # and surface in unmatched_frozen as findings the run "failed to reproduce". So the
    # arithmetic is re-checked against what actually loaded rather than assumed.
    loaded = sum(len(per_file[n]) for n in kept)
    distinct = len({k for n in kept for k in keys[n]})
    if distinct != loaded:
        notes.append(f"WARNING partition check failed: {loaded} records loaded but only "
                     f"{distinct} distinct findings — {loaded - distinct} are duplicates "
                     f"across the kept files. Every rate below is computed on an inflated "
                     f"denominator.")
    return records, notes


def _escaped_text(row):
    parts = [row.get("symptom"), row.get("root_cause"), row.get("the_incidental_defect"),
             row.get("evidence_quote"), row.get("defect_class")]
    return " ".join(p for p in parts if p)


def _escaped_pr(row):
    ticket = row.get("ticket") or ""
    m = _TICKET_PR_RE.search(ticket) or _TICKET_ISSUE_RE.search(ticket)
    return int(m.group(1)) if m else None


def load_escaped(root):
    """Escaped defects from sessions_*.json — defects that shipped and were fixed later."""
    sdir = pathlib.Path(root) / "sessions"
    if not sdir.is_dir():
        raise SystemExit(f"no sessions/ under {root}")
    records, notes = [], []
    for f in sorted(sdir.glob("sessions_*.json")):
        rows = json.loads(f.read_text())
        if not isinstance(rows, list):
            notes.append(f"SKIP {f.name} — not an array of defects")
            continue
        for i, row in enumerate(rows):
            text = _escaped_text(row)
            paths = [p for p in _PATH_RE.findall(row.get("file_hint") or "") if "." in p]
            records.append({
                # Content-addressed so the held-out split survives a re-export that
                # reorders rows; the index only breaks ties on identical text.
                "id": hashlib.sha1(f"{f.name}|{text or i}".encode()).hexdigest()[:16],
                "corpus": f.stem, "defect_class": row.get("defect_class"),
                "diff_visible": (row.get("would_a_diff_show_it") or "").lower(),
                "text": text, "paths": paths, "pr": _escaped_pr(row),
                "file_hint": row.get("file_hint") or "",
            })
        notes.append(f"{f.name}: {len(rows)} defects")
    dupes = len(records) - len({r["id"] for r in records})
    if dupes:
        notes.append(f"WARNING {dupes} escaped defects share a content fingerprint")
    return records, notes


def load_gold(root):
    """Blind third-review findings — the only recall ground truth with real anchors.

    Shipped two ways: a flat findings array, and PRs each holding their own findings.
    Both are read; the mechanism is the same normaliser as the verdicts.
    """
    sdir = pathlib.Path(root) / "sessions"
    records, notes = [], []
    for f in sorted(sdir.glob("*goldstandard*.json")):
        doc = json.loads(f.read_text())
        corpus = f.stem
        rows = []
        for pr in doc.get("prs", []) if isinstance(doc, dict) else []:
            for row in pr.get("findings", []):
                rows.append({**row, "pr": pr.get("pr")})
        rows = rows or _rows_of(doc)
        for i, row in enumerate(rows):
            # `locations` is a list of free-text anchors; take the first and mark the
            # rest, exactly as a multi-path `file` field is handled.
            locs = row.get("locations") or []
            row = dict(row)
            if locs and not _pick(row, PATH_KEYS):
                row["file"] = locs[0]
            # A blind reviewer's title is terse; the mechanism paragraph is where the
            # identifiers live, and identifiers are what the matcher runs on.
            row["title"] = " ".join(filter(None, [row.get("title"), row.get("mechanism")]))
            rec = _normalize(row, corpus, i)
            rec["source"] = "gold"
            rec["tier"] = _tier("gold", rec["severity"])
            rec["verdict"] = None
            if len(locs) > 1:
                rec["anchor_quality"] = "multi"
            records.append(rec)
        notes.append(f"{f.name}: {len(rows)} findings")
    return records, notes
