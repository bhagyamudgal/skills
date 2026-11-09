#!/usr/bin/env python3
"""Render every GitHub body a /review-pr run posts from one review JSON file.

Writes summary.md, line_comments.json, file_level.json, monolithic.md and ids.json
into a new --out directory, and exits 2 with one line per problem on stderr when
the input breaks the schema. Run with --example to print a valid input file.
"""

import argparse
import json
import os
import pathlib
import re
import sys
import tempfile

SEVERITIES = ["Critical", "Serious", "Moderate", "Minor"]
SEVERITY_EMOJI = {"Critical": "🔴", "Serious": "🟠", "Moderate": "🟡", "Minor": "🔵"}
SEVERITY_PREFIX = {"Critical": "C", "Serious": "S", "Moderate": "M", "Minor": "m"}
VERDICT_EMOJI = {"approve": "✅", "request-changes": "❌"}
ORIGINS = ["introduced", "pre-existing"]
FINDING_REQUIRED = ["finding_id", "severity", "category", "issue", "explanation", "why", "fix", "inverse_risk", "class_sites"]
RESOLVED_REQUIRED = ["label", "location", "issue", "round", "commit"]
BLOCKER_REQUIRED = ["path", "author", "issue"]
FORBIDDEN_DASHES = ["\u2014", "\u2013"]
MARKER_PREFIX = "review-pr:"
GITHUB_BODY_LIMIT = 65536
DETAILS_IN_COMMENTS = "*Details in review comments below.*"
DETAILS_BELOW = "*Details below.*"

EXAMPLE = {
    "verdict": "request-changes",
    "senior_approval": {"approved": False, "reason": "The import drops rows whose country cell is blank."},
    "goal": "Import client workbooks without inventing address values.",
    "summary": "The parser and writer are sound. One branch still writes a placeholder country.",
    "findings": [
        {
            "finding_id": "3f2a9c1d7e",
            "severity": "Serious",
            "category": "Intent",
            "file": "apps/backend/src/import/address.ts",
            "line": 42,
            "issue": "A blank country cell falls back to a hardcoded country.",
            "explanation": "The fallback runs before the account country lookup, so the account default never applies.",
            "why": "Clients outside that country get a wrong delivery address.",
            "fix": "Move the account country lookup ahead of the fallback.",
            "inverse_risk": "none, pure reorder",
            "class_sites": "1/3",
            "origin": "introduced",
        }
    ],
    "blockers": [],
    "resolved": [],
}

ENTRY_SHAPES = {
    "blockers": {"path": "apps/backend/src/import/address.ts", "line": 12, "author": "reviewer-login", "issue": "Postcode is still trimmed twice."},
    "resolved": {"label": "S2", "location": "address.ts:18", "issue": "missing null check", "round": 1, "commit": "abc1234"},
}


def unquote_path(path):
    path = path.split("\t")[0]
    if len(path) >= 2 and path[0] == '"' and path[-1] == '"':
        inner = path[1:-1].encode("latin-1", "backslashreplace").decode("unicode_escape")
        return inner.encode("latin-1", "replace").decode("utf-8", "replace")
    return path


def strip_prefix(path, prefix):
    return path[len(prefix):] if path.startswith(prefix) else path


def parse_diff(diff_text):
    files = {}
    current = None
    expect_new_header = False
    old_left = new_left = counter = 0
    for raw in diff_text.split("\n"):
        line = raw[:-1] if raw.endswith("\r") else raw
        if old_left > 0 or new_left > 0:
            tag = line[:1]
            if tag == "\\":
                continue
            if tag == "+":
                files[current].add(counter)
                counter += 1
                new_left -= 1
                continue
            if tag == "-":
                old_left -= 1
                continue
            if tag in (" ", ""):
                files[current].add(counter)
                counter += 1
                new_left -= 1
                old_left -= 1
                continue
            old_left = new_left = 0
        if line.startswith("diff --git "):
            current = None
            expect_new_header = False
            target = line.rsplit(" b/", 1)
            if len(target) == 2:
                current = unquote_path(target[1])
                files.setdefault(current, set())
            continue
        if line.startswith("rename to "):
            current = unquote_path(line[len("rename to "):])
            files.setdefault(current, set())
            continue
        if line.startswith("--- "):
            expect_new_header = True
            continue
        if line.startswith("+++ ") and expect_new_header:
            expect_new_header = False
            target = unquote_path(line[4:])
            if target != "/dev/null":
                current = strip_prefix(target, "b/")
                files.setdefault(current, set())
            continue
        hunk = re.match(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
        if hunk and current is not None:
            old_left = int(hunk.group(1)) if hunk.group(1) is not None else 1
            counter = int(hunk.group(2))
            new_left = int(hunk.group(3)) if hunk.group(3) is not None else 1
    return files


def is_text(value):
    return isinstance(value, str) and value.strip() != ""


def outside_code(text):
    return re.sub(r"`[^`]*`", "", text)


def text_fields(review):
    approval = review.get("senior_approval") or {}
    yield "goal", review.get("goal")
    yield "summary", review.get("summary")
    yield "senior_approval.reason", approval.get("reason")
    for index, finding in enumerate(review.get("findings") or []):
        for field in ["category", "issue", "explanation", "why", "fix", "inverse_risk", "class_sites", "blame"]:
            yield f"findings[{index}].{field}", finding.get(field)
    for index, blocker in enumerate(review.get("blockers") or []):
        for field in ["author", "issue"]:
            yield f"blockers[{index}].{field}", blocker.get(field)
    for index, item in enumerate(review.get("resolved") or []):
        for field in ["location", "issue"]:
            yield f"resolved[{index}].{field}", item.get(field)


def marker_paths(value, path="review"):
    if isinstance(value, str):
        return [path] if MARKER_PREFIX in value else []
    if isinstance(value, dict):
        return [hit for key, item in value.items() for hit in marker_paths(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [hit for index, item in enumerate(value) for hit in marker_paths(item, f"{path}[{index}]")]
    return []


def is_line(value):
    return value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 1)


def is_introduced(finding):
    return finding.get("origin", "introduced") == "introduced"


def finding_problems(index, finding):
    label = f"findings[{index}]"
    problems = [f"{label}.{field} is required" for field in FINDING_REQUIRED if not is_text(finding.get(field))]
    if is_text(finding.get("finding_id")) and not re.fullmatch(r"[0-9a-f]{10}", finding["finding_id"]):
        problems.append(f"{label}.finding_id must be the 10-hex state ID from finding-state-schema.md")
    if finding.get("severity") not in SEVERITIES:
        problems.append(f"{label}.severity must be one of {SEVERITIES}")
    if finding.get("origin", "introduced") not in ORIGINS:
        problems.append(f"{label}.origin must be one of {ORIGINS}")
    if not is_line(finding.get("line")):
        problems.append(f"{label}.line must be a whole number of at least 1, or null")
    if finding.get("line") is not None and not is_text(finding.get("file")):
        problems.append(f"{label} has a line but no file")
    if finding.get("origin") == "pre-existing" and not is_text(finding.get("blame")):
        problems.append(f"{label} is pre-existing and needs blame (short commit SHA)")
    if "\n" in str(finding.get("issue", "")):
        problems.append(f"{label}.issue must be one line")
    return problems


def verdict_problems(review):
    findings = review.get("findings") or []
    introduced = any(is_introduced(finding) for finding in findings)
    blockers = review.get("blockers") or []
    verdict = review.get("verdict")
    approved = (review.get("senior_approval") or {}).get("approved")
    problems = []
    if introduced and verdict != "request-changes":
        problems.append("verdict must be request-changes while any introduced finding survives")
    if blockers and introduced:
        problems.append("blockers apply only when no introduced finding survives")
    if blockers and verdict != "request-changes":
        problems.append("verdict must be request-changes while blockers are listed")
    if not introduced and not blockers and verdict != "approve":
        problems.append("verdict must be approve when no introduced finding or blocker remains")
    if approved is True and (introduced or blockers):
        problems.append("senior_approval.approved must be false while a finding or blocker remains")
    return problems


def validate(review):
    if not isinstance(review, dict):
        return ["the review file must hold one JSON object"]
    problems = [f"missing top-level field: {key}" for key in ["verdict", "senior_approval", "goal", "summary", "findings"] if key not in review]
    problems.extend(f"{key} must be non-empty text" for key in ["goal", "summary"] if key in review and not is_text(review[key]))
    problems.extend(f"{path} contains '{MARKER_PREFIX}'; only the renderer writes review-pr markers, so paraphrase the quoted text"
                    for path in marker_paths(review))
    if "_entry_shapes" in review:
        problems.append("remove _entry_shapes; it only shows the blockers and resolved entry shapes")
    if not isinstance(review.get("verdict"), str) or review.get("verdict") not in VERDICT_EMOJI:
        problems.append(f"verdict must be one of {sorted(VERDICT_EMOJI)}")
    approval = review.get("senior_approval")
    if not isinstance(approval, dict) or not isinstance(approval.get("approved"), bool) or not is_text(approval.get("reason")):
        problems.append("senior_approval needs approved (true or false) and reason")
    for key in ["findings", "blockers", "resolved"]:
        entries = review.get(key, [])
        if not isinstance(entries, list):
            problems.append(f"{key} must be a list")
            continue
        problems.extend(f"{key}[{index}] must be an object" for index, entry in enumerate(entries) if not isinstance(entry, dict))
    if problems:
        return problems
    for index, finding in enumerate(review["findings"]):
        problems.extend(finding_problems(index, finding))
    ids = [finding.get("finding_id") for finding in review["findings"]]
    problems.extend(f"finding_id {finding_id} appears more than once" for finding_id in sorted({i for i in ids if ids.count(i) > 1 and isinstance(i, str)}))
    for index, blocker in enumerate(review.get("blockers") or []):
        problems.extend(f"blockers[{index}].{field} is required" for field in BLOCKER_REQUIRED if not is_text(blocker.get(field)))
        problems.extend(f"blockers[{index}].{field} must be one line" for field in BLOCKER_REQUIRED if "\n" in str(blocker.get(field, "")))
        if not is_line(blocker.get("line")):
            problems.append(f"blockers[{index}].line must be a whole number of at least 1, or null")
    for index, item in enumerate(review.get("resolved") or []):
        problems.extend(f"resolved[{index}].{field} is required" for field in RESOLVED_REQUIRED if item.get(field) in (None, ""))
    problems.extend(verdict_problems(review))
    problems.extend(f"{name} contains an em or en dash outside backticks; use a period or a comma"
                    for name, text in text_fields(review)
                    if isinstance(text, str) and any(dash in outside_code(text) for dash in FORBIDDEN_DASHES))
    return problems


def assign_labels(findings):
    ordered = sorted(enumerate(findings), key=lambda item: (
        not is_introduced(item[1]), SEVERITIES.index(item[1]["severity"]), item[0]))
    counters = {severity: 0 for severity in SEVERITIES}
    labelled = []
    for _, finding in ordered:
        counters[finding["severity"]] += 1
        labelled.append({**finding, "label": f"{SEVERITY_PREFIX[finding['severity']]}{counters[finding['severity']]}"})
    return labelled


def route(finding, diff_files, body_only):
    path = finding.get("file")
    if body_only or not path or path not in diff_files:
        return "body"
    if finding.get("line") in diff_files[path]:
        return "line"
    return "file"


def location(finding):
    if not finding.get("file"):
        return "*(general)*"
    if finding.get("line") is not None:
        return f"`{finding['file']}:{finding['line']}`"
    return f"`{finding['file']}`"


def cell(text):
    return str(text).replace("|", "\\|")


def badges(findings):
    introduced = [finding for finding in findings if is_introduced(finding)]
    parts = [f"{SEVERITY_EMOJI[severity]} {count} {severity}"
             for severity in SEVERITIES
             if (count := sum(1 for finding in introduced if finding["severity"] == severity))]
    if len(findings) > len(introduced):
        parts.append(f"⚪ {len(findings) - len(introduced)} Pre-existing")
    return " · ".join(parts) if parts else "No findings"


def finding_table(findings):
    rows = []
    for finding in findings:
        severity = SEVERITY_EMOJI[finding["severity"]] + ("" if is_introduced(finding) else " pre-existing")
        rows.append(f"| {finding['label']} | {severity} | {location(finding)} | {cell(finding['issue'])} |")
    return "\n".join(["| # | Sev | File | Issue |", "|---|-----|------|-------|"] + rows)


def comment_body(finding):
    header = f"{SEVERITY_EMOJI[finding['severity']]} **{finding['severity']}** · {finding['category']}"
    parts = [header + ("" if is_introduced(finding) else " · Pre-existing")]
    if not is_introduced(finding):
        parts.append(f"This line predates the PR (blame {finding['blame']}), so it does not block this review. It gets its own issue.")
    parts.extend([
        f"**{finding['issue']}**",
        finding["explanation"],
        f"**Why it matters**: {finding['why']}",
        f"**Suggested fix**: {finding['fix']}",
        f"**Inverse risk**: {finding['inverse_risk']}",
        f"**Class-sites**: {finding['class_sites']}",
    ])
    if not is_introduced(finding):
        parts.append("<!-- review-pr:origin=pre-existing -->")
    return "\n\n".join(parts)


def blocker_table(blockers):
    rows = [f"| `{blocker['path']}{':' + str(blocker['line']) if blocker.get('line') else ''}` | {cell(blocker['author'])} | {cell(blocker['issue'])} |"
            for blocker in blockers]
    return "\n".join(["| Location | Author | Issue |", "|---|---|---|"] + rows)


def findings_section(review, routed, details_line):
    introduced = [finding for finding, _ in routed if is_introduced(finding)]
    pre_existing = [finding for finding, _ in routed if not is_introduced(finding)]
    blockers = review.get("blockers") or []
    sections = ["### Findings"]
    if introduced:
        sections.append(finding_table(introduced))
    elif blockers:
        sections.append("No new findings. These open threads still block this PR:\n\n" + blocker_table(blockers))
    else:
        sections.append("No findings.")
    if pre_existing:
        sections.append("### Pre-existing\n\n" + finding_table(pre_existing))
    if details_line and any(tier != "body" for _, tier in routed):
        sections.append(details_line)
    resolved = review.get("resolved") or []
    if resolved:
        items = ", ".join(f"{item['label']} (`{item['location']}` {item['issue']}, round {item['round']} commit `{item['commit']}`)"
                          for item in resolved)
        sections.append(f"**Resolved since last review**: {items} *(threads resolved)*")
    body_only = [finding for finding, tier in routed if tier == "body"]
    if body_only:
        sections.append("### Additional findings\n\n" + "\n\n---\n\n".join(
            f"**{finding['label']}** {location(finding)}\n\n{comment_body(finding)}" for finding in body_only))
    return "\n\n".join(sections)


def summary_body(review, routed, meta, details_line):
    approval = review["senior_approval"]
    verdict = review["verdict"]
    head = [
        f"<!-- review-pr:run sha={meta['head_sha']} round={meta['round']} -->",
        f"## PR Review: #{meta['pr']}",
        f"{VERDICT_EMOJI[verdict]} {verdict} | {badges([finding for finding, _ in routed])}",
        f"**Senior engineer approval**: {'✅ Yes' if approval['approved'] else '❌ No'}, {approval['reason']}",
    ]
    lead = f"**Goal**: {review['goal']}\n**Summary**: {review['summary']}"
    return "\n".join(head) + "\n\n" + lead + "\n\n" + findings_section(review, routed, details_line)


def monolithic_body(review, routed, meta):
    summary = summary_body(review, routed, meta, DETAILS_BELOW)
    details = [f"**{finding['label']}** {location(finding)}\n\n{comment_body(finding)}"
               for finding, tier in routed if tier != "body"]
    if not details:
        return summary
    return summary + "\n\n### Finding details\n\n" + "\n\n---\n\n".join(details)


def render(review, diff_text, meta):
    diff_files = parse_diff(diff_text)
    body_only = bool(review.get("blockers"))
    routed = [(finding, route(finding, diff_files, body_only)) for finding in assign_labels(review.get("findings") or [])]
    return {
        "summary.md": summary_body(review, routed, meta, DETAILS_IN_COMMENTS),
        "line_comments.json": [{"path": finding["file"], "line": finding["line"], "side": "RIGHT", "body": comment_body(finding)}
                               for finding, tier in routed if tier == "line"],
        "file_level.json": [{"finding_id": finding["finding_id"], "label": finding["label"], "path": finding["file"], "body": comment_body(finding)}
                            for finding, tier in routed if tier == "file"],
        "monolithic.md": monolithic_body(review, routed, meta),
        "ids.json": [{"finding_id": finding["finding_id"], "label": finding["label"], "tier": tier,
                      "file": finding.get("file"), "line": finding.get("line")} for finding, tier in routed],
    }


def demotions(outputs):
    return [f"{entry['label']} {entry['file']}:{entry['line']} is not on the diff's post-image side; posting it as {entry['tier']}"
            for entry in outputs["ids.json"] if entry.get("line") is not None and entry["tier"] != "line"]


def size_problems(outputs):
    bodies = [("summary.md", outputs["summary.md"])]
    bodies += [(f"line_comments.json[{index}]", entry["body"]) for index, entry in enumerate(outputs["line_comments.json"])]
    bodies += [(f"file_level.json[{index}]", entry["body"]) for index, entry in enumerate(outputs["file_level.json"])]
    return [f"{name} is over GitHub's {GITHUB_BODY_LIMIT}-character limit" for name, body in bodies if len(body) > GITHUB_BODY_LIMIT]


def write_outputs(outputs, out_dir):
    out = pathlib.Path(out_dir)
    staging = pathlib.Path(tempfile.mkdtemp(prefix=f".{out.name}.", dir=out.parent))
    for name, content in outputs.items():
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2) + "\n"
        (staging / name).write_text(text, encoding="utf-8")
    os.rename(staging, out)


def read_inputs(review_path, diff_path):
    try:
        review = json.loads(pathlib.Path(review_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, None, [f"cannot read {review_path}: {error}"]
    try:
        diff_text = pathlib.Path(diff_path).read_bytes().decode("utf-8", "replace")
    except OSError as error:
        return None, None, [f"cannot read {diff_path}: {error}"]
    return review, diff_text, []


def meta_problems(args):
    problems = []
    if args.pr < 1:
        problems.append("--pr must be a PR number of at least 1")
    if args.round < 1:
        problems.append("--round must be at least 1")
    if not re.fullmatch(r"[0-9a-f]{40}", args.head_sha):
        problems.append("--head-sha must be the full 40-character commit SHA")
    if pathlib.Path(args.out).exists():
        problems.append(f"--out {args.out} already exists; render into a new directory")
    if not pathlib.Path(args.out).parent.is_dir():
        problems.append(f"--out parent directory {pathlib.Path(args.out).parent} does not exist")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("review", nargs="?", help="review JSON file")
    parser.add_argument("--diff", help="the staged diff.full.patch, used to route findings to line, file or body")
    parser.add_argument("--out", help="new directory for the rendered files")
    parser.add_argument("--pr", type=int, help="PR number")
    parser.add_argument("--head-sha", help="the pinned head commit SHA")
    parser.add_argument("--round", type=int, help="CURRENT_ROUND from Phase 1")
    parser.add_argument("--example", action="store_true", help="print a valid input file and exit")
    args = parser.parse_args(argv)
    if args.example:
        print(json.dumps({**EXAMPLE, "_entry_shapes": ENTRY_SHAPES}, ensure_ascii=False, indent=2))
        return 0
    if None in (args.review, args.diff, args.out, args.pr, args.head_sha, args.round):
        parser.error("review, --diff, --out, --pr, --head-sha and --round are required")
    review, diff_text, problems = read_inputs(args.review, args.diff)
    problems = problems or (meta_problems(args) + validate(review))
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 2
    outputs = render(review, diff_text, {"pr": args.pr, "head_sha": args.head_sha, "round": args.round})
    problems = size_problems(outputs)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 2
    for warning in demotions(outputs):
        print(warning, file=sys.stderr)
    if len(outputs["monolithic.md"]) > GITHUB_BODY_LIMIT:
        print(f"monolithic.md is over GitHub's {GITHUB_BODY_LIMIT}-character limit; a monolithic post of it would be rejected", file=sys.stderr)
    write_outputs(outputs, args.out)
    tiers = [entry["tier"] for entry in outputs["ids.json"]]
    print(json.dumps({tier: tiers.count(tier) for tier in ["line", "file", "body"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
