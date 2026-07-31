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
import argparse, json, pathlib, shutil, subprocess, sys, tempfile, time

HERE = pathlib.Path(__file__).resolve().parent
CASES = HERE / "triggers.json"
FIXTURE = HERE / "fixture"


def make_sandbox():
    """Copy the fixture to a throwaway git repo.

    The committed fixture lives inside this repo, so an agent with write access and a
    `commit this` utterance would commit to the skills repo itself. Every run gets its
    own tree, git-initialised so git-shaped utterances have something real to act on,
    and discarded afterwards.
    """
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="trigger-eval-"))
    shutil.copytree(FIXTURE, tmp / "repo")
    repo = tmp / "repo"
    q = {"cwd": str(repo), "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    subprocess.run(["git", "init", "-q"], **q)
    subprocess.run(["git", "add", "-A"], **q)
    subprocess.run(["git", "-c", "user.email=eval@local", "-c", "user.name=eval",
                    "commit", "-qm", "fixture"], **q)
    # Leave one uncommitted edit so "review this" / "commit this" have a real diff.
    (repo / "src" / "user.ts").write_text(
        (repo / "src" / "user.ts").read_text() + "\nexport const VERSION = 2;\n")
    return tmp, repo


def run_case(utterance, budget, timeout, tools=None):
    """Return (skill_or_None, cost, seconds, error_or_None)."""
    tmp, repo = make_sandbox()
    cmd = ["claude", "-p", utterance,
           "--output-format", "stream-json", "--verbose",
           "--max-budget-usd", str(budget)]
    if tools:
        cmd += ["--tools", tools]
    proc = subprocess.Popen(
        cmd, cwd=str(repo), stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True)

    fired, cost, started = None, 0.0, time.time()
    try:
        for line in proc.stdout:
            if time.time() - started > timeout:
                proc.kill()
                return None, cost, time.time() - started, "timeout"
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            if d.get("type") == "assistant":
                for c in d.get("message", {}).get("content", []):
                    if c.get("type") == "tool_use" and c.get("name") == "Skill":
                        fired = (c.get("input") or {}).get("skill")
                        proc.kill()
                        return fired, cost, time.time() - started, None
            elif d.get("type") == "result":
                # Ran to completion with no Skill call — a legitimate "fired nothing".
                cost = d.get("total_cost_usd", 0.0)
                break
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
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
    args = ap.parse_args()

    if not FIXTURE.is_dir():
        print(f"missing fixture: {FIXTURE}", file=sys.stderr)
        return 2

    cases = json.loads(CASES.read_text())["cases"]
    if args.case is not None:
        cases = [cases[args.case]]
    elif args.limit:
        cases = cases[:args.limit]

    results, total_cost = [], 0.0
    for i, c in enumerate(cases):
        want = c["expect"]
        print(f"[{i+1}/{len(cases)}] {c['utterance'][:56]:<56} ", end="", flush=True)
        fires = []
        for _ in range(args.repeat):
            got, cost, secs, err = run_case(c["utterance"], args.budget, args.timeout, args.tools)
            total_cost += cost
            fires.append(got)
        hits = sum(f == want for f in fires)
        rate = hits / len(fires)
        # Anything short of unanimous is a variance finding in its own right.
        verdict = "PASS" if hits == len(fires) else ("FLAKY" if hits else "FAIL")
        seen = {}
        for f in fires:
            seen[f or "none"] = seen.get(f or "none", 0) + 1
        summary = ", ".join(f"{k}x{v}" for k, v in sorted(seen.items(), key=lambda kv: -kv[1]))
        print(f"{verdict:<5} {hits}/{len(fires)}  {summary}")
        results.append({**c, "fires": fires, "hits": hits, "n": len(fires),
                        "rate": rate, "verdict": verdict})

    clean = sum(r["verdict"] == "PASS" for r in results)
    print(f"\n{clean}/{len(results)} unanimous   ~${total_cost:.2f}\n")

    misses = [r for r in results if r["verdict"] != "PASS"]
    if misses:
        print("Findings — each is about the description, not the eval:\n")
        for r in misses:
            want = r["expect"] or "nothing"
            kinds = set()
            for f in r["fires"]:
                if f == r["expect"]:
                    continue
                kinds.add("OVER-TRIGGER" if r["expect"] is None else
                          "SILENT" if f is None else "WRONG SKILL")
            print(f"  {'/'.join(sorted(kinds))}: \"{r['utterance']}\"")
            print(f"      expected {want} — fired it {r['hits']}/{r['n']} runs")
            print(f"      testing: {r['why']}\n")

    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
