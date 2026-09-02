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


class ProseFences(unittest.TestCase):
    """The defect that made the first baseline run measure the wrong text. A model asked for
    a PR body fences it so it can be copy-pasted, and stripping every fence scored the chat
    commentary about the body instead of the body."""

    def test_a_markdown_fence_is_kept(self):
        text = "Here is the body.\n\n```markdown\nWe utilize the delve approach.\n```\n"
        scored = slop_score.score(text)
        self.assertEqual(scored["rules"]["fancy-synonym"]["count"], 1)
        self.assertEqual(scored["rules"]["ai-vocabulary"]["count"], 1)

    def test_a_bare_fence_is_kept_because_titles_use_one(self):
        scored = slop_score.score("Title:\n\n```\nfix(x): utilize the thing\n```\n")
        self.assertEqual(scored["rules"]["fancy-synonym"]["count"], 1)

    def test_a_diff_fence_is_dropped(self):
        scored = slop_score.score("Body.\n\n```diff\n- utilize delve crucial\n```\n")
        self.assertEqual(scored["rules"]["fancy-synonym"]["count"], 0)
        self.assertEqual(scored["rules"]["ai-vocabulary"]["count"], 0)

    def test_named_code_languages_are_dropped(self):
        for language in ("python", "ts", "bash", "json", "sql", "yaml"):
            scored = slop_score.score(f"Body.\n\n```{language}\nutilize delve\n```\n")
            self.assertEqual(scored["rules"]["fancy-synonym"]["count"], 0, language)

    def test_prose_fence_words_reach_the_word_count(self):
        bare = slop_score.score("Short intro here.\n")
        fenced = slop_score.score(
            "Short intro here.\n\n```markdown\nOne two three four five six.\n```\n")
        self.assertGreater(fenced["words"], bare["words"] + 5)


class TellDeduplication(unittest.TestCase):
    def test_a_term_filed_under_two_rules_counts_once_in_the_total(self):
        # "great question" is both a chatbot phrase and sycophancy. Summing the rules would
        # weight it double against every other tell.
        scored = slop_score.score("Great question, here is the answer to it now.")
        self.assertEqual(scored["rules"]["chatbot-phrase"]["count"], 1)
        self.assertEqual(scored["rules"]["sycophancy"]["count"], 1)
        raw_sum = sum(h["count"] for h in scored["rules"].values())
        total = scored["tells_per_100w"] * scored["words"] / 100.0
        self.assertLess(round(total), raw_sum)

    def test_distinct_tells_still_add_up(self):
        scored = slop_score.score("We utilize it. Additionally, it is crucial.")
        total = round(scored["tells_per_100w"] * scored["words"] / 100.0)
        self.assertEqual(total, 3)


class RuleDataFixes(unittest.TestCase):
    def test_an_arrow_is_not_an_emoji(self):
        # `->` is the format the global rules prescribe for completion reports.
        self.assertEqual(slop_score.score("Old logic → new logic.")["rules"]["emoji"]["count"], 0)

    def test_a_real_emoji_still_counts(self):
        self.assertEqual(slop_score.score("Nice \U0001F600 work.")["rules"]["emoji"]["count"], 1)

    def test_sycophancy_is_word_anchored(self):
        self.assertEqual(
            slop_score.score("The server was spot online all day.")["rules"]["sycophancy"]["count"], 0)
        self.assertEqual(slop_score.score("That is spot on.")["rules"]["sycophancy"]["count"], 1)

    def test_nominalisation_suffixes_are_unique(self):
        _, measures = slop_score.load_rules()
        suffixes = measures["nominalisation_suffixes"]
        self.assertEqual(len(suffixes), len(set(suffixes)))

    def test_a_partially_parsed_vocabulary_is_rejected(self):
        # The guard that matters: a regex that clips the list returns one term, and a drift
        # check comparing one term passes while comparing nothing.
        clipped = "**AI vocabulary.** delve. Replace with plain words. Also: leverage, robust."
        self.assertIsNone(slop_score.extract_live_vocabulary(clipped))


class CodeStripping(unittest.TestCase):
    def test_fenced_blocks_do_not_dilute_the_rate(self):
        prose = "Additionally, this is crucial.\n"
        padding = "\n".join(f"const value{n} = {n};" for n in range(200))
        with_code = prose + f"\n```js\n{padding}\n```\n"
        bare = slop_score.score(prose)
        fenced = slop_score.score(with_code)
        self.assertEqual(bare["words"], fenced["words"])
        self.assertEqual(bare["tells_per_100w"], fenced["tells_per_100w"])

    def test_tilde_code_fences_are_stripped_too(self):
        scored = slop_score.score("Real prose here.\n\n~~~python\nutilize leverage delve\n~~~\n")
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
        scored = slop_score.score("```python\nx = 1\n```\n")
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
        text = ("7. **AI vocabulary.** Additionally, crucial, delve, enduring, enhance, "
                "garner, interplay, intricate, landscape (abstract), pivotal, showcase, "
                "vibrant. Replace with plain words.\n")
        self.assertEqual(
            slop_score.extract_live_vocabulary(text),
            {"additionally", "crucial", "delve", "enduring", "enhance", "garner",
             "interplay", "intricate", "landscape", "pivotal", "showcase", "vibrant"})

    def test_returns_none_when_the_shape_moved(self):
        self.assertIsNone(slop_score.extract_live_vocabulary("no such rule here"))

    def test_vendored_list_covers_the_live_one(self):
        """The drift check itself, run as a test so a stale vendor fails the suite."""
        live_path = slop_score.find_live_unslop()
        if live_path is None:
            self.skipTest("no installed unslop on this machine; it is user-local")
        live = slop_score.extract_live_vocabulary(live_path.read_text())
        self.assertIsNotNone(live, "rule 7 no longer parses out of the live skill")
        spec = json.loads(slop_score.RULES_FILE.read_text())
        vendored = {t.lower() for r in spec["rules"] for t in r.get("terms", [])}
        self.assertEqual(live - vendored, set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
