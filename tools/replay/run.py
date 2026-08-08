#!/usr/bin/env python3
"""Replay /review-pr non-interactively against a recorded PR and capture its findings as JSON.

The skill emits findings as the labelled text block in
`skills/review-pr/references/finding-output-format.md`, not as JSON, so this parses that
block out of the streamed transcript. That coupling is deliberate: the format file is the
one place the shape is defined, and a second JSON emitter in the skill would be a second
shape to keep in sync.

Four properties this harness must have, in order:

1. **It never writes to a real PR.** The skill's Phase 4 posts reviews through `gh`, and
   a benchmark run that comments on someone's PR is an incident, not a measurement. The
   denylist, an allowlist that grants no write path, and the appended system prompt each
   block it, and the run is also never in a position to answer the post prompt.
2. **It can read one.** Phase 1's `gh pr view` / `gh pr diff` need permission that `-p`
   has no way to obtain interactively, so the run grants a read-only allowlist up front
   and any refusal left over is reported as a refusal — never as an empty review.
3. **It is reproducible.** Replay MERGED or CLOSED PRs. An open PR's head moves, so the
   run scores against a commit the frozen verdicts were never adjudicated on. `--sha` is
   recorded in the output so a scored run always states what it read, and the skill
   directory that produced the review is resolved and fingerprinted into the same output.
4. **It cannot lose a review it obtained.** The parser reads one grammar; the reviewer is
   free to emit another. A review that arrives in an unparseable shape is reported as a
   format failure with its own exit code, and the text is persisted verbatim so the
   findings survive the parser that could not read them.

Exit codes: 0 findings parsed, 1 none parsed, 2 the CLI failed or timed out or is
misconfigured, 3 nothing parsed and a tool call the harness meant to allow was refused,
4 a review arrived and no part of it parsed.

Usage:
    python3 tools/replay/run.py --pr https://github.com/o/r/pull/123 --out run.json
    python3 tools/replay/run.py --pr <url> --sha <merge-sha> --budget 8.0 --out run.json
    python3 tools/replay/run.py --pr <url> --skill-dir skills/review-pr --out run.json
"""
import argparse
import hashlib
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

# The review text is kept in the output so a run survives its own format bugs, but a
# runaway transcript must not turn a findings file into something nothing will open.
# The head is what is kept: the review leads with its findings and trails into process
# notes, so a truncated tail loses the least.
RAW_REVIEW_LIMIT = 400_000

# Vocabulary the finding format owns and ordinary review prose does not. A reviewer who
# emitted findings reaches for these words whatever shape it wraps them in; a genuinely
# clean PR has no fix to suggest and no rule-class to name, so it writes none of them.
# `Severity`, `File` and `Issue` are deliberately absent — they are ordinary English and
# would fire on a clean review that merely discusses severity.
FORMAT_MARKERS = ("suggested fix", "inverse risk", "rule-class", "class-sites",
                  "why it matters")

# Both gates must trip before a run is called a format failure, and both are set where a
# clean review cannot reach them. One marker is a turn of phrase ("no suggested fix is
# needed"); two is the format's vocabulary being used. The character floor is roughly a
# page — below it there is no review to have lost, and calling a short clean run a format
# failure would be the same silent-lie defect pointed the other way.
MIN_FORMAT_MARKERS = 2
MIN_REVIEW_CHARS = 2000

# The names the dispatch tool has carried across CLI builds. Counted, not just allowed:
# the skill's reviewer phases live inside subagents, so a run that dispatched none
# answered none of the questions those phases exist to ask.
DISPATCH_TOOLS = ("Agent", "Task")

# The skill this harness measures, and where a CLI build looks for it. Project scope
# outranks user scope, which is the order the CLI itself resolves in.
SKILL_NAME = "review-pr"
SKILL_MANIFEST = "SKILL.md"

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
# Shell control flow is deliberately absent — `bash -c`, and equally `for`, `while`, `if`
# and any other construct that opens a shell. Granting any of them grants arbitrary shell,
# which is the write access the rest of this list exists to withhold. This costs real
# reads: batching line lookups as `for n in 64 151; do sed -n "${n}p" f; done` is a
# natural thing for a reviewer to reach for, and `_segments` splits it on `;` into pieces
# whose first word is `for`, matching no prefix rule. Such a loop is refused, shows up in
# `permissions.refused`, and the reviewer falls back to one command per read. That trade
# stands: a rule that admits a read-only loop admits every other loop too.
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
EXIT_FORMAT_FAILURE = 4

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


def diagnose_format(text, findings, dropped):
    """Did a review arrive that the grammar could not see any part of?

    `unparsed.blocks` and `unparsed.orphan_fields` only catch output that *almost*
    parsed — a block missing its file, a field line before its severity. Output in a
    wholly different shape trips neither, so a reviewer that emitted its findings as
    markdown headings and `**Suggested fix**:` in bold reports zero findings, zero
    unparsed blocks and zero orphans: every counter agreeing that nothing was lost.

    That case is separated from a genuinely clean PR by two gates, both of which must
    trip. Nothing parsed *at all* — one recognised field line anywhere means the grammar
    was understood and this is an ordinary parse, not a format change. And the text both
    runs long and uses the format's own vocabulary, which a clean review has no occasion
    to write.

    The gates are set to under-report on purpose. A reviewer that abandons the grammar
    *and* its vocabulary — plain JSON, or `Fix:` for `Suggested fix:` — passes this
    undetected and lands on exit 1, where the operator reads a `raw_review` that plainly
    is a review. Calling a real clean run a format failure is the worse error: it teaches
    the operator to disbelieve the signal, which is how the next real one gets waved
    through.
    """
    markers = sum(text.lower().count(marker) for marker in FORMAT_MARKERS)
    parsed_anything = bool(findings) or dropped["blocks"] or dropped["orphan_fields"]
    failure = (not parsed_anything
               and len(text) >= MIN_REVIEW_CHARS
               and markers >= MIN_FORMAT_MARKERS)
    return {"failure": failure, "markers": markers}


def raw_review(text):
    """The review as the reviewer wrote it, so a run outlives the parser that read it.

    Held under its own key and never merged into `findings`: `score.py` reads `findings`
    and would otherwise be handed prose to match against adjudicated verdicts, inventing
    a measurement out of text nobody structured. `chars` is the length before truncation,
    so a clipped review says so rather than looking short.
    """
    return {"chars": len(text), "truncated": len(text) > RAW_REVIEW_LIMIT,
            "text": text[:RAW_REVIEW_LIMIT]}


def fingerprint_skill(path):
    """Content hash of a skill directory, so a scored run states what it measured.

    Paths and bytes both, in sorted order: a renamed reference file changes the artifact
    under test as surely as an edited one, and a hash over contents alone would miss it.
    """
    digest = hashlib.sha256()
    for f in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(f.relative_to(path)).encode())
        digest.update(f.read_bytes())
    return digest.hexdigest()[:12]


def resolve_skill(repo, requested=None, name=SKILL_NAME, home=None):
    """Which skill directory the CLI will load, and whether it is the one asked for.

    `claude -p` has no flag that points a session at a skill directory — `--plugin-dir`
    takes plugins, not skills — so the run cannot pin what it measures. It can state it.
    The search order mirrors the CLI's own: project scope before user scope.

    `--skill-dir` is therefore a *claim to verify*, not an install. When it names a
    directory the CLI will not load, the run is measuring a different artifact than the
    operator asked for, and saying so before spending a review's worth of budget is the
    entire point of the check.

    `home` is a parameter so the user scope can be pointed somewhere else. Without it a
    test asserting "nothing resolves" passes or fails on whether the machine running it
    happens to have the skill installed, which is not a property of this code.
    """
    home = pathlib.Path(home) if home else pathlib.Path.home()
    candidates = [pathlib.Path(repo).expanduser() / ".claude" / "skills" / name,
                  home / ".claude" / "skills" / name]
    resolved = next((c for c in candidates if (c / SKILL_MANIFEST).is_file()), None)
    wanted = pathlib.Path(requested).expanduser().resolve() if requested else None
    return {
        "name": name,
        "requested": str(wanted) if wanted else None,
        "resolved": str(resolved.resolve()) if resolved else None,
        "fingerprint": fingerprint_skill(resolved) if resolved else None,
        "pinned": bool(wanted and resolved and resolved.resolve() == wanted),
    }


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
    """Run the CLI, returning (assistant_text, telemetry).

    Telemetry carries `cost_usd`, `seconds`, `denials`, `dispatches` and `error` in a dict
    rather than as four more positional returns, because the caller of a six-tuple writes
    `_, _, _, _, x =` and the next field added to it is dropped without a diagnostic —
    which is the shape of failure this whole module exists to make loud.

    Refused tool calls are collected rather than left in the transcript: they are the one
    signal that separates "the review was not allowed to read the PR" from "the review
    read the PR and found nothing", and both otherwise print as zero findings.

    Subagent dispatches are counted for the same reason. The skill runs its reviewer
    phases inside subagents, and a run where the dispatch tool was never exposed does the
    whole review single-pass in main — a different experiment, producing none of the
    output only a subagent writes, and otherwise indistinguishable in the JSON.

    stderr is captured rather than discarded: when the CLI dies before emitting a single
    event, stderr holds the only statement of why, and a harness that throws it away
    reports an auth failure or a bad flag as "this PR had no findings".
    """
    chunks, denials, cost, started = [], [], 0.0, time.time()
    dispatches = 0
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
                        elif c.get("type") == "tool_use" and c.get("name") in DISPATCH_TOOLS:
                            dispatches += 1
                elif event.get("type") == "result":
                    cost = event.get("total_cost_usd", 0.0)
                    # Every result event, not just the last: a subagent's refusals arrive
                    # in its own result event and the parent's final one lists none. The
                    # skill runs most of the review inside subagents, so reading only the
                    # last event would miss almost every refusal there is to see.
                    denials.extend(event.get("permission_denials") or [])
                    # The result event restates the last assistant message verbatim.
                    # Appended blind it doubles the review, and with it every finding
                    # parsed out of it — inflating the run's finding count with duplicates
                    # the matcher can only report as unmatched, which drags the match rate
                    # down and reads as a worse reviewer.
                    result_text = event.get("result") or ""
                    if result_text and result_text not in "\n".join(chunks):
                        chunks.append(result_text)
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
    return "\n".join(chunks), {"cost_usd": cost, "seconds": time.time() - started,
                               "denials": denials, "dispatches": dispatches,
                               "error": error}


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
    ap.add_argument("--skill-dir", help="the skill directory this run is meant to "
                                        "measure. Verified against the one the CLI will "
                                        "actually load, and recorded either way — the "
                                        "CLI has no flag that pins it")
    ap.add_argument("--transcript", help="also write the raw assistant text")
    args = ap.parse_args()

    pr_number = int(re.search(r"/pull/(\d+)", args.pr).group(1)) if "/pull/" in args.pr \
        else None
    if pr_number is None:
        ap.error(f"cannot read a PR number out of {args.pr}")

    repo = str(pathlib.Path(args.repo).expanduser())
    skill = resolve_skill(repo, args.skill_dir)
    if args.skill_dir and not skill["pinned"]:
        # Before the budget, not after: a run that measures the published skill while the
        # operator is testing a branch answers a question nobody asked, and it costs a
        # full review to find out.
        print(f"SKILL MISMATCH — asked to measure {skill['requested']}, but the CLI will "
              f"load {skill['resolved'] or 'a skill this harness cannot see'}. Link the "
              f"directory into {repo}/.claude/skills/{skill['name']} and rerun.")
        return EXIT_CLI_ERROR

    cmd = build_command(args.pr, args.budget, args.model)
    text, run = stream(cmd, repo, args.timeout)
    findings, dropped = parse_findings(text, pr_number)
    fmt = diagnose_format(text, findings, dropped)
    blocked, refused = classify_denials(run["denials"])
    err = run["error"]
    payload = {
        "pr": pr_number, "pr_url": args.pr, "sha": args.sha, "model": args.model,
        "skill": skill,
        "cost_usd": round(run["cost_usd"], 4), "seconds": round(run["seconds"], 1),
        "error": err, "subagent_dispatches": run["dispatches"],
        "permissions": {"blocked_by_policy": blocked, "refused": refused},
        "unparsed": dropped, "format": fmt,
        "raw_review": raw_review(text), "findings": findings,
    }
    pathlib.Path(args.out).write_text(json.dumps(payload, indent=2))
    if args.transcript:
        pathlib.Path(args.transcript).write_text(text)

    print(f"pr={pr_number} findings={len(findings)} "
          f"subagents={run['dispatches']} "
          f"unparsed_blocks={dropped['blocks']} "
          f"orphan_fields={dropped['orphan_fields']} "
          f"blocked_by_policy={len(blocked)} refused={len(refused)} "
          f"skill={skill['fingerprint'] or 'unresolved'} "
          f"cost=${run['cost_usd']:.2f} {run['seconds']:.0f}s {err or ''}")
    if err:
        return EXIT_CLI_ERROR
    if not run["dispatches"]:
        print("SINGLE-PASS — no subagent was dispatched. The skill's reviewer phases run "
              "inside subagents, so whatever only a subagent writes was never written "
              "and the questions those phases ask were never asked. This is a different "
              "experiment from a multi-agent run; do not compare the two silently.")
    # Refusals are reported before the emptiness is diagnosed, and separately from it.
    # Folding them together once blamed an unrelated denied read for an empty findings
    # list that a format change had caused, sending the operator after the wrong thing.
    if refused:
        print(f"PERMISSION REFUSED — {len(refused)} tool call(s) the harness meant to "
              f"allow were denied, so this run saw less of the PR than it should have. "
              f"Whether that is why anything below is empty is a separate question. "
              f"First: {refused[0]}")
    # Diagnosed in order of what the evidence supports. A review that arrived and did not
    # parse is the strongest claim available — it names the defect outright — so it is
    # tested before the weaker inference that a refusal is what emptied the run.
    if fmt["failure"]:
        print(f"FORMAT FAILURE — {payload['raw_review']['chars']} characters of review "
              f"text and not one parseable field line. The reviewer produced findings "
              f"this parser cannot see; they are preserved verbatim under `raw_review` "
              f"in {args.out}. Read that text against the finding-output-format "
              f"reference, work out which of the two moved, and fix it. Do not score "
              f"this run — an empty findings list here means the harness failed, not the "
              f"PR was clean.")
        return EXIT_FORMAT_FAILURE
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
