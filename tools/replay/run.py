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
   findings survive the parser that could not read them. A review that arrives in *two*
   shapes, only one of which parses, is caught by the count the review declares of
   itself — the failure the total-failure gate was never built to see.

Exit codes: 0 findings parsed, 1 none parsed, 2 the CLI failed or timed out or is
misconfigured, 3 nothing parsed and a tool call the harness meant to allow was refused,
4 a review arrived and no part of it parsed, 5 the number parsed is not the number the
review says it wrote.

Usage:
    python3 tools/replay/run.py --pr https://github.com/o/r/pull/123 --out run.json
    python3 tools/replay/run.py --pr <url> --sha <merge-sha> --timeout 3600 --out run.json
    python3 tools/replay/run.py --pr <url> --skill-dir skills/review-pr --out run.json
"""
import argparse
import collections
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
# The label may arrive wearing markdown. `**Issue**:`, `__Issue__:`, `` `Issue`: ``,
# `` `Issue: value` `` and a `- ` or `* ` bullet in front of any of them all name the same
# field, and three consecutive live runs lost an entire review to that wrapper. What the
# decoration may NOT do is move the label off the start of the line: the anchor is the only
# thing separating a field emission from the same word inside a sentence, so an opening
# wrapper is allowed before the label and nothing else is. A closing wrapper must be the
# one that opened — `**Issue`:` is a typo, not a dialect, and admitting it buys nothing.
#
# Deliberately still rejected: markdown headings (`### Issue:`) and ordinals (`1. Issue:`).
# Both are section syntax rather than field syntax, and accepting them would let an
# ordinary contents line ("## Severity: how we grade") open a finding.
_WRAPPER = r"\*\*|__|`"
_FIELD_RE = re.compile(
    r"^[ \t]*(?P<bullet>[-*][ \t]+)?(?P<open>" + _WRAPPER + r")?[ \t]*"
    r"(?P<label>" + "|".join(re.escape(k) for k in FIELDS) + r")[ \t]*"
    r"(?P<close>(?P=open))?[ \t]*:[ \t]*(?P<value>.*)$",
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
EXIT_COUNT_MISMATCH = 5

# `claude -p` appends its own directive to the system prompt: "Do not call the AgentTool
# unless the user requested it", alongside the same sentence for workflows. It is a
# property of the print entrypoint, not of this machine's configuration — it survives
# `--setting-sources project` and every value of it, and survives scrubbing `CLAUDECODE`,
# `CLAUDE_CODE_CHILD_SESSION` and the rest of the nesting markers from the child's
# environment. A run that leaves it unanswered reviews the whole PR inline in main and
# says so in a footnote, which is a different experiment wearing this one's output shape.
#
# The directive is conditional, and the condition is a user request. The harness is the
# user here, so it makes the request rather than trying to suppress the rule — an
# `--append-system-prompt` block lands after the directive and satisfies it on its own
# terms. What it must NOT do is describe the review: how many subagents there are, what
# each one reads, and whether a small PR skips dispatch entirely are the skill's decisions
# and are part of what is being measured. This grants the tool and refuses the substitute;
# it does not design the run.
DISPATCH = (
    " The user has explicitly requested that you dispatch subagents with the Agent tool "
    "wherever the skill's instructions call for one, and has opted in to multi-agent "
    "orchestration for this run. Treat that as the request any standing "
    "use-the-Agent-tool-only-when-asked instruction is waiting for. Do not substitute an "
    "inline single-pass run for a dispatch the skill specifies; the skill decides how many "
    "subagents there are and what goes in them, not this instruction."
)

# Output redirection reads as a write to the CLI's own matcher, whatever the command in
# front of it: `gh pr diff … > /tmp/x.diff` is refused even though `Bash(gh pr diff:*)` is
# allowed. Telling the reviewer up front is cheaper than letting it discover this the way
# the last run did — ten refusals, four of them the same command retried, and the diff it
# was trying to stash never read at all.
NO_REDIRECT = (
    " Do not redirect command output to a file (`>`, `>>`, `tee`) or write scratch files: "
    "redirection is refused here regardless of the command producing it. Read command "
    "output directly from the tool result, and re-run the command if you need it again."
)

GUARD = (
    "You are running inside a non-interactive benchmark harness. Do NOT post, comment, "
    "review, or otherwise write anything to GitHub or to any remote — produce findings "
    "only. There is no human to answer AskUserQuestion: when the skill offers a choice, "
    "take the option that continues the review without posting, and state which you took."
) + NO_REDIRECT + DISPATCH

# Which settings scopes the child loads. User scope is dropped and project scope kept,
# because the two hold different things and only one of them belongs in a measurement.
# User scope carries the operator's personal standing rules, their output style and their
# enabled plugins — including, on this machine, a second skill also named `review-pr`,
# which is a coin-flip over which artifact the benchmark scores. Project scope carries the
# reviewed repo's own CLAUDE.md, which a review has to read to judge the repo's
# conventions; a benchmark that isolated that away would be measuring a worse reviewer
# than the one it means to.
#
# Not `--bare`. It would drop the ambient configuration too, but it also drops CLAUDE.md
# discovery outright, and its auth is strictly ANTHROPIC_API_KEY — under an OAuth login it
# exits "Not logged in" before the review starts.
SETTING_SOURCES = "project,local"


def field_value(match):
    """The value a decorated field line meant, without the decoration around it.

    A wrapper opened before the label and not closed before the colon closes somewhere
    after it, and where it closes says which of two shapes was written. Immediately after
    the colon, it wrapped the label and its punctuation — `**Issue:** text` — and the
    value is what follows. Anywhere later, it wrapped the whole field —
    `` `Rule-class: stale-read` `` — and the value ends there.

    `**Issue:**` matters more than it looks: it is the most ordinary way to bold a label,
    and reading it the other way returns an empty value, which `parse_findings` discards
    without counting. That is the silent loss this whole change exists to remove, so the
    two cases are told apart rather than collapsed.

    Whatever follows the closing delimiter is left unread rather than guessed at: a second
    field sharing a line is not a shape the format emits, and inventing a separator to
    split on would be the parser deciding what the reviewer meant.
    """
    value = match.group("value")
    opened = match.group("open")
    if opened and not match.group("close"):
        before, closed, after = value.partition(opened)
        value = after if closed and not before.strip() else before
    return value.strip()


def decoration(text):
    """Which labels arrived dressed in markdown, and how many times.

    Parsing a decorated label and saying nothing would trade one silent failure for
    another: the run scores, the emitter drifts further from the contract every week, and
    nothing in the output ever mentions it. So the tolerance is real and the deviation is
    reported — counted here, printed by `main`, never fatal. Losing a whole review over a
    wrapper character is the worse outcome, and a drift that is visible gets fixed.
    """
    labels = collections.Counter()
    for line in text.splitlines():
        m = _FIELD_RE.match(line)
        if m and (m.group("bullet") or m.group("open") or m.group("close")):
            labels[FIELDS[m.group("label").lower()]] += 1
    return {"fields": sum(labels.values()), "labels": sorted(labels)}


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
        key = FIELDS[m.group("label").lower()]
        value = field_value(m)
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
    wholly different shape trips neither, so a reviewer that folded its findings into
    prose and headings reports zero findings, zero unparsed blocks and zero orphans:
    every counter agreeing that nothing was lost.

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
    return {"failure": failure, "markers": markers, "decorated": decoration(text)}


# The review states its own total in `## Findings (N)`, and the format reference fixes
# what N covers: every finding the round emits, `Follow-ups (non-blocking)` included. That
# makes it the one number in the output that can be held against the parse with no
# heuristic, no threshold and no marker vocabulary behind it.
#
# Anchored to heading syntax and to the word `Findings`. `## Filtered out (N)` carries a
# count of its own and is a different set by contract — findings the review dropped, which
# nothing downstream acts on — so reading it here would invent a shortfall on every run
# that filtered anything. `## Follow-ups (non-blocking)` carries no count and its entries
# are a subset of N, so it is not a source either.
_FINDINGS_HEADING_RE = re.compile(r"^[ \t]*#{1,6}[ \t]+Findings\b[^\n(]*\((\d+)\)",
                                  re.MULTILINE)

# The same heading with the count dropped. It is the one way this detector goes quiet
# while a review plainly exists, so it is recognised separately and said out loud rather
# than left to look like a review that declared nothing.
_UNCOUNTED_HEADING_RE = re.compile(r"^[ \t]*#{1,6}[ \t]+Findings\b", re.MULTILINE)

# The header's `Convergence` field partitions the same set the heading totals, so its four
# numbers are a second statement of N written by a different step of the skill. Each part
# is matched against the word that names it rather than by position, so the trend sentence
# the posted-body rendering appends to the same line cannot contribute a number.
_CONVERGENCE_LINE_RE = re.compile(r"^.*\bConvergence\b.*$", re.MULTILINE)
_CONVERGENCE_PARTS = (r"(\d+)[ \t]+new\b", r"(\d+)[ \t]+caused\b",
                      r"(\d+)[ \t]+regressions?\b", r"(\d+)[ \t]+carried\b")


def _convergence_total(text):
    """The `Convergence` header field's four counts, summed — or None if it is not there.

    All four parts or nothing: a line missing one of them is a rendering this code does
    not recognise, and summing what it could find would declare a total lower than the
    review meant, which is the direction that hides loss.
    """
    for line in _CONVERGENCE_LINE_RE.findall(text):
        found = [re.search(part, line, re.IGNORECASE) for part in _CONVERGENCE_PARTS]
        if all(found):
            return sum(int(m.group(1)) for m in found)
    return None


def diagnose_count(text, findings):
    """Does the number of findings parsed match the number the review says it wrote?

    `format.failure` was calibrated on a review where *nothing* parsed, and it does not
    generalise to one where some of it did. Two live runs declared 15 and 22 findings,
    parsed 3 and 4, and tripped no counter at all: `unparsed.blocks` and
    `unparsed.orphan_fields` were zero because the lost findings were not malformed
    blocks — they were rows of a markdown summary table, a shape with no field lines in
    it to be dropped or orphaned. Every instrument here was built for total failure, so
    a partial one passed as clean.

    This one needs none of that machinery, because the review declares the answer. Two
    sources state it and neither is inferred:

    - `## Findings (N)` — the contractual declaration.
    - the `Convergence` header field, whose four counts partition the same set.

    Where they disagree the larger is taken and the disagreement is reported. Both are the
    review's own arithmetic; when a review cannot agree with itself the declaration is
    already unreliable, and the smaller number is the one that would let real loss through.

    Repeated `## Findings` headings are likewise resolved by taking the largest and
    reporting how many there were. A re-printed review block is the shape that produces
    them, and it is also the shape that duplicates findings — so an operator reading a
    shortfall needs to know a second heading existed before concluding anything.

    A surplus is reported too, and just as fatally. It cannot mean loss, but it means the
    finding list and the review's own count describe different sets — which is what a
    double-counted result event looks like, a defect this harness has already shipped
    once, and scoring a run whose findings appear twice measures the duplication.

    Silent when the review declares nothing. A clean PR with no `## Findings` heading, or
    any review that emits none, leaves `declared` at None and this detector inert: the
    comparison exists only where the review made a claim to compare against. A heading
    that arrives *without* its count is the one shape where that silence is wrong — there
    is a review and no declaration of it — so `undeclared_heading` names it. It warns
    rather than fails: a missing `(N)` is a formatting deviation, and nothing here knows
    whether anything was lost behind it.
    """
    headings = [int(n) for n in _FINDINGS_HEADING_RE.findall(text)]
    heading = max(headings) if headings else None
    convergence = _convergence_total(text)
    stated = [n for n in (heading, convergence) if n is not None]
    declared = max(stated) if stated else None
    parsed = len(findings)
    return {
        "declared": declared, "parsed": parsed,
        "heading": heading, "heading_occurrences": len(headings),
        "convergence": convergence,
        "undeclared_heading": bool(_UNCOUNTED_HEADING_RE.search(text)) and declared is None,
        "sources_disagree": len(set(stated)) > 1,
        "shortfall": max(declared - parsed, 0) if declared is not None else 0,
        "surplus": max(parsed - declared, 0) if declared is not None else 0,
    }


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


def build_command(pr_url, model):
    # No `--max-budget-usd`. It is enforced whatever the billing mode, so on a
    # subscription it is a kill switch with no corresponding saving: run 2 died at
    # "$15.17 of $15" partway through Phase 2 and answered none of the questions it was
    # launched to answer. `--timeout` is now the ONLY bound on a run, which is why it
    # must always be set — the failure being fixed here was a bound in the wrong
    # currency, not one bound too many.
    """The full invocation, in one place so a test can assert what the run may do.

    Whether a benchmark run can write to the repo it is reviewing should be readable and
    testable on its own, not reconstructed from the arguments of a subprocess call.
    """
    cmd = ["claude", "-p", f"/review-pr {pr_url}",
           "--output-format", "stream-json", "--verbose",
           "--append-system-prompt", GUARD,
           "--setting-sources", SETTING_SOURCES,
           "--permission-mode", PERMISSION_MODE,
           "--forward-subagent-text",
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

    Counting them is not enough to see what they said. Subagent turns reach the stream
    only under `--forward-subagent-text`, and they are returned separately from main's
    text rather than concatenated with it: the reviewer's Q lines and coverage cells are
    the evidence that the phases ran in their declared shapes, but they also restate
    findings main has already emitted, and folding them into the parsed text would count
    every such finding twice and read as a reviewer that repeats itself.

    stderr is captured rather than discarded: when the CLI dies before emitting a single
    event, stderr holds the only statement of why, and a harness that throws it away
    reports an auth failure or a bad flag as "this PR had no findings".
    """
    chunks, sub_chunks, denials, cost, started = [], [], [], 0.0, time.time()
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
                # `parent_tool_use_id` is the CLI's marker for a forwarded subagent turn.
                # It is the whole basis of the split: a reviewer subagent's Q lines and
                # coverage cells are the output the ledger is assembled from, and main
                # never restates them, so a run that keeps only main's text cannot say
                # whether they were ever emitted.
                inside_subagent = bool(event.get("parent_tool_use_id"))
                target = sub_chunks if inside_subagent else chunks
                if event.get("type") == "assistant":
                    for c in event.get("message", {}).get("content", []):
                        if c.get("type") == "text":
                            target.append(c.get("text", ""))
                        elif c.get("type") == "tool_use" and c.get("name") in DISPATCH_TOOLS:
                            dispatches += 1
                elif event.get("type") == "result":
                    # A subagent emits its own result event carrying its own spend. Read
                    # blind, the last one to arrive wins and the run reports whatever the
                    # final subagent cost instead of what the review cost.
                    if not inside_subagent:
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
                    if result_text and result_text not in "\n".join(target):
                        target.append(result_text)
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
                               "error": error, "subagent_text": "\n".join(sub_chunks)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pr", required=True, help="PR URL. Prefer merged/closed PRs — an "
                                                "open PR's head moves under the benchmark")
    ap.add_argument("--sha", help="the commit this replay is scored against. Recorded in "
                                  "the output; not enforced against the live PR head")
    ap.add_argument("--repo", default=".", help="local checkout the skill runs in")
    ap.add_argument("--out", required=True, help="findings JSON, input to score.py")
    ap.add_argument("--timeout", type=int, default=3600,
                    help="seconds. The only bound on a run — there is no cost cap.")
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

    cmd = build_command(args.pr, args.model)
    text, run = stream(cmd, repo, args.timeout)
    findings, dropped = parse_findings(text, pr_number)
    fmt = diagnose_format(text, findings, dropped)
    count = diagnose_count(text, findings)
    blocked, refused = classify_denials(run["denials"])
    err = run["error"]
    payload = {
        "pr": pr_number, "pr_url": args.pr, "sha": args.sha, "model": args.model,
        "skill": skill, "setting_sources": SETTING_SOURCES,
        "cost_usd": round(run["cost_usd"], 4), "seconds": round(run["seconds"], 1),
        "error": err, "subagent_dispatches": run["dispatches"],
        "permissions": {"blocked_by_policy": blocked, "refused": refused},
        "unparsed": dropped, "format": fmt, "count": count,
        "raw_review": raw_review(text),
        "subagent_output": raw_review(run["subagent_text"]),
        "findings": findings,
    }
    pathlib.Path(args.out).write_text(json.dumps(payload, indent=2))
    if args.transcript:
        pathlib.Path(args.transcript).write_text(text)

    print(f"pr={pr_number} findings={len(findings)} "
          f"declared={count['declared'] if count['declared'] is not None else '-'} "
          f"subagents={run['dispatches']} "
          f"unparsed_blocks={dropped['blocks']} "
          f"orphan_fields={dropped['orphan_fields']} "
          f"decorated_fields={fmt['decorated']['fields']} "
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
    if fmt["decorated"]["fields"]:
        print(f"FORMAT DRIFT — {fmt['decorated']['fields']} field line(s) arrived wrapped "
              f"in markdown ({', '.join(fmt['decorated']['labels'])}). The parser read "
              f"them and this run still counts, but the emitter is off the contract: "
              f"finding-output-format asks for a bare label at line start. Fix the skill "
              f"rather than widening the parser again — the next wrapper may not be one "
              f"it knows.")
    if count["shortfall"]:
        print(f"FINDINGS LOST — the review declares {count['declared']} finding(s) and "
              f"{count['parsed']} parsed. The missing {count['shortfall']} exist in this "
              f"run only as `raw_review` text in {args.out}; nothing downstream will ever "
              f"see them. Read that text against the finding-output-format reference: the "
              f"shapes that produce this are a summary table or a heading-and-prose "
              f"rendering under a heading the parser cannot enter. Do not score this run "
              f"— its findings are a minority of the review it came from.")
    if count["surplus"]:
        print(f"FINDINGS DUPLICATED — {count['parsed']} findings parsed against "
              f"{count['declared']} declared. Nothing was lost, but the finding list and "
              f"the review's own count describe different sets, and a list carrying the "
              f"same finding twice scores the duplicate as an unmatched miss. Do not "
              f"score this run until the extra {count['surplus']} are accounted for.")
    if count["sources_disagree"]:
        print(f"COUNT DISAGREEMENT — the `## Findings` heading says {count['heading']} "
              f"and the Convergence field sums to {count['convergence']}. The review is "
              f"inconsistent with itself, so the larger was used above; whichever number "
              f"is wrong, one of the skill's two counting steps is.")
    if count["undeclared_heading"]:
        print("NO DECLARED COUNT — the review has a `## Findings` heading with no `(N)` "
              "after it and no `Convergence` field, so nothing states how many findings "
              "it meant to emit and the shortfall check has nothing to compare against. "
              "This run cannot say whether it lost any. Fix the emitter: the count is "
              "what makes that question answerable at all.")
    if count["heading_occurrences"] > 1:
        print(f"REPEATED HEADING — {count['heading_occurrences']} `## Findings` headings "
              f"in one review. The block was emitted more than once, which is both a way "
              f"to declare two different totals and a way to parse the same finding twice.")
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
    # After the format failure, which names the same defect more precisely when both fire,
    # and before the emptiness codes, which would otherwise file a run that lost every
    # finding it declared as a clean PR. Exit 0 is what let two live runs report a clean
    # bill of health while 82% of the review went nowhere, so a mismatch never returns it.
    if count["shortfall"] or count["surplus"]:
        return EXIT_COUNT_MISMATCH
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
