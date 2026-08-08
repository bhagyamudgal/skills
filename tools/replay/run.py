#!/usr/bin/env python3
"""Replay /review-pr non-interactively against a recorded PR and capture its findings as JSON.

The skill emits findings as the labelled text block in
`skills/review-pr/references/finding-output-format.md`, not as JSON, so this parses that
block out of the streamed transcript. That coupling is deliberate: the format file is the
one place the shape is defined, and a second JSON emitter in the skill would be a second
shape to keep in sync.

Three properties this harness must have, in order:

1. **It never writes to a real PR.** The skill's Phase 4 posts reviews through `gh`, and
   a benchmark run that comments on someone's PR is an incident, not a measurement. The
   denylist, an allowlist that grants no write path, and the appended system prompt each
   block it, and the run is also never in a position to answer the post prompt.
2. **It can read one.** Phase 1's `gh pr view` / `gh pr diff` need permission that `-p`
   has no way to obtain interactively, so the run grants a read-only allowlist up front
   and any refusal left over is reported as a refusal — never as an empty review.
3. **It is reproducible.** Replay MERGED or CLOSED PRs. An open PR's head moves, so the
   run scores against a commit the frozen verdicts were never adjudicated on. `--sha` is
   recorded in the output so a scored run always states what it read.

Exit codes: 0 findings parsed, 1 none parsed, 2 the CLI failed or timed out, 3 a tool
call the harness meant to allow was refused.

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

# Enough of a refused command to recognise which one it was.
DENIAL_LABEL = 120

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
# correct trade for a harness pointed at real PRs. Write/Edit are denied at the tool
# level: nothing in a measurement needs to change the checkout it is measuring, and a
# deny rule is the only guard that survives an operator whose own settings allow them.
# AskUserQuestion is denied for a different reason: there is no human, so the skill's
# checkpoints cannot be answered. Denying it says so where GUARD only asks nicely, and
# keeps a checkpoint out of the refusal bucket that means "the harness is misconfigured".
DENY = ["Bash(gh pr review:*)", "Bash(gh pr comment:*)", "Bash(gh pr edit:*)",
        "Bash(gh api:*)", "Bash(gh issue create:*)", "Bash(gh issue comment:*)",
        "Bash(git push:*)", "Write", "Edit", "NotebookEdit", "AskUserQuestion"]

# The skill's whole read path: Phase 1's two `gh` calls, the local reads that follow, and
# the subagents it dispatches. In `-p` there is nobody to approve a prompt, so anything
# not granted here comes back "This command requires approval" — which for Phase 1 ends
# the review before it starts and scores as "this PR had no findings".
#
# An allowlist rather than `--permission-mode bypassPermissions`: bypass would also work,
# and would hand the run write access to the checkout and to every `gh` subcommand the
# deny list does not happen to name. A measurement must not be able to modify what it
# measures, and enumerating what a review may READ is bounded in a way that enumerating
# everything it must not WRITE is not.
#
# The dispatch tool is granted under both names it has carried: `Task` in older CLI
# builds, `Agent` in the installed one. The skill is built on subagents, so getting this
# name wrong denies every one of them — and a rule naming a tool that does not exist in a
# given build costs nothing.
#
# `bash -c` is deliberately absent even though the skill's reusability search wraps its
# globs in it: granting it grants arbitrary shell, which is the write access the rest of
# this list exists to withhold. That search degrades and says so, which is the trade.
#
# That reasoning does not fully survive the list it introduces, and saying so here is
# cheaper than discovering it later. `sed -i` writes in place, `find` takes `-delete` and
# `-exec`, and `xargs` runs whatever it is piped — each is a shell the `bash -c` rule was
# written to refuse, reached by another name. They stay because the skill uses all three
# for reads and removing them degrades the review more than the residual risk warrants;
# what changes is the claim. This list withholds every *intended* write path and is not a
# sandbox: it stops a review that means to post from posting, not a review that has been
# argued into `sed -i`.
#
# So: run replays against a throwaway clone, never a working tree you care about. The
# reproducibility rule already points this at merged PRs, where there is nothing live to
# damage; this is the same discipline for the local side.
ALLOW = ["Read", "Grep", "Glob", "Agent", "Task", "Skill", "TodoWrite",
         "Bash(gh pr view:*)", "Bash(gh pr diff:*)", "Bash(gh pr list:*)",
         "Bash(gh pr checks:*)", "Bash(gh issue view:*)", "Bash(gh issue list:*)",
         "Bash(gh repo view:*)", "Bash(git log:*)", "Bash(git diff:*)",
         "Bash(git show:*)", "Bash(git status:*)", "Bash(git blame:*)",
         "Bash(git rev-parse:*)", "Bash(git ls-files:*)", "Bash(git merge-base:*)",
         "Bash(jq:*)", "Bash(grep:*)", "Bash(rg:*)", "Bash(find:*)", "Bash(awk:*)",
         "Bash(sed:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(wc:*)", "Bash(sort:*)",
         "Bash(uniq:*)", "Bash(cat:*)", "Bash(ls:*)", "Bash(xargs:*)"]

# `dontAsk` is the only mode that states the headless contract outright: never prompt,
# refuse whatever ALLOW does not cover. The default mode reaches the same place by way of
# a prompt nobody can answer, which is a behaviour to inherit rather than to declare.
PERMISSION_MODE = "dontAsk"

EXIT_OK = 0
EXIT_NO_FINDINGS = 1
EXIT_CLI_ERROR = 2
EXIT_PERMISSION_REFUSED = 3

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


def _segments(command):
    """The pieces a shell would run, so a prefix rule sees each one on its own.

    The CLI records the command as typed, and the skill pipes and chains freely
    (`gh pr diff … | head -200`). Matching a prefix against the whole string files a
    denial of `cd . && gh pr comment …` as something nobody asked to deny — turning the
    guard doing its job into a reported harness failure.
    """
    return [s.strip() for s in re.split(r"&&|\|\||[;|\n]", command) if s.strip()]


def _rule_covers(rule, tool_name, command):
    """Does a permission rule such as `Bash(gh pr review:*)` or `Write` cover this call?"""
    name, sep, pattern = rule.partition("(")
    if name != tool_name:
        return False
    # A rule with no argument (`Write`) covers the whole tool. `Tool()` covers nothing —
    # an empty pattern read as "matches everything" would file every refusal as expected
    # and silence the exit code for good.
    if not sep:
        return True
    pattern = pattern.rstrip(")").removesuffix(":*").strip()
    return bool(pattern) and any(s.startswith(pattern) for s in _segments(command))


def classify_denials(denials, deny=DENY):
    """Split refused tool calls into the ones this harness asked for and the rest.

    A denial the deny list explains is the guard doing its job: the skill reached for its
    posting path and was stopped. Any other denial is the run being refused something it
    was meant to have — a machine that grants nothing, a rule the operator added, a read
    command outside ALLOW. That has to stay separable from a review that ran to the end
    and found nothing, because both otherwise arrive as an empty findings list.

    A denial this cannot attribute — a wrapped command a prefix rule does not recognise —
    counts as a refusal. Over-reporting is recoverable by reading the run; under-reporting
    is the failure mode being fixed.
    """
    expected, unexpected = [], []
    for denial in denials:
        tool = denial.get("tool_name") or ""
        payload = denial.get("tool_input") or {}
        command = payload.get("command") or ""
        # A denial has to name something even when the CLI's payload shape moves, or the
        # one line the operator reads says "First:" and then nothing.
        detail = command or payload.get("description") or ""
        label = f"{tool}({detail})" if detail else (tool or "unnamed tool call")
        bucket = expected if any(_rule_covers(r, tool, command) for r in deny) \
            else unexpected
        bucket.append(label[:DENIAL_LABEL])
    return expected, unexpected


def build_command(pr_url, budget, model):
    """The full invocation, in one place so a test can assert what the run may do.

    Whether a benchmark run can write to the repo it is reviewing should be readable and
    testable on its own, not reconstructed from the arguments of a subprocess call.
    """
    cmd = ["claude", "-p", f"/review-pr {pr_url}",
           "--output-format", "stream-json", "--verbose",
           "--max-budget-usd", str(budget),
           "--append-system-prompt", GUARD,
           "--permission-mode", PERMISSION_MODE,
           "--allowedTools", *ALLOW,
           "--disallowed-tools", *DENY]
    if model:
        cmd += ["--model", model]
    return cmd


def stream(cmd, cwd, timeout):
    """Run the CLI, returning (assistant_text, cost_usd, seconds, denials, error).

    Refused tool calls are collected rather than left in the transcript: they are the one
    signal that separates "the review was not allowed to read the PR" from "the review
    read the PR and found nothing", and both otherwise print as zero findings.

    stderr is captured rather than discarded: when the CLI dies before emitting a single
    event, stderr holds the only statement of why, and a harness that throws it away
    reports an auth failure or a bad flag as "this PR had no findings".
    """
    chunks, denials, cost, started = [], [], 0.0, time.time()
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
                    # Every result event, not just the last: a subagent's refusals arrive
                    # in its own result event and the parent's final one lists none. The
                    # skill runs most of the review inside subagents, so reading only the
                    # last event would miss almost every refusal there is to see.
                    denials.extend(event.get("permission_denials") or [])
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
    return "\n".join(chunks), cost, time.time() - started, denials, error


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

    cmd = build_command(args.pr, args.budget, args.model)
    text, cost, secs, denials, err = stream(cmd, str(pathlib.Path(args.repo).expanduser()),
                                            args.timeout)
    findings, dropped = parse_findings(text, pr_number)
    blocked, refused = classify_denials(denials)
    payload = {
        "pr": pr_number, "pr_url": args.pr, "sha": args.sha, "model": args.model,
        "cost_usd": round(cost, 4), "seconds": round(secs, 1), "error": err,
        "permissions": {"blocked_by_policy": blocked, "refused": refused},
        "unparsed": dropped, "findings": findings,
    }
    pathlib.Path(args.out).write_text(json.dumps(payload, indent=2))
    if args.transcript:
        pathlib.Path(args.transcript).write_text(text)

    print(f"pr={pr_number} findings={len(findings)} "
          f"unparsed_blocks={dropped['blocks']} "
          f"orphan_fields={dropped['orphan_fields']} "
          f"blocked_by_policy={len(blocked)} refused={len(refused)} "
          f"cost=${cost:.2f} {secs:.0f}s {err or ''}")
    if err:
        return EXIT_CLI_ERROR
    if refused:
        print(f"PERMISSION REFUSED — {len(refused)} tool call(s) the harness meant to "
              f"allow were denied, so this run saw less of the PR than it should have. "
              f"First: {refused[0]}")
    if not findings:
        # Refusal gets its own code because the alternative is the failure this harness
        # exists to catch: a run never allowed to read the PR reporting the same empty
        # findings list as a run that read it and found nothing. With findings in hand
        # the run is still worth scoring, so the refusal is a printed warning instead of
        # a discarded result.
        return EXIT_PERMISSION_REFUSED if refused else EXIT_NO_FINDINGS
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
