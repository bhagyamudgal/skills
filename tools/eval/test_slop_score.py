#!/usr/bin/env python3
"""Offline tests for tools/eval/slop_score.py.

The first test is the one that matters. A scorer that cannot separate hand-written slop
from hand-written plain prose will not detect anything subtler, and every register number
built on it would be noise wearing a decimal point.

    python3 tools/eval/test_slop_score.py
"""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import slop_score

SLOP = """## Understanding The Key Considerations

Additionally, it is important to note that this pivotal decision serves as a testament to
the evolving landscape of modern engineering. The comprehensive framework is designed to
seamlessly enhance productivity, showcasing a robust approach that leverages numerous
cutting-edge paradigms.

Experts believe this is not just an improvement, but a groundbreaking shift. Furthermore,
the intricate interplay could potentially possibly facilitate a streamlined workflow.
Despite challenges, the system continues to thrive.

I hope this helps! Let me know if you would like me to delve deeper.
"""

PLAIN = """## What changed

The scheduler used to hold a lock while it wrote to disk. Under load that serialized every
writer behind one slow fsync, so p99 latency tracked disk speed rather than queue depth.

I moved the write outside the lock. The lock now covers only the queue mutation, which
takes about 40 nanoseconds.

There is one catch. Two writers can now interleave their writes, so the file needs a
sequence number per record to stay reconstructable. I added one. It costs 8 bytes a record.

p99 went from 340ms to 12ms on the staging load test. I have not tried it under the
production write mix, which is roughly 4x heavier.
"""


class Separation(unittest.TestCase):
    """The scorer's reason to exist. If this fails, nothing downstream means anything."""

    def setUp(self):
        self.slop = slop_score.score(SLOP)
        self.plain = slop_score.score(PLAIN)

    def test_slop_scores_far_higher(self):
        self.assertGreater(self.slop["tells_per_100w"], 10.0)
        self.assertLess(self.plain["tells_per_100w"], 1.0)

    def test_the_gap_is_an_order_of_magnitude(self):
        self.assertGreater(self.slop["tells_per_100w"],
                           self.plain["tells_per_100w"] * 10 + 5)

    def test_nominalisation_separates_them_too(self):
        slop_rate = self.slop["measures"]["nominalisation_per_100w"]
        plain_rate = self.plain["measures"]["nominalisation_per_100w"]
        self.assertGreater(slop_rate, plain_rate * 2)

    def test_plain_prose_is_not_scored_as_perfect_by_accident(self):
        # Guards against the scorer silently matching nothing at all, which would make
        # every text look clean and every delta look like a null result.
        self.assertGreater(self.plain["words"], 50)
        self.assertGreater(self.plain["sentences"], 5)


class Rules(unittest.TestCase):
    def setUp(self):
        self.rules, self.measures = slop_score.load_rules()

    def _count(self, text, rule_name):
        return slop_score.score(text, self.rules, self.measures)["rules"][rule_name]["count"]

    def test_every_rule_has_a_compiled_pattern(self):
        self.assertGreater(len(self.rules), 15)
        for rule in self.rules:
            self.assertTrue(hasattr(rule["regex"], "search"), rule["name"])

    def test_ai_vocabulary(self):
        self.assertEqual(self._count("We must delve into the crucial tapestry.",
                                     "ai-vocabulary"), 3)
        self.assertEqual(self._count("We read the file and fixed the bug.",
                                     "ai-vocabulary"), 0)

    def test_ai_vocabulary_respects_word_boundaries(self):
        # "enhance" must not fire inside "enhancement" handling, and "realm" not in "realms"
        # is fine, but a substring match would flag "crucially" as "crucial".
        self.assertEqual(self._count("delved", "ai-vocabulary"), 0)

    def test_trailing_ing_clause_needs_the_comma(self):
        self.assertEqual(self._count("It caches results, ensuring low latency.",
                                     "trailing-ing-clause"), 1)
        self.assertEqual(self._count("Ensuring low latency means caching.",
                                     "trailing-ing-clause"), 0)

    def test_not_just_but(self):
        self.assertEqual(self._count("This is not just fast, but correct.",
                                     "not-just-but"), 1)
        self.assertEqual(self._count("This is not fast. But it is correct.",
                                     "not-just-but"), 0)

    def test_stacked_hedge(self):
        self.assertEqual(self._count("It could potentially break.", "stacked-hedge"), 1)
        self.assertEqual(self._count("It could break.", "stacked-hedge"), 0)

    def test_em_and_en_dash(self):
        self.assertEqual(self._count("one — two", "em-dash"), 1)
        self.assertEqual(self._count("one – two", "en-dash"), 1)
        self.assertEqual(self._count("one - two", "em-dash"), 0)

    def test_curly_quote(self):
        self.assertEqual(self._count("“hello” and it’s", "curly-quote"), 3)
        self.assertEqual(self._count('"hello" and it\'s', "curly-quote"), 0)

    def test_inline_header_list_is_line_anchored(self):
        self.assertEqual(self._count("- **Performance:** it got faster",
                                     "inline-header-list"), 1)
        self.assertEqual(self._count("we measured **latency** at p99",
                                     "inline-header-list"), 0)

    def test_passive_voice(self):
        self.assertEqual(self._count("The file is parsed by the loader.", "passive-voice"), 1)
        self.assertEqual(self._count("The loader parses the file.", "passive-voice"), 0)

    def test_fancy_synonym(self):
        self.assertEqual(self._count("We utilize it to leverage the API.",
                                     "fancy-synonym"), 2)
        self.assertEqual(self._count("We use it to call the API.", "fancy-synonym"), 0)

    def test_unknown_kind_is_rejected_loudly(self):
        bad = pathlib.Path(slop_score.HERE) / "_bad_rules_for_test.json"
        bad.write_text(json.dumps({
            "rules": [{"id": 1, "name": "x", "kind": "telepathy", "terms": []}],
            "measures": {"adverb_exceptions": [], "nominalisation_suffixes": []},
        }))
        try:
            with self.assertRaises(ValueError):
                slop_score.load_rules(bad)
        finally:
            bad.unlink()

    def test_empty_rule_set_is_rejected(self):
        empty = pathlib.Path(slop_score.HERE) / "_empty_rules_for_test.json"
        empty.write_text(json.dumps({
            "rules": [],
            "measures": {"adverb_exceptions": [], "nominalisation_suffixes": []},
        }))
        try:
            with self.assertRaises(ValueError):
                slop_score.load_rules(empty)
        finally:
            empty.unlink()


class CodeStripping(unittest.TestCase):
    def test_fenced_blocks_do_not_dilute_the_rate(self):
        prose = "Additionally, this is crucial.\n"
        padding = "\n".join(f"const value{n} = {n};" for n in range(200))
        with_code = prose + f"\n```js\n{padding}\n```\n"
        bare = slop_score.score(prose)
        fenced = slop_score.score(with_code)
        self.assertEqual(bare["words"], fenced["words"])
        self.assertEqual(bare["tells_per_100w"], fenced["tells_per_100w"])

    def test_tilde_fences_are_stripped_too(self):
        scored = slop_score.score("Real prose here.\n\n~~~\nutilize leverage delve\n~~~\n")
        self.assertEqual(scored["rules"]["fancy-synonym"]["count"], 0)


class Robustness(unittest.TestCase):
    def test_empty_text_does_not_divide_by_zero(self):
        scored = slop_score.score("")
        self.assertEqual(scored["words"], 0)
        self.assertEqual(scored["tells_per_100w"], 0.0)
        self.assertEqual(scored["measures"]["sentence_words_stdev"], 0.0)

    def test_single_sentence_has_no_stdev(self):
        scored = slop_score.score("One sentence only.")
        self.assertEqual(scored["measures"]["sentence_words_stdev"], 0.0)

    def test_code_only_input_does_not_crash(self):
        scored = slop_score.score("```\nx = 1\n```\n")
        self.assertEqual(scored["words"], 0)


class Delta(unittest.TestCase):
    def test_improvement_reads_negative(self):
        change = slop_score.delta(slop_score.score(SLOP), slop_score.score(PLAIN))
        self.assertLess(change["tells_per_100w"], 0)

    def test_no_change_is_zero(self):
        scored = slop_score.score(PLAIN)
        change = slop_score.delta(scored, scored)
        self.assertEqual(change["tells_per_100w"], 0)
        self.assertEqual(change["rules"], {})

    def test_unchanged_rules_are_omitted(self):
        change = slop_score.delta(slop_score.score(SLOP), slop_score.score(PLAIN))
        self.assertIn("ai-vocabulary", change["rules"])
        self.assertLess(change["rules"]["ai-vocabulary"], 0)


class DriftExtraction(unittest.TestCase):
    def test_parses_the_live_rule_shape(self):
        text = ("7. **AI vocabulary.** Additionally, crucial, delve, landscape (abstract), "
                "vibrant. Replace with plain words.\n")
        self.assertEqual(slop_score.extract_live_vocabulary(text),
                         {"additionally", "crucial", "delve", "landscape", "vibrant"})

    def test_returns_none_when_the_shape_moved(self):
        self.assertIsNone(slop_score.extract_live_vocabulary("no such rule here"))

    def test_vendored_list_covers_the_live_one(self):
        """The drift check itself, run as a test so a stale vendor fails the suite."""
        if not slop_score.LIVE_UNSLOP.is_file():
            self.skipTest(f"{slop_score.LIVE_UNSLOP} is user-local and not on this machine")
        live = slop_score.extract_live_vocabulary(slop_score.LIVE_UNSLOP.read_text())
        self.assertIsNotNone(live, "rule 7 no longer parses out of the live skill")
        spec = json.loads(slop_score.RULES_FILE.read_text())
        vendored = {t.lower() for r in spec["rules"] for t in r.get("terms", [])}
        self.assertEqual(live - vendored, set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
