#!/usr/bin/env python3
"""Static context accounting for the review-pr skill.

Walks the load pointers in skills/review-pr/SKILL.md ("## Reference files": which
reader loads which file on which branch) and prints, per run path, the bytes main
loads (distinct and with repeats), the bytes each dispatched subagent receives, and
the prescribed gh network call count.

Static numbers are the repeatable check from bhagyamudgal/skills#60: live token
counts move with the model and the diff, but a skill edit that adds a file to a
hot path shows up here deterministically. tools/eval/test_review_pr_load.py pins
every cell below as a ceiling, so a later PR that raises any of them fails the
suite. Live tokens and wall time come from tools/eval/review_pr_tokens.py.

Model assumptions the skill text leaves open (see #60 decision 6), each
encoded in exactly one place below so a later PR can flip it and watch the
ceilings move. Monorepo: the target has packages/ or apps/, so main loads
repo-map.md (--no-monorepo drops it). Main never loads
finding-output-format.md; only finding emitters (Subagent 1, Subagent 3, V3)
do. V1/V2 report compact verdicts and load no references; V3 emits findings
and loads finding-output-format.md. Subagent prompts are counted by source
file: reviewer-prompt.md is the whole Subagent 1 prompt,
cross-cutting-prompt.md the whole Subagent 3 prompt,
verification-subagents.md the whole V1/V2/V3 prompts, and the hunter packet
is the fenced block under "Subagent 2" in dispatch-prompts.md.

Usage:
    python3 tools/eval/review_pr_load.py [--chunks N] [--json] [--no-monorepo]
"""
import argparse
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SKILL_DIR = HERE.parents[1] / "skills" / "review-pr"
REF = SKILL_DIR / "references"


def size(name):
    path = SKILL_DIR / name if name == "SKILL.md" else REF / name
    return path.stat().st_size


FILES = [
    "SKILL.md",
    "batch-mode.md",
    "class-sweep-and-inverse-risk.md",
    "critic-round2.md",
    "critic-verify.md",
    "cross-cutting-prompt.md",
    "dispatch-prompts.md",
    "false-positive-rules.md",
    "finding-output-format.md",
    "finding-state-phase4.md",
    "finding-state-schema.md",
    "github-posting.md",
    "github-posting-recovery.md",
    "github-posting-rerun.md",
    "phase1-timeline-state.md",
    "q5-type-coercion.md",
    "q6-cross-repo.md",
    "q6-reusability-search.md",
    "repo-map.md",
    "reviewer-prompt.md",
    "schema-design-checks.md",
    "verification-subagents.md",
]

# Assumptions the skill text leaves open (see #60 decision 6). Each is encoded in
# exactly one place below so a later PR can flip it and watch the ceilings move.
#  - Monorepo: the target repo has packages/ or apps/, so main loads repo-map.md.
#    --no-monorepo drops it.
#  - Main never loads finding-output-format.md. Only finding emitters (Subagent 1,
#    Subagent 3, V3) do; the skill never tells main to open it.
#  - V1/V2 report compact verdicts and load no references. V3 emits findings and
#    loads finding-output-format.md.
#  - Subagent prompts are counted by their source file: reviewer-prompt.md is the
#    whole Subagent 1 prompt, cross-cutting-prompt.md the whole Subagent 3
#    prompt, verification-subagents.md the whole V1/V2/V3 prompts. The hunter
#    packet is the fenced block under "Subagent 2" in dispatch-prompts.md.
MAIN_ALWAYS = [
    "SKILL.md",
    "reviewer-prompt.md",
    "dispatch-prompts.md",
    "phase1-timeline-state.md",
    "finding-state-schema.md",
    "github-posting.md",
    "critic-verify.md",
    "repo-map.md",
]

MAIN_IF_FINDINGS = ["false-positive-rules.md"]
MAIN_IF_CODE_CHANGE_FINDINGS = ["verification-subagents.md"]

SOLO_INLINE_BEST = []
SOLO_INLINE_WORST = [
    "q5-type-coercion.md",
    "q6-reusability-search.md",
    "class-sweep-and-inverse-risk.md",
    "finding-output-format.md",
    "schema-design-checks.md",
]

SUBAGENT_1_ALWAYS = ["reviewer-prompt.md", "finding-output-format.md"]
SUBAGENT_1_COND = [
    "q5-type-coercion.md",
    "q6-reusability-search.md",
    "class-sweep-and-inverse-risk.md",
    "schema-design-checks.md",
]


def hunter_prompt_bytes():
    text = (REF / "dispatch-prompts.md").read_text(encoding="utf-8")
    start = text.index("### Subagent 2")
    fence = text.index("```", start)
    close = text.index("```", fence + 3)
    return len(text[fence + 3:close].encode("utf-8"))


def main_loads(mode, worst=False, round2=False, step6_reload=False, monorepo=True):
    """Ordered file list main loads, repeats kept. Solo-main runs the Subagent
    1 prompt inline, so the reviewer references land in main: best case the
    diff has no DB/API payload, no new definitions, and no code-change
    finding, worst case all three plus schema checks. The cross-cutting
    prompt loads only in parallel-chunked, the only mode that dispatches
    Subagent 3. The trailing phase4 entry is the Phase 4 write-back file,
    loaded after posting; the rerun and recovery posting files load only on
    re-runs and failures and stay out of the fresh-run paths. The
    critic-verify entry is the step-6 reload for findings routed back
    through 4.55/4.56."""
    loads = [f for f in MAIN_ALWAYS if monorepo or f != "repo-map.md"]
    if mode == "parallel-chunked":
        loads += ["cross-cutting-prompt.md"]
    if mode == "solo-main" and worst:
        loads += SOLO_INLINE_WORST
    loads += MAIN_IF_FINDINGS
    if mode != "solo-main" or worst:
        loads += MAIN_IF_CODE_CHANGE_FINDINGS
    loads += ["finding-state-phase4.md"]
    if step6_reload:
        loads += ["critic-verify.md"]
    if round2:
        loads += ["critic-round2.md"]
    return loads


def subagent_loads(chunks, hunter=True, worst=True):
    """role -> ordered reference list. Chunk reviewers share one shape."""
    cond = SUBAGENT_1_COND if worst else []
    out = {}
    for i in range(chunks):
        out[f"chunk-reviewer-{i + 1}"] = SUBAGENT_1_ALWAYS + cond
    if hunter:
        out["silent-failure-hunter"] = []
    out["cross-cutting"] = ["cross-cutting-prompt.md", "finding-output-format.md"]
    return out


def network_calls(mode, chunks=1, hunter=True, linked_issues=0,
                  file_level_findings=0, cross_repo=True):
    """Prescribed gh calls. Phase 1 is view, diff, the post-diff OID re-read,
    viewer, author, cwd repo lookup, threads and coderabbit-config, plus the
    tree fetch and suppressions read when cross-repo, plus one fetch per
    linked issue. Subagent fetches counted: every chunk reviewer runs
    `gh pr diff` plus `gh pr view --json files`, the hunter and
    cross-cutting reviewer each fetch the diff, and Subagent 3 dispatches
    only in parallel-chunked. Phase 4 is the prior-review query, the hunk
    fetch, create, the create read-backs, submit, the submit read-back, and
    one GraphQL call per file-level thread. Evidence fetches inside
    V1/V2/V3, re-run thread resolution, and the Phase 4 garbage sweep are
    unbounded by the text and reported separately."""
    phase1 = 10 if cross_repo else 8
    phase1 += linked_issues
    if mode == "solo-main":
        phase2 = (1 if hunter else 0)
    elif mode == "parallel-standard":
        phase2 = 2 + (1 if hunter else 0)
    else:
        phase2 = 2 * chunks + (1 if hunter else 0) + 1
    phase4 = 7 + file_level_findings
    return {"phase1": phase1, "phase2": phase2, "phase4": phase4,
            "total": phase1 + phase2 + phase4}


def report(chunks=3, monorepo=True):
    sizes = {f: size(f) for f in FILES}

    def sums(loads):
        distinct = sum(sizes[f] for f in dict.fromkeys(loads))
        repeated = sum(sizes[f] for f in loads)
        return distinct, repeated

    paths = {}
    for mode in ("solo-main", "parallel-standard", "parallel-chunked"):
        n = chunks if mode == "parallel-chunked" else (1 if mode == "parallel-standard" else 0)
        for variant, kw in (
            ("best", {"worst": False}),
            ("worst", {"worst": True}),
        ):
            if mode != "solo-main" and variant == "best":
                continue
            loads = main_loads(mode, round2=False, monorepo=monorepo, **kw)
            d, r = sums(loads)
            net = network_calls(mode, chunks=n or 1)
            paths[f"{mode}/{variant if mode == 'solo-main' else 'round-1'}"] = {
                "main_distinct": d, "main_with_repeats": r, "network": net["total"],
            }
    std = main_loads("parallel-standard", monorepo=monorepo)
    d, r = sums(std + ["critic-verify.md"])
    paths["parallel-standard/with-step6-reload"] = {
        "main_distinct": sums(std)[0], "main_with_repeats": r,
        "network": network_calls("parallel-standard", chunks=1)["total"],
    }
    r2 = main_loads("parallel-chunked", worst=True, round2=True, monorepo=monorepo)
    r1 = main_loads("parallel-chunked", worst=True, round2=False, monorepo=monorepo)
    d2, r2s = sums(r2)
    d1, r1s = sums(r1)
    paths["any/round-2-delta"] = {"delta_distinct": d2 - d1,
                                  "delta_with_repeats": r2s - r1s, "network": 0}

    subs = subagent_loads(chunks)
    sub_bytes = {role: sums(loads) for role, loads in subs.items()}
    sub_prompts = {
        "chunk-reviewer-prompt": sizes["reviewer-prompt.md"],
        "silent-failure-hunter-prompt": hunter_prompt_bytes(),
        "cross-cutting-prompt": sizes["cross-cutting-prompt.md"],
        "verifier-prompt": sizes["verification-subagents.md"],
    }
    return {"sizes": sizes, "paths": paths, "subagent_refs": sub_bytes,
            "subagent_prompts": sub_prompts, "chunks": chunks}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chunks", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-monorepo", action="store_true")
    args = parser.parse_args()
    rep = report(chunks=args.chunks, monorepo=not args.no_monorepo)
    if args.json:
        print(json.dumps(rep, indent=2))
        return
    print(f"review-pr static load accounting ({args.chunks}-chunk baseline, "
          f"{'monorepo' if not args.no_monorepo else 'non-monorepo'} target)")
    print(f"{'path':42} {'main distinct':>14} {'with repeats':>13} {'network':>8}")
    for name, cells in rep["paths"].items():
        net = cells["network"] or "-"
        if "delta_distinct" in cells:
            print(f"{name:42} {cells['delta_distinct']:>14,} "
                  f"{cells['delta_with_repeats']:>13,} {net:>8}")
        else:
            print(f"{name:42} {cells['main_distinct']:>14,} "
                  f"{cells['main_with_repeats']:>13,} {net:>8}")
    print("\nper-subagent references (distinct, with repeats):")
    for role, (d, r) in rep["subagent_refs"].items():
        print(f"  {role:24} {d:>8,} {r:>8,}")
    print("subagent prompt sources:")
    for role, n in rep["subagent_prompts"].items():
        print(f"  {role:24} {n:>8,}")
    print(f"\ncorpus: {sum(rep['sizes'].values()):,} bytes across "
          f"{len(rep['sizes'])} files")


if __name__ == "__main__":
    main()
