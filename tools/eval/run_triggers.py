#!/usr/bin/env python3
"""Trigger eval: does each skill's description fire when it should, and stay quiet when it shouldn't?

The rubric this repo is written against says two of its judgements — whether a line is a
no-op, and whether a leading word beats the default — can only be settled by running the
skill, not by reading it. This measures the one part of that which produces a clean
discrete signal: which skill the agent reaches for first.

Each case runs in a fresh non-interactive session against tools/eval/fixture/, streams the
JSON event log, and records the first Skill invocation that is not ambient. The session is
killed the moment that lands — we are measuring the routing decision, not the work that
follows, and letting the skill run costs roughly 3x more per case.

Usage:
    python3 tools/eval/run_triggers.py                # all cases
    python3 tools/eval/run_triggers.py --limit 5      # pilot before spending the full run
    python3 tools/eval/run_triggers.py --case 7       # one case by index
    python3 tools/eval/run_triggers.py --budget 0.15  # per-case USD cap
    python3 tools/eval/run_triggers.py --ignore-skill foo  # extend the ambient set
"""
import argparse, json, os, pathlib, selectors, shutil, subprocess, sys, time

import harness

HERE = pathlib.Path(__file__).resolve().parent
CASES = HERE / "triggers.json"
FIXTURE = HERE / "fixture"

# Skills a standing instruction fires in every session, whatever the utterance. They are not
# routing decisions, so recording one as the answer scores the global config instead of the
# description under test. `unslop` is here because the user's global CLAUDE.md orders it into
# every session and a UserPromptSubmit hook repeats the order; it lands first in every case
# and, since the session dies on the first Skill event, the real routing choice never runs.
AMBIENT_SKILLS = frozenset({"unslop"})


def leave_uncommitted_edit(repo):
    """So "review this" and "commit this" have a real diff to act on."""
    path = repo / "src" / "user.ts"
    path.write_text(path.read_text() + "\nexport const VERSION = 2;\n")


def make_sandbox(skill_path=None):
    return harness.make_sandbox(
        "trigger-eval-", FIXTURE,
        skills=[skill_path] if skill_path else (),
        post_commit_edit=leave_uncommitted_edit)


def run_case(utterance, budget, timeout, tools=None, skill_path=None, ambient=AMBIENT_SKILLS):
    """Return (skill_or_None, cost, seconds, error_or_None, ambient_skills_seen)."""
    tmp, repo = make_sandbox(skill_path)
    cmd = ["claude", "-p", utterance,
           "--output-format", "stream-json", "--verbose",
           "--max-budget-usd", str(budget)]
    if tools:
        cmd += ["--tools", tools]
    proc = subprocess.Popen(
        cmd, cwd=str(repo), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=True)

    is_process_group_stopped = False

    def stop_process_group():
        nonlocal is_process_group_stopped
        if is_process_group_stopped:
            return "", ""
        is_process_group_stopped = True
        return harness.kill_process_group(proc)

    def parse_event(line):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return None
        named = harness.parse_skill_names(event)
        if named:
            return "skill", named
        if event.get("type") == "result":
            return "result", (event.get("total_cost_usd", 0.0),
                              harness.format_result_error(event))
        return None

    cost, started = 0.0, time.time()
    stdout_buffer = b""
    stderr_chunks = []
    seen_ambient = []

    def consume(parsed):
        """Fold one parsed event into a return tuple, or None to keep reading."""
        kind, value = parsed
        if kind == "skill":
            for name in value:
                # A Skill block whose input did not parse means a skill fired and the
                # harness could not read which. Returning it as `None` is indistinguishable
                # from the agent choosing nothing, which a `forbid` case then scores as a
                # pass. It is an eval failure, not a routing decision.
                if name is None:
                    return (None, cost, time.time() - started,
                            "Skill invoked with unreadable input", seen_ambient)
                if name in ambient:
                    seen_ambient.append(name)
                    continue
                return name, cost, time.time() - started, None, seen_ambient
            return None
        total, error = value
        return None, total, time.time() - started, error, seen_ambient

    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            selector.register(proc.stderr, selectors.EVENT_READ)
            while selector.get_map():
                remaining = timeout - (time.time() - started)
                if remaining <= 0:
                    stop_process_group()
                    return None, cost, time.time() - started, "timeout", seen_ambient
                events = selector.select(timeout=min(remaining, 1.0))
                if not events:
                    if proc.poll() is not None:
                        break
                    continue
                for key, _ in events:
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    if key.fileobj is proc.stderr:
                        stderr_chunks.append(chunk)
                        continue
                    stdout_buffer += chunk
                    while b"\n" in stdout_buffer:
                        line, stdout_buffer = stdout_buffer.split(b"\n", 1)
                        parsed = parse_event(line.decode(errors="replace"))
                        if not parsed:
                            continue
                        outcome = consume(parsed)
                        if outcome:
                            return outcome

            remaining = timeout - (time.time() - started)
            if remaining <= 0:
                stop_process_group()
                return None, cost, time.time() - started, "timeout", seen_ambient
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                stop_process_group()
                return None, cost, time.time() - started, "timeout", seen_ambient

            if stdout_buffer:
                parsed = parse_event(stdout_buffer.decode(errors="replace"))
                if parsed:
                    outcome = consume(parsed)
                    if outcome:
                        return outcome

            stderr = b"".join(stderr_chunks).decode(errors="replace").strip()
            returncode = proc.returncode
            detail = f": {stderr}" if stderr else ""
            if returncode != 0:
                return (None, cost, time.time() - started,
                        f"claude exited {returncode}{detail}", seen_ambient)
            return (None, cost, time.time() - started,
                    f"missing result event{detail}", seen_ambient)
    finally:
        stop_process_group()
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="run only the first N cases")
    ap.add_argument("--case", type=int, help="run a single case by index")
    ap.add_argument("--budget", type=float, default=0.60,
                    help="per-case USD cap. Too low and the session is cut off before the "
                         "agent finishes orienting, which reads as 'never fired' when it "
                         "simply never got there. 0.10 caps most sessions at one turn.")
    ap.add_argument("--tools", default=None,
                    help="restrict the tool set (e.g. 'Skill Read Glob Grep'). Off by "
                         "default: removing Bash denies the agent its usual orienting "
                         "move and suppresses invocation as a side effect.")
    ap.add_argument("--timeout", type=int, default=180, help="per-case seconds")
    ap.add_argument("--repeat", type=int, default=1,
                    help="runs per case. Invocation is non-deterministic — a single run "
                         "reports a coin flip as a fact. Use 3+ for anything you act on.")
    ap.add_argument("--skill-path", type=pathlib.Path,
                    help="copy a source skill into each sandbox for pre-install testing")
    ap.add_argument("--ignore-skill", action="append", default=[], metavar="NAME",
                    help=f"treat NAME as ambient and keep reading past it. Repeatable. "
                         f"Adds to the default set {sorted(AMBIENT_SKILLS)}.")
    ap.add_argument("--no-ignore-ambient", action="store_true",
                    help="record the first Skill invocation even if it is ambient, which is "
                         "how this ran before and is the way to see what is being skipped.")
    args = ap.parse_args()

    if args.repeat < 1:
        ap.error("--repeat must be at least 1")

    ambient = frozenset() if args.no_ignore_ambient else AMBIENT_SKILLS | set(args.ignore_skill)

    if not FIXTURE.is_dir():
        print(f"missing fixture: {FIXTURE}", file=sys.stderr)
        return 2

    skill_path = args.skill_path.resolve() if args.skill_path else None
    if skill_path and not (skill_path / "SKILL.md").is_file():
        print(f"invalid skill path: {skill_path}", file=sys.stderr)
        return 2

    cases = json.loads(CASES.read_text())["cases"]
    if args.case is not None:
        cases = [cases[args.case]]
    elif args.limit:
        cases = cases[:args.limit]

    for index, case in enumerate(cases):
        if "expect" not in case and "forbid" not in case:
            print(f"case {index} declares neither 'expect' nor 'forbid'", file=sys.stderr)
            return 2

    results = []
    for i, c in enumerate(cases):
        has_expected_skill = "expect" in c
        expected_skill = c.get("expect")
        forbidden_skill = c.get("forbid")
        print(f"[{i+1}/{len(cases)}] {c['utterance'][:56]:<56} ", end="", flush=True)
        fires, errors, skipped = [], [], []
        for _ in range(args.repeat):
            got, cost, secs, err, ambient_seen = run_case(
                c["utterance"], args.budget, args.timeout, args.tools, skill_path, ambient)
            fires.append(got)
            errors.append(err)
            skipped.extend(ambient_seen)
        hits = sum(
            err is None
            and (not has_expected_skill or fired == expected_skill)
            and (forbidden_skill is None or fired != forbidden_skill)
            for fired, err in zip(fires, errors)
        )
        rate = hits / len(fires)
        verdict = harness.verdict(hits, len(fires), has_error=any(errors))
        seen = {}
        for fired, error in zip(fires, errors):
            outcome = f"error:{error}" if error else fired or "none"
            seen[outcome] = seen.get(outcome, 0) + 1
        summary = ", ".join(f"{k}x{v}" for k, v in sorted(seen.items(), key=lambda kv: -kv[1]))
        passed_over = ", ".join(f"{n}x{skipped.count(n)}" for n in sorted(set(skipped)))
        print(f"{verdict:<5} {hits}/{len(fires)}  {summary}"
              + (f"  [ambient: {passed_over}]" if passed_over else ""))
        results.append({**c, "fires": fires, "errors": errors, "ambient": skipped,
                        "hits": hits, "n": len(fires),
                        "rate": rate, "verdict": verdict})

    clean = sum(r["verdict"] == "PASS" for r in results)
    print(f"\n{clean}/{len(results)} unanimous\n")

    misses = [r for r in results if r["verdict"] != "PASS"]
    if misses:
        print("Findings — each is about the description, not the eval:\n")
        for r in misses:
            has_expected_skill = "expect" in r
            expected_skill = r.get("expect")
            forbidden_skill = r.get("forbid")
            want = (expected_skill or "nothing") if has_expected_skill else f"anything except {forbidden_skill}"
            kinds = set()
            for f, error in zip(r["fires"], r["errors"]):
                if error:
                    kinds.add("EVAL ERROR")
                    continue
                if has_expected_skill and f == expected_skill:
                    continue
                if not has_expected_skill and f != forbidden_skill:
                    continue
                kinds.add("OVER-TRIGGER" if forbidden_skill or expected_skill is None else
                          "SILENT" if f is None else "WRONG SKILL")
            print(f"  {'/'.join(sorted(kinds))}: \"{r['utterance']}\"")
            print(f"      expected {want} — fired it {r['hits']}/{r['n']} runs")
            print(f"      testing: {r['why']}\n")

    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
