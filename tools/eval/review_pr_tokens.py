#!/usr/bin/env python3
"""Token and wall-time accounting for a review-pr live run.

Reads the stream-json transcripts produced by `claude -p "/review-pr <url>"
--output-format stream-json --verbose` (one file per agent: the main run first,
then one file per dispatched subagent) and reports input/output/cache tokens
plus wall time, split by main and subagent. Built on harness.iter_events so a
truncated transcript reads as truncated, not clean.

A main transcript alone undercounts a run by every reviewer dispatched, which
is why the run procedure (docs/review_pr_fixture_runs.md) captures one stream
per agent. Wall times overlap: subagents run in parallel, so the run wall
time is the main duration while the summed durations are CPU.

A single parent capture works too. With --forward-subagent-text the stream
carries each subagent's messages tagged by parent_tool_use_id, and --split
carves one file per agent out of it. Token cells then reflect only the usage
events present on each group's messages; a group with none reports zero
rather than an estimate.

Usage:
    python3 tools/eval/review_pr_tokens.py main.jsonl [sub1.jsonl ...] [--json]
    python3 tools/eval/review_pr_tokens.py --split outdir parent.jsonl [--json]
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness

USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens",
              "cache_read_input_tokens")


def summarize(path, require_result=True):
    """Return token sums, wall time, cost, and truncation flag for one file.

    Carved subagent streams hold no result event, so their callers pass
    require_result=False and read truncated/error as stream health only."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    totals = {key: 0 for key in USAGE_KEYS}
    duration_ms, cost_usd, saw_result, turns = 0, 0.0, False, 0
    for event in harness.iter_events(text):
        if event.get("type") == "assistant":
            usage = (event.get("message") or {}).get("usage") or {}
            for key in USAGE_KEYS:
                totals[key] += usage.get(key, 0) or 0
        elif event.get("type") == "result":
            saw_result = True
            duration_ms = event.get("duration_ms", 0) or 0
            cost_usd = event.get("total_cost_usd", 0.0) or 0.0
            usage = event.get("usage") or {}
            for key in USAGE_KEYS:
                totals[key] = max(totals[key], usage.get(key, 0) or 0)
            turns = event.get("num_turns", 0) or 0
    _, _, error = harness.parse_transcript(text)
    truncated = not saw_result and require_result
    if not truncated and not saw_result:
        error = None
    return {"file": str(path), "truncated": truncated,
            "error": error, "turns": turns,
            "duration_ms": duration_ms, "cost_usd": round(cost_usd, 4),
            **totals}


def split_parent(path, outdir):
    """Carve one parent stream into per-agent files grouped by
    parent_tool_use_id. Returns (main_file, [subagent_files]) with subagents
    in first-seen order. Main messages carry a null parent id."""
    outdir = pathlib.Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    groups, order = {}, []
    for event in harness.iter_events(pathlib.Path(path).read_text(encoding="utf-8")):
        key = event.get("parent_tool_use_id") or "main"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(event)
    written = {}
    for index, key in enumerate(order):
        name = "main.jsonl" if key == "main" else f"sub-{index}.jsonl"
        target = outdir / name
        target.write_text("\n".join(json.dumps(e) for e in groups[key]) + "\n",
                          encoding="utf-8")
        written[key] = str(target)
    subs = [written[key] for key in order if key != "main"]
    return written.get("main", ""), subs


def report_parent(path, outdir):
    """Split one parent stream, then report across the carved files."""
    carved_main, carved_subs = split_parent(path, outdir)
    agents = {"main": summarize(carved_main)}
    agents["subagents"] = [summarize(sub, require_result=False)
                           for sub in carved_subs]
    total = {key: agents["main"][key] + sum(s[key] for s in agents["subagents"])
             for key in USAGE_KEYS}
    total["cost_usd"] = round(agents["main"]["cost_usd"]
                              + sum(s["cost_usd"] for s in agents["subagents"]), 4)
    agents["total"] = total
    agents["carved"] = {"main": carved_main, "subagents": carved_subs}
    return agents


def report(main_path, subagent_paths):
    agents = {"main": summarize(main_path)}
    agents["subagents"] = [summarize(path) for path in subagent_paths]
    total = {key: agents["main"][key] + sum(s[key] for s in agents["subagents"])
             for key in USAGE_KEYS}
    total["cost_usd"] = round(agents["main"]["cost_usd"]
                              + sum(s["cost_usd"] for s in agents["subagents"]), 4)
    agents["total"] = total
    return agents


def print_report(rep):
    """Shared text table. A completed run that still carries a parse error
    gets an ERROR marker: without it a failed run reads as valid and can
    enter a baseline comparison."""
    rows = [("main", rep["main"])] + [(f"sub/{pathlib.Path(s['file']).stem}", s)
                                      for s in rep["subagents"]]
    print(f"{'agent':28} {'in':>9} {'out':>9} {'cache-new':>9} "
          f"{'cache-read':>10} {'wall-s':>7} {'usd':>7}")
    for name, s in rows:
        if s["truncated"]:
            flag = " TRUNCATED"
        elif s["error"]:
            flag = " ERROR"
        else:
            flag = ""
        wall = f"{s['duration_ms'] / 1000:>7.0f}" if s["duration_ms"] else "    n/a"
        print(f"{name:28} {s['input_tokens']:>9,} {s['output_tokens']:>9,} "
              f"{s['cache_creation_input_tokens']:>9,} {s['cache_read_input_tokens']:>10,} "
              f"{wall} {s['cost_usd']:>7.2f}{flag}")
    t = rep["total"]
    print(f"{'TOTAL':28} {t['input_tokens']:>9,} {t['output_tokens']:>9,} "
          f"{t['cache_creation_input_tokens']:>9,} {t['cache_read_input_tokens']:>10,}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("main", help="main transcript, or parent stream with --split")
    parser.add_argument("subagents", nargs="*")
    parser.add_argument("--split", metavar="OUTDIR",
                        help="carve one parent stream into per-agent files first")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.split:
        rep = report_parent(args.main, args.split)
    else:
        rep = report(args.main, args.subagents)
    if args.json:
        print(json.dumps(rep, indent=2))
        return
    print_report(rep)


if __name__ == "__main__":
    main()
