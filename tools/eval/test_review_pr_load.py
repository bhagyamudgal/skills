"""Ceilings for the review-pr static load model (bhagyamudgal/skills#60, PR 1).

Every cell of tools/eval/review_pr_load.py output is pinned: a skill edit that
raises any main-context, subagent, or network number fails here. That is the
point. A legitimate increase updates the ceiling in this file alongside the
skill change, so the diff shows the cost next to the cause.

Each rule is asserted in the expensive direction only when it has one. A
ceiling nobody has seen fail is still worth pinning: the failure it prevents
is a silent 10 KB growth, not a crash.

Regeneration: tools/eval/review_pr_load.py --chunks 3, monorepo target.
`python3 tools/eval/review_pr_load.py --json` output pasted below, never
hand-edited.
"""
import json
import pathlib
import unittest

import review_pr_load
import review_pr_tokens

CORPUS_CEILING = 182987
CEILINGS = {
    "solo-main/best": (141590, 168384, 18),
    "solo-main/worst": (170242, 197036, 18),
    "parallel-standard/round-1": (147344, 174138, 20),
    "parallel-chunked/round-1": (148877, 175671, 25),
    "parallel-standard/with-step6-reload": (147344, 182742, 20),
}
DELTA_CEILINGS = {"delta_distinct": 5772, "delta_with_repeats": 5772,
                  "network": 0}
CHUNK_REVIEWER_CEILING = (32571, 32571)
SUBAGENT_CEILINGS = {
    "silent-failure-hunter": (0, 0),
    "cross-cutting": (5936, 5936),
}
PROMPT_CEILINGS = {
    "chunk-reviewer-prompt": 9673,
    "silent-failure-hunter-prompt": 383,
    "cross-cutting-prompt": 1533,
    "verifier-prompt": 5754,
}


class LoadCeilingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = review_pr_load.report(chunks=3, monorepo=True)

    def test_main_paths_within_ceilings(self):
        for name, (distinct, repeated, network) in CEILINGS.items():
            with self.subTest(path=name):
                cells = self.rep["paths"][name]
                self.assertLessEqual(cells["main_distinct"], distinct,
                                     f"{name} main-distinct grew. If the skill "
                                     f"added a file to this path, raise the "
                                     f"ceiling here in the same PR")
                self.assertLessEqual(cells["main_with_repeats"], repeated)
                self.assertLessEqual(cells["network"], network)

    def test_no_unceilinged_path(self):
        self.assertEqual(set(self.rep["paths"]),
                         set(CEILINGS) | {"any/round-2-delta"})
        for name in CEILINGS:
            with self.subTest(path=name):
                self.assertEqual(set(self.rep["paths"][name]),
                                 {"main_distinct", "main_with_repeats",
                                  "network"})
        self.assertEqual(set(self.rep["paths"]["any/round-2-delta"]),
                         set(DELTA_CEILINGS))

    def test_round2_row_is_a_delta(self):
        cells = self.rep["paths"]["any/round-2-delta"]
        for metric, ceiling in DELTA_CEILINGS.items():
            with self.subTest(metric=metric):
                self.assertLessEqual(cells[metric], ceiling)

    def test_subagent_refs_within_ceilings(self):
        for role, (distinct, repeated) in SUBAGENT_CEILINGS.items():
            with self.subTest(role=role):
                got_distinct, got_repeated = self.rep["subagent_refs"][role]
                self.assertLessEqual(got_distinct, distinct)
                self.assertLessEqual(got_repeated, repeated)

    def test_no_unceilinged_subagent(self):
        self.assertEqual(set(self.rep["subagent_refs"]),
                         {"chunk-reviewer-1", "chunk-reviewer-2",
                          "chunk-reviewer-3"} | set(SUBAGENT_CEILINGS))

    def test_chunk_reviewers_share_one_ceiling(self):
        for index in (1, 2, 3):
            with self.subTest(role=f"chunk-reviewer-{index}"):
                got = self.rep["subagent_refs"][f"chunk-reviewer-{index}"]
                self.assertLessEqual(got[0], CHUNK_REVIEWER_CEILING[0])
                self.assertLessEqual(got[1], CHUNK_REVIEWER_CEILING[1])

    def test_subagent_prompts_within_ceilings(self):
        self.assertEqual(set(self.rep["subagent_prompts"]), set(PROMPT_CEILINGS))
        for role, ceiling in PROMPT_CEILINGS.items():
            with self.subTest(role=role):
                self.assertLessEqual(self.rep["subagent_prompts"][role], ceiling)

    def test_corpus_within_ceiling(self):
        self.assertLessEqual(sum(self.rep["sizes"].values()), CORPUS_CEILING)

    def test_model_is_deterministic(self):
        again = review_pr_load.report(chunks=3, monorepo=True)
        self.assertEqual(json.dumps(self.rep, sort_keys=True),
                         json.dumps(again, sort_keys=True))

    def test_model_covers_every_skill_file(self):
        on_disk = {"SKILL.md"} | {path.name for path in
                                  (review_pr_load.SKILL_DIR / "references").glob("*.md")}
        self.assertEqual(set(review_pr_load.FILES), on_disk)

    def test_round2_delta_is_critic_round2(self):
        cells = self.rep["paths"]["any/round-2-delta"]
        self.assertEqual(cells["delta_distinct"],
                         self.rep["sizes"]["critic-round2.md"])
        self.assertEqual(cells["delta_with_repeats"],
                         self.rep["sizes"]["critic-round2.md"])

    def test_step6_reload_is_critic_verify(self):
        delta = (self.rep["paths"]["parallel-standard/with-step6-reload"]["main_with_repeats"]
                 - self.rep["paths"]["parallel-standard/round-1"]["main_with_repeats"])
        self.assertEqual(delta, self.rep["sizes"]["critic-verify.md"])


SYNTHETIC = "\n".join([
    json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}],
                "usage": {"input_tokens": 100, "output_tokens": 20,
                          "cache_creation_input_tokens": 1000,
                          "cache_read_input_tokens": 5000}}}),
    json.dumps({"type": "result", "subtype": "success", "is_error": False,
                "result": "done", "duration_ms": 90000, "total_cost_usd": 0.12,
                "num_turns": 4,
                "usage": {"input_tokens": 50, "output_tokens": 10,
                          "cache_creation_input_tokens": 500,
                          "cache_read_input_tokens": 2000}}),
])


class TokensParserTest(unittest.TestCase):
    def test_sums_event_usage_not_result_usage(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl",
                                         delete=False) as handle:
            handle.write(SYNTHETIC)
            path = handle.name
        got = review_pr_tokens.summarize(path)
        self.assertEqual(got["input_tokens"], 100)
        self.assertEqual(got["output_tokens"], 20)
        self.assertEqual(got["cache_creation_input_tokens"], 1000)
        self.assertEqual(got["cache_read_input_tokens"], 5000)
        self.assertEqual(got["duration_ms"], 90000)
        self.assertFalse(got["truncated"])
        pathlib.Path(path).unlink()

    def test_truncated_transcript_is_flagged(self):
        import tempfile
        line = SYNTHETIC.splitlines()[0]
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl",
                                         delete=False) as handle:
            handle.write(line)
            path = handle.name
        got = review_pr_tokens.summarize(path)
        self.assertTrue(got["truncated"])
        pathlib.Path(path).unlink()

    def test_completed_error_is_kept(self):
        import tempfile
        failed = SYNTHETIC.splitlines()[1].replace('"is_error": false',
                                                   '"is_error": true')
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl",
                                         delete=False) as handle:
            handle.write(SYNTHETIC.splitlines()[0] + "\n" + failed)
            path = handle.name
        got = review_pr_tokens.summarize(path)
        self.assertFalse(got["truncated"])
        self.assertIsNotNone(got["error"])
        pathlib.Path(path).unlink()

    def test_error_flag_prints(self):
        import io
        from contextlib import redirect_stdout
        rep = {"main": {"file": "m", "input_tokens": 1, "output_tokens": 1,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0, "duration_ms": 1000,
                        "cost_usd": 0.0, "truncated": False,
                        "error": "api error 500"},
               "subagents": [],
               "total": {"input_tokens": 1, "output_tokens": 1,
                         "cache_creation_input_tokens": 0,
                         "cache_read_input_tokens": 0, "cost_usd": 0.0}}
        out = io.StringIO()
        with redirect_stdout(out):
            review_pr_tokens.print_report(rep)
        self.assertIn("ERROR", out.getvalue())
        self.assertNotIn("TRUNCATED", out.getvalue())

    def test_split_groups_by_parent_tool_use_id(self):
        import tempfile
        main_event = json.dumps({"type": "assistant",
                                 "parent_tool_use_id": None,
                                 "message": {"content": [{"type": "text",
                                                          "text": "go"}],
                                             "usage": {"input_tokens": 10,
                                                       "output_tokens": 2,
                                                       "cache_creation_input_tokens": 0,
                                                       "cache_read_input_tokens": 0}}})
        sub_event = json.dumps({"type": "assistant",
                                "parent_tool_use_id": "toolu_1",
                                "message": {"content": [{"type": "text",
                                                         "text": "found"}],
                                            "usage": {"input_tokens": 40,
                                                      "output_tokens": 5,
                                                      "cache_creation_input_tokens": 0,
                                                      "cache_read_input_tokens": 0}}})
        result = json.dumps({"type": "result", "subtype": "success",
                             "is_error": False, "result": "done",
                             "duration_ms": 5000, "total_cost_usd": 0.01,
                             "usage": {"input_tokens": 1000,
                                       "output_tokens": 200,
                                       "cache_creation_input_tokens": 0,
                                       "cache_read_input_tokens": 0}})
        with tempfile.TemporaryDirectory() as tmp:
            parent = pathlib.Path(tmp) / "parent.jsonl"
            parent.write_text(main_event + "\n" + sub_event + "\n" + result + "\n")
            carved_main, carved_subs = review_pr_tokens.split_parent(
                str(parent), str(pathlib.Path(tmp) / "agents"))
            self.assertEqual(len(carved_subs), 1)
            rep = review_pr_tokens.report_parent(str(parent),
                                                 str(pathlib.Path(tmp) / "agents"))
        self.assertEqual(rep["main"]["input_tokens"], 10)
        self.assertEqual(len(rep["subagents"]), 1)
        self.assertEqual(rep["subagents"][0]["input_tokens"], 40)
        self.assertFalse(rep["subagents"][0]["truncated"])
        self.assertEqual(rep["subagents"][0]["duration_ms"], 0)
        self.assertEqual(rep["total"]["input_tokens"], 50)
        self.assertEqual(rep["main"]["duration_ms"], 5000)
        self.assertTrue(carved_main.endswith("main.jsonl"))


if __name__ == "__main__":
    unittest.main()
