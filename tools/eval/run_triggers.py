#!/usr/bin/env python3
"""Trigger eval: does each skill's description fire when it should, and stay quiet when it shouldn't?

The rubric this repo is written against says two of its judgements — whether a line is a
no-op, and whether a leading word beats the default — can only be settled by running the
skill, not by reading it. This measures the one part of that which produces a clean
discrete signal: which skill the agent reaches for first.

Each case runs in a fresh non-interactive session against tools/eval/fixture/, streams the
JSON event log, and records the FIRST Skill invocation. The session is killed the moment
that lands — we are measuring the routing decision, not the work that follows, and letting
the skill run costs roughly 3x more per case.

Usage:
    python3 tools/eval/run_triggers.py                # all cases
    python3 tools/eval/run_triggers.py --limit 5      # pilot before spending the full run
    python3 tools/eval/run_triggers.py --case 7       # one case by index
    python3 tools/eval/run_triggers.py --budget 0.15  # per-case USD cap
"""
import argparse, json, os, pathlib, selectors, shutil, signal, subprocess, sys, tempfile, time

HERE = pathlib.Path(__file__).resolve().parent
CASES = HERE / "triggers.json"
FIXTURE = HERE / "fixture"


def make_sandbox(skill_path=None):
    """Copy the fixture to a throwaway git repo.

    The committed fixture lives inside this repo, so an agent with write access and a
    `commit this` utterance would commit to the skills repo itself. Every run gets its
    own tree, git-initialised so git-shaped utterances have something real to act on,
    and discarded afterwards.
    """
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="trigger-eval-"))
    shutil.copytree(FIXTURE, tmp / "repo")
    repo = tmp / "repo"
    if skill_path:
        project_skills = repo / ".claude" / "skills"
        project_skills.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill_path, project_skills / skill_path.name, dirs_exist_ok=True)
    q = {"cwd": str(repo), "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    subprocess.run(["git", "init", "-q"], **q)
    subprocess.run(["git", "add", "-A"], **q)
    subprocess.run(["git", "-c", "user.email=eval@local", "-c", "user.name=eval",
                    "commit", "-qm", "fixture"], **q)
    # Leave one uncommitted edit so "review this" / "commit this" have a real diff.
    (repo / "src" / "user.ts").write_text(
        (repo / "src" / "user.ts").read_text() + "\nexport const VERSION = 2;\n")
    return tmp, repo


def run_case(utterance, budget, timeout, tools=None, skill_path=None):
    """Return (skill_or_None, cost, seconds, error_or_None)."""
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
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            return proc.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            proc.stdout.close()
            proc.stderr.close()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            return "", ""

    def parse_event(line):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return None
        if event.get("type") == "assistant":
            for content in event.get("message", {}).get("content", []):
                if content.get("type") == "tool_use" and content.get("name") == "Skill":
                    return "skill", (content.get("input") or {}).get("skill")
        if event.get("type") == "result":
            error = None
            if event.get("is_error"):
                status = event.get("api_error_status")
                terminal_reason = event.get("terminal_reason")
                detail = str(event.get("result", "")).strip().replace("\n", " ")[:160]
                error = ": ".join(
                    part
                    for part in [
                        f"api error {status}" if status else None,
                        terminal_reason if terminal_reason != "completed" else None,
                        detail or None,
                    ]
                    if part
                ) or "result-error"
            return "result", (event.get("total_cost_usd", 0.0), error)
        return None

    fired, cost, started = None, 0.0, time.time()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            while proc.poll() is None:
                remaining = timeout - (time.time() - started)
                if remaining <= 0:
                    stop_process_group()
                    return None, cost, time.time() - started, "timeout"
                events = selector.select(timeout=min(remaining, 1.0))
                if not events:
                    continue
                line = proc.stdout.readline()
                if not line:
                    break
                parsed = parse_event(line)
                if not parsed:
                    continue
                kind, value = parsed
                if kind == "skill":
                    return value, cost, time.time() - started, None
                cost, error = value
                return None, cost, time.time() - started, error

            remaining = timeout - (time.time() - started)
            if remaining <= 0:
                stop_process_group()
                return None, cost, time.time() - started, "timeout"
            try:
                stdout_tail, stderr = proc.communicate(timeout=remaining)
            except subprocess.TimeoutExpired:
                stop_process_group()
                return None, cost, time.time() - started, "timeout"

            for line in stdout_tail.splitlines():
                parsed = parse_event(line)
                if not parsed:
                    continue
                kind, value = parsed
                if kind == "skill":
                    return value, cost, time.time() - started, None
                cost, error = value
                return None, cost, time.time() - started, error

            stderr = stderr.strip()
            returncode = proc.returncode
            detail = f": {stderr}" if stderr else ""
            if returncode != 0:
                return None, cost, time.time() - started, f"claude exited {returncode}{detail}"
            return None, cost, time.time() - started, f"missing result event{detail}"
    finally:
        stop_process_group()
        shutil.rmtree(tmp, ignore_errors=True)

    return fired, cost, time.time() - started, None


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
    args = ap.parse_args()

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

    results = []
    for i, c in enumerate(cases):
        has_expected_skill = "expect" in c
        expected_skill = c.get("expect")
        forbidden_skill = c.get("forbid")
        print(f"[{i+1}/{len(cases)}] {c['utterance'][:56]:<56} ", end="", flush=True)
        fires, errors = [], []
        for _ in range(args.repeat):
            got, cost, secs, err = run_case(
                c["utterance"], args.budget, args.timeout, args.tools, skill_path)
            fires.append(got)
            errors.append(err)
        hits = sum(
            err is None
            and (not has_expected_skill or fired == expected_skill)
            and (forbidden_skill is None or fired != forbidden_skill)
            for fired, err in zip(fires, errors)
        )
        rate = hits / len(fires)
        verdict = ("ERROR" if any(errors) else "PASS" if hits == len(fires)
                   else "FLAKY" if hits else "FAIL")
        seen = {}
        for fired, error in zip(fires, errors):
            outcome = f"error:{error}" if error else fired or "none"
            seen[outcome] = seen.get(outcome, 0) + 1
        summary = ", ".join(f"{k}x{v}" for k, v in sorted(seen.items(), key=lambda kv: -kv[1]))
        print(f"{verdict:<5} {hits}/{len(fires)}  {summary}")
        results.append({**c, "fires": fires, "errors": errors,
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
