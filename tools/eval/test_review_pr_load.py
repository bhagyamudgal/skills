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
    "solo-main/best": (147344, 174138, 11),
    "solo-main/worst": (170242, 197036, 11),
    "parallel-standard/round-1": (147344, 174138, 13),
    "parallel-chunked/round-1": (147344, 174138, 18),
    "parallel-standard/with-step6-reload": (147344, 182742, 13),
    "any/round-2-delta": (153116, 179910, 0),
}
SUBAGENT_CEILINGS = {
    "chunk-reviewer-1": (32571, 32571),
    "cross-cutting": (5936, 5936),
    "silent-failure-hunter": (0, 0),
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

    def test_subagent_refs_within_ceilings(self):
        for role, (distinct, repeated) in SUBAGENT_CEILINGS.items():
            with self.subTest(role=role):
                got_distinct, got_repeated = self.rep["subagent_refs"][role]
                self.assertLessEqual(got_distinct, distinct)
                self.assertLessEqual(got_repeated, repeated)

    def test_subagent_prompts_within_ceilings(self):
        for role, ceiling in PROMPT_CEILINGS.items():
            with self.subTest(role=role):
                self.assertLessEqual(self.rep["subagent_prompts"][role], ceiling)

    def test_corpus_within_ceiling(self):
        self.assertLessEqual(sum(self.rep["sizes"].values()), CORPUS_CEILING)

    def test_model_is_deterministic(self):
        again = review_pr_load.report(chunks=3, monorepo=True)
        self.assertEqual(json.dumps(self.rep, sort_keys=True),
                         json.dumps(again, sort_keys=True))

    def test_every_modeled_file_exists(self):
        for name in review_pr_load.FILES:
            with self.subTest(file=name):
                base = (review_pr_load.SKILL_DIR if name == "SKILL.md"
                        else review_pr_load.REF)
                self.assertTrue((base / name).exists(),
                                f"{name} is in the model but not on disk. A "
                                f"load pointer that resolves to nothing fails "
                                f"silently at review time")

    def test_round2_delta_is_critic_round2(self):
        delta = (self.rep["paths"]["any/round-2-delta"]["main_distinct"]
                 - self.rep["paths"]["parallel-chunked/round-1"]["main_distinct"])
        self.assertEqual(delta, self.rep["sizes"]["critic-round2.md"])

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


if __name__ == "__main__":
    unittest.main()
