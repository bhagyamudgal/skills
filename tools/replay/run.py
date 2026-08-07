#!/usr/bin/env python3
"""Replay /review-pr non-interactively against a recorded PR and capture its findings as JSON.

The skill emits findings as the labelled text block in
`skills/review-pr/references/finding-output-format.md`, not as JSON, so this parses that
block out of the streamed transcript. That coupling is deliberate: the format file is the
one place the shape is defined, and a second JSON emitter in the skill would be a second
shape to keep in sync.

Two properties this harness must have, in order:

1. **It never writes to a real PR.** The skill's Phase 4 posts reviews through `gh`, and
   a benchmark run that comments on someone's PR is an incident, not a measurement. Both
   the tool denylist and the appended system prompt block it, and the run is also never
   in a position to answer the post prompt.
2. **It is reproducible.** Replay MERGED or CLOSED PRs. An open PR's head moves, so the
   run scores against a commit the frozen verdicts were never adjudicated on. `--sha` is
   recorded in the output so a scored run always states what it read.

Usage:
    python3 tools/replay/run.py --pr https://github.com/o/r/pull/123 --out run.json
    python3 tools/replay/run.py --pr <url> --sha <merge-sha> --budget 8.0 --out run.json
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import threading
import time

# Enough of the child's stderr to name the failure, without pasting a whole traceback
# into a one-line status.
STDERR_TAIL = 400

FIELDS = {
    "severity": "severity", "confidence": "confidence", "file": "file",
    "category": "category", "rule-class": "rule_class",
    "enclosing-symbol": "enclosing_symbol", "issue": "claim",
    "why it matters": "why", "suggested fix": "fix", "inverse risk": "inverse_risk",
    "class-sites": "class_sites",
}
_FIELD_RE = re.compile(r"^\s*(" + "|".join(re.escape(k) for k in FIELDS) + r")\s*:\s*(.*)$",
                       re.IGNORECASE)

# Phase 4's posting path runs through `gh pr review` / `gh pr comment` and raw `gh api`
# calls. Denying `gh api` wholesale costs the skill a few GraphQL reads; that is the
# correct trade for a harness pointed at real PRs.
DENY = ["Bash(gh pr review:*)", "Bash(gh pr comment:*)", "Bash(gh pr edit:*)",
        "Bash(gh api:*)", "Bash(gh issue create:*)", "Bash(gh issue comment:*)",
        "Bash(git push:*)"]

GUARD = (
    "You are running inside a non-interactive benchmark harness. Do NOT post, comment, "
    "review, or otherwise write anything to GitHub or to any remote — produce findings "
    "only. There is no human to answer AskUserQuestion: when the skill offers a choice, "
    "take the option that continues the review without posting, and state which you took."
)


def parse_findings(text, pr):
    """Pull labelled finding blocks out of the transcript.

    A `Severity:` line opens a block; the fields that follow attach to it until the next
    one. Blocks without a severity and either a file or an issue are dropped as prose
    that happened to contain a colon — every drop is counted, because a parser that
    silently loses findings understates the run instead of failing loudly. That includes
    field lines arriving before any `Severity:` has opened a block: they belong to a
    finding whose severity line the transcript lost, which is exactly the case worth
    knowing about.
    """
    findings, current, orphans = [], None, 0
    for line in text.splitlines():
        m = _FIELD_RE.match(line)
        if not m:
            continue
        key = FIELDS[m.group(1).lower()]
        value = m.group(2).strip()
        if key == "severity":
            if current:
                findings.append(current)
            current = {"pr": pr}
        if current is None:
            orphans += 1
            continue
        if value:
            current.setdefault(key, value)
    if current:
        findings.append(current)

    kept = []
    for i, f in enumerate(findings):
        if not f.get("severity") or not (f.get("file") or f.get("claim")):
            continue
        raw = f.pop("file", None) or ""
        path, _, line = raw.partition(":")
        f["id"] = f"replay-{pr}-{i}"
        f["path"] = path.strip() or None
        f["line"] = int(line.strip()) if line.strip().isdigit() else None
        f["source"] = "review-pr-skill"
        kept.append(f)
    return kept, {"blocks": len(findings) - len(kept), "orphan_fields": orphans}


def stream(cmd, cwd, timeout):
    """Run the CLI, returning (assistant_text, cost_usd, seconds, error).

    stderr is captured rather than discarded: when the CLI dies before emitting a single
    event, stderr holds the only statement of why, and a harness that throws it away
    reports an auth failure or a bad flag as "this PR had no findings".
    """
    chunks, cost, started = [], 0.0, time.time()
    timed_out = threading.Event()
    with tempfile.TemporaryFile(mode="w+") as errfile:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=errfile,
                                text=True)

        def kill_at_deadline():
            timed_out.set()
            proc.kill()

        # The deadline cannot be enforced inside the read loop. `for line in proc.stdout`
        # blocks until a line arrives, so a child that hangs without printing never
        # reaches the clock check and the timeout never fires at all.
        watchdog = threading.Timer(timeout, kill_at_deadline)
        watchdog.start()
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "assistant":
                    for c in event.get("message", {}).get("content", []):
                        if c.get("type") == "text":
                            chunks.append(c.get("text", ""))
                elif event.get("type") == "result":
                    cost = event.get("total_cost_usd", 0.0)
                    chunks.append(event.get("result") or "")
        finally:
            watchdog.cancel()
            if proc.poll() is None:
                proc.kill()
            proc.stdout.close()
            proc.wait()
        errfile.seek(0)
        stderr_text = errfile.read()

    if timed_out.is_set():
        error = "timeout"
    elif proc.returncode:
        error = f"exit {proc.returncode}: {stderr_text.strip()[-STDERR_TAIL:]}"
    else:
        error = None
    # One join for both paths. Splicing the chunks differently on the way out of a
    # timeout silently changes how the parser sees block boundaries.
    return "\n".join(chunks), cost, time.time() - started, error


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pr", required=True, help="PR URL. Prefer merged/closed PRs — an "
                                                "open PR's head moves under the benchmark")
    ap.add_argument("--sha", help="the commit this replay is scored against. Recorded in "
                                  "the output; not enforced against the live PR head")
    ap.add_argument("--repo", default=".", help="local checkout the skill runs in")
    ap.add_argument("--out", required=True, help="findings JSON, input to score.py")
    ap.add_argument("--budget", type=float, default=8.0,
                    help="per-run USD cap. A full /review-pr run dispatches several "
                         "subagents over a whole diff; the trigger eval's 0.60 cuts it "
                         "off during Phase 1 and reads as 'found nothing'.")
    ap.add_argument("--timeout", type=int, default=3600, help="seconds")
    ap.add_argument("--model", help="pin the model so runs are comparable over time")
    ap.add_argument("--transcript", help="also write the raw assistant text")
    args = ap.parse_args()

    pr_number = int(re.search(r"/pull/(\d+)", args.pr).group(1)) if "/pull/" in args.pr \
        else None
    if pr_number is None:
        ap.error(f"cannot read a PR number out of {args.pr}")

    cmd = ["claude", "-p", f"/review-pr {args.pr}",
           "--output-format", "stream-json", "--verbose",
           "--max-budget-usd", str(args.budget),
           "--append-system-prompt", GUARD,
           "--disallowed-tools", *DENY]
    if args.model:
        cmd += ["--model", args.model]

    text, cost, secs, err = stream(cmd, str(pathlib.Path(args.repo).expanduser()),
                                   args.timeout)
    findings, dropped = parse_findings(text, pr_number)
    payload = {
        "pr": pr_number, "pr_url": args.pr, "sha": args.sha, "model": args.model,
        "cost_usd": round(cost, 4), "seconds": round(secs, 1), "error": err,
        "unparsed": dropped, "findings": findings,
    }
    pathlib.Path(args.out).write_text(json.dumps(payload, indent=2))
    if args.transcript:
        pathlib.Path(args.transcript).write_text(text)

    print(f"pr={pr_number} findings={len(findings)} "
          f"unparsed_blocks={dropped['blocks']} "
          f"orphan_fields={dropped['orphan_fields']} "
          f"cost=${cost:.2f} {secs:.0f}s {err or ''}")
    if err:
        return 2
    # Zero findings from a real PR is almost always a harness failure (budget cut, an
    # unanswerable prompt, a format change) rather than a clean PR. Fail loudly.
    return 0 if findings else 1


if __name__ == "__main__":
    sys.exit(main())
