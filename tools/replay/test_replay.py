#!/usr/bin/env python3
"""Unit tests for the replay harness.

Every fixture here is invented. Nothing in this file — no repo name, path, claim text or
verdict — is copied out of the private benchmark, so the tests can live in a public repo
and still exercise the real code paths.

    python3 tools/replay/test_replay.py
"""
import contextlib
import io
import json
import pathlib
import random
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import benchmark as bench
import match as matcher
import perturb
import run as runner
import score


def frozen(fid, path, line, claim, verdict="CORRECT", pr=7,
           source="review-pr-skill", severity="serious", corpus="synthetic"):
    return {"id": fid, "corpus": corpus, "source": source, "pr": pr, "path": path,
            "line_start": line, "line_end": line, "claim": claim,
            "severity_raw": severity, "severity": severity,
            "tier": bench._tier(source, severity), "verdict": verdict,
            "anchor_quality": "exact"}


class TestMatcher(unittest.TestCase):
    def setUp(self):
        self.frozens = [
            frozen("F1", "src/alpha/parser.ts", 100,
                   "parseWidget swallows a malformed payload and returns an empty list"),
            frozen("F2", "src/beta/store.ts", 40,
                   "saveWidget writes before validateOwner runs, so a foreign tenant wins",
                   verdict="FALSE_POSITIVE"),
        ]

    def test_identical_finding_matches(self):
        result = matcher.match([dict(self.frozens[0])], self.frozens)
        self.assertEqual(len(result["matched"]), 1)
        self.assertEqual(result["matched"][0]["frozen"]["id"], "F1")

    def test_line_drift_and_rewording_still_match(self):
        replay = [{"id": "R1", "pr": 7, "path": "src/alpha/parser.ts", "line_start": 112,
                   "claim": "malformed payload is swallowed by parseWidget, "
                            "which returns an empty list instead of raising"}]
        result = matcher.match(replay, self.frozens)
        self.assertEqual(len(result["matched"]), 1)
        self.assertEqual(result["matched"][0]["frozen"]["id"], "F1")

    def test_different_file_never_matches(self):
        replay = [dict(self.frozens[0], id="R1", path="src/gamma/other.ts")]
        result = matcher.match(replay, self.frozens)
        self.assertEqual(result["matched"], [])
        self.assertEqual(len(result["unmatched_replay"]), 1)

    def test_different_pr_never_matches(self):
        replay = [dict(self.frozens[0], id="R1", pr=99)]
        result = matcher.match(replay, self.frozens)
        self.assertEqual(result["matched"], [])

    def test_duplicate_replays_do_not_both_absorb_one_verdict(self):
        replay = [dict(self.frozens[0], id="R1"), dict(self.frozens[0], id="R2")]
        result = matcher.match(replay, self.frozens)
        self.assertEqual(len(result["matched"]), 1)
        self.assertEqual(len(result["unmatched_replay"]), 1)

    def test_unmatched_frozen_is_reported(self):
        result = matcher.match([dict(self.frozens[0])], self.frozens)
        self.assertEqual([f["id"] for f in result["unmatched_frozen"]], ["F2"])

    def test_missing_line_does_not_penalise(self):
        with_line = matcher.score_pair(dict(self.frozens[0]), self.frozens[0])[0]
        without = matcher.score_pair(dict(self.frozens[0], line_start=None),
                                     self.frozens[0])[0]
        self.assertAlmostEqual(with_line, 1.0, places=6)
        self.assertAlmostEqual(without, 1.0, places=6)

    def test_same_basename_different_tree_scores_below_exact(self):
        self.assertEqual(matcher.path_score("a/b/index.ts", "a/b/index.ts"), 1.0)
        self.assertEqual(matcher.path_score("a/b/index.ts", "c/b/index.ts"), 0.85)
        self.assertEqual(matcher.path_score("a/b/index.ts", "c/d/index.ts"), 0.70)
        self.assertEqual(matcher.path_score("a/b/index.ts", "a/b/other.ts"), 0.0)


class TestGrading(unittest.TestCase):
    def test_false_positive_rate_and_headline(self):
        frozens = [frozen(f"F{i}", "src/a/x.ts", i * 10, f"claim number {i} about thing")
                   for i in range(9)]
        frozens.append(frozen("F9", "src/a/y.ts", 5, "a bad claim about nothing real",
                              verdict="FALSE_POSITIVE"))
        result = matcher.match([dict(f) for f in frozens], frozens)
        buckets = score.grade(result)
        head = score.headline_rates(buckets)
        self.assertEqual(head["review-pr-skill"]["graded"], 10)
        self.assertEqual(head["review-pr-skill"]["false"], 1)
        self.assertEqual(head["review-pr-skill"]["verdict"], "FAIL")

    def test_correct_trivial_is_not_a_false_positive(self):
        frozens = [frozen("F1", "src/a/x.ts", 1, "a cosmetic claim",
                          verdict="CORRECT_TRIVIAL")]
        buckets = score.grade(matcher.match([dict(frozens[0])], frozens))
        self.assertEqual(buckets[("synthetic", "review-pr-skill", "high")]["false"], 0)
        self.assertEqual(buckets[("synthetic", "review-pr-skill", "high")]["graded"], 1)

    def test_wilson_bounds(self):
        self.assertEqual(score.wilson95(0, 0), [0.0, 0.0])
        lo, hi = score.wilson95(0, 36)
        self.assertEqual(lo, 0.0)
        self.assertTrue(0.09 < hi < 0.10)


def replay_of(record, **overrides):
    """A replay finding for the same construct, re-emitted with its own severity/source."""
    row = dict(record, id=f"R-{record['id']}", **overrides)
    row["severity_raw"] = row["severity"]
    row["tier"] = bench._tier(row["source"], row["severity"])
    return row


class TestBucketAttribution(unittest.TestCase):
    """Buckets describe what the run emitted; only the verdict comes from the benchmark."""

    def test_a_de_escalated_false_positive_leaves_the_high_tier_rate(self):
        """Emitting a Critical-graded false positive as Minor is a de-escalation, and the
        high-tier rate must stop counting it — the tier is a property of this run."""
        frozens = [frozen("F1", "src/a/x.ts", 10, "widgetCache is never invalidated",
                          verdict="FALSE_POSITIVE", severity="critical")]
        replay = [replay_of(frozens[0], severity="minor")]
        buckets = score.grade(matcher.match(replay, frozens))
        head = score.headline_rates(buckets)
        self.assertNotIn("review-pr-skill", head)
        self.assertEqual(buckets[("synthetic", "review-pr-skill", "low")]["false"], 1)

    def test_an_escalated_finding_enters_the_high_tier_denominator(self):
        """A trivial claim re-emitted as Critical is a severity regression. It cannot be
        seen at all while the tier is read off the frozen record."""
        frozens = [frozen("F1", "src/a/x.ts", 10, "widgetCache is never invalidated",
                          verdict="CORRECT_TRIVIAL", severity="minor")]
        replay = [replay_of(frozens[0], severity="critical")]
        buckets = score.grade(matcher.match(replay, frozens))
        head = score.headline_rates(buckets)
        self.assertEqual(head["review-pr-skill"]["graded"], 1)
        self.assertEqual(head["review-pr-skill"]["false"], 0)

    def test_a_skill_finding_matching_a_coderabbit_record_counts_as_the_skill(self):
        frozens = [frozen("F1", "src/a/x.ts", 10, "widgetCache is never invalidated",
                          verdict="FALSE_POSITIVE", source="coderabbit",
                          severity="major")]
        replay = [replay_of(frozens[0], source="review-pr-skill",
                            severity="serious")]
        head = score.headline_rates(score.grade(matcher.match(replay, frozens)))
        self.assertNotIn("coderabbit", head)
        self.assertEqual(head["review-pr-skill"]["false"], 1)

    def test_reasserting_a_coderabbit_false_positive_fails_the_gate(self):
        """CodeRabbit's rate never gates, so misfiling a skill finding under it let a run
        reassert someone else's false positives and still exit 0."""
        frozens = [frozen("F1", "src/a/x.ts", 10, "widgetCache is never invalidated",
                          verdict="FALSE_POSITIVE", source="coderabbit",
                          severity="major")]
        replay = [replay_of(frozens[0], source="review-pr-skill",
                            severity="serious")]
        result = matcher.match(replay, frozens)
        status, _ = score.gate(TestExitGate.Args(), result, replay,
                               score.headline_rates(score.grade(result)))
        self.assertEqual(status, score.EXIT_REGRESSION)

    def test_a_record_with_no_replay_side_keeps_frozen_attribution(self):
        record = frozen("F1", "src/a/x.ts", 10, "widgetCache is never invalidated",
                        source="coderabbit", severity="major")
        self.assertEqual(score._bucket_key(record, None),
                         ("synthetic", "coderabbit", "high"))


class TestTierDrift(unittest.TestCase):
    def setUp(self):
        self.frozens = [
            frozen("F1", "src/a/x.ts", 10, "widgetCache is never invalidated after write",
                   verdict="CORRECT_TRIVIAL", severity="minor"),
            frozen("F2", "src/b/y.ts", 20, "saveWidget skips validateOwner entirely",
                   verdict="FALSE_POSITIVE", severity="critical"),
            frozen("F3", "src/c/z.ts", 30, "parseWidget swallows a malformed payload"),
        ]

    def _drift(self, replay):
        return score.tier_drift(matcher.match(replay, self.frozens))

    def test_each_direction_is_counted(self):
        replay = [replay_of(self.frozens[0], severity="critical"),
                  replay_of(self.frozens[1], severity="minor"),
                  replay_of(self.frozens[2])]
        drift = self._drift(replay)
        self.assertEqual(drift["escalated"], 1)
        self.assertEqual(drift["de_escalated"], 1)
        self.assertEqual(drift["unchanged"], 1)

    def test_drift_names_the_verdict_it_moved(self):
        """Escalating a trivially-true claim and de-escalating a false positive are
        opposite outcomes; a bare count of moves cannot tell them apart."""
        replay = [replay_of(self.frozens[0], severity="critical"),
                  replay_of(self.frozens[1], severity="minor")]
        drift = self._drift(replay)
        self.assertEqual(drift["by_verdict"]["escalated"], {"CORRECT_TRIVIAL": 1})
        self.assertEqual(drift["by_verdict"]["de_escalated"], {"FALSE_POSITIVE": 1})

    def test_a_cross_source_pair_is_counted_separately(self):
        frozens = [frozen("F1", "src/a/x.ts", 10, "widgetCache is never invalidated",
                          source="coderabbit", severity="major")]
        drift = score.tier_drift(matcher.match(
            [replay_of(frozens[0], source="review-pr-skill", severity="serious")],
            frozens))
        self.assertEqual(drift["cross_source"], 1)
        self.assertEqual(drift["unchanged"], 1)

    def test_drift_alone_never_changes_the_exit_code(self):
        replay = [replay_of(self.frozens[0], severity="critical"),
                  replay_of(self.frozens[2])]
        result = matcher.match(replay, self.frozens)
        status, _ = score.gate(TestExitGate.Args(), result, replay,
                               score.headline_rates(score.grade(result)))
        self.assertEqual(score.tier_drift(result)["escalated"], 1)
        self.assertEqual(status, score.EXIT_OK)


class TestHoldout(unittest.TestCase):
    def setUp(self):
        self.defects = [{"id": f"d{i:03d}"} for i in range(100)]

    def test_split_is_deterministic_and_sized(self):
        a, meta_a = score.holdout_split(self.defects, seed=1)
        b, meta_b = score.holdout_split(self.defects, seed=1)
        self.assertEqual(a, b)
        self.assertEqual(meta_a["holdout_digest"], meta_b["holdout_digest"])
        self.assertEqual(len(a), 20)

    def test_split_is_order_independent(self):
        a, _ = score.holdout_split(self.defects, seed=1)
        b, _ = score.holdout_split(list(reversed(self.defects)), seed=1)
        self.assertEqual(a, b)

    def test_different_seed_draws_a_different_set(self):
        a, _ = score.holdout_split(self.defects, seed=1)
        b, _ = score.holdout_split(self.defects, seed=2)
        self.assertNotEqual(a, b)


class TestAnchorParsing(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(bench._parse_free_anchor("src/a/x.ts:12-40"),
                         ("src/a/x.ts", 12, 40, "exact"))

    def test_two_paths_flag_multi(self):
        p, start, _, q = bench._parse_free_anchor("src/a/x.ts:12 and src/b/y.ts:99")
        self.assertEqual((p, start, q), ("src/a/x.ts", 12, "multi"))

    def test_glob_yields_no_path_but_says_why(self):
        self.assertEqual(bench._parse_free_anchor("src/**/*.tsx (all views)"),
                         (None, None, None, "glob"))

    def test_brace_expansion_is_a_glob_not_a_blank(self):
        self.assertEqual(bench._parse_free_anchor("src/{a,b,c}.ts")[3], "glob")

    def test_empty(self):
        self.assertEqual(bench._parse_free_anchor(None)[3], "none")


class TestTranscriptParsing(unittest.TestCase):
    TRANSCRIPT = """Here is what I found.

Severity:    Serious
Confidence:  high
File:        src/alpha/parser.ts:118
Category:    Silent-failure
Rule-class:  swallowed-error
Issue:       parseWidget returns an empty list on a malformed payload.
Why it matters: callers read the empty list as "no widgets".

Severity:    Minor
File:        src/beta/store.ts
Category:    Architecture
Issue:       storeWidget reaches across the module boundary.

Some closing prose: not a finding.
"""

    def test_blocks_become_findings(self):
        findings, dropped = runner.parse_findings(self.TRANSCRIPT, 7)
        self.assertEqual(dropped, {"blocks": 0, "orphan_fields": 0})
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]["path"], "src/alpha/parser.ts")
        self.assertEqual(findings[0]["line"], 118)
        self.assertEqual(findings[0]["rule_class"], "swallowed-error")
        self.assertIsNone(findings[1]["line"])

    def test_incomplete_block_is_dropped_and_counted(self):
        findings, dropped = runner.parse_findings("Severity: Serious\nCategory: DRY\n", 7)
        self.assertEqual(findings, [])
        self.assertEqual(dropped["blocks"], 1)

    def test_parsed_findings_are_scoreable(self):
        findings, _ = runner.parse_findings(self.TRANSCRIPT, 7)
        tmp = pathlib.Path(__file__).with_name("_test_findings.json")
        tmp.write_text(__import__("json").dumps(findings))
        try:
            loaded = score.load_findings(tmp)
        finally:
            tmp.unlink()
        self.assertEqual(loaded[0]["path"], "src/alpha/parser.ts")
        self.assertEqual(loaded[0]["tier"], "high")
        self.assertEqual(loaded[1]["tier"], "low")


class TestRecall(unittest.TestCase):
    DEFECTS = [
        {"id": "d1", "diff_visible": "yes", "defect_class": "swallowed-error",
         "paths": ["src/alpha/parser.ts"],
         "text": "parseWidget swallowed a malformed payload and returned an empty list, "
                 "so downstream callers reported zero widgets instead of failing"},
        {"id": "d2", "diff_visible": "no", "defect_class": "race",
         "paths": ["src/beta/store.ts"], "text": "two writers raced on the same row"},
    ]

    def test_only_diff_visible_defects_are_eligible(self):
        out = score.score_recall([], self.DEFECTS, reserved=set(), permutations=1)
        self.assertEqual(out["eligible"], 1)

    def test_a_naming_finding_counts(self):
        finding = {"id": "R1", "path": "src/alpha/parser.ts",
                   "claim": "parseWidget swallowed a malformed payload, returning an "
                            "empty list to callers"}
        out = score.score_recall([finding], self.DEFECTS, reserved=set(), permutations=1)
        self.assertEqual(out["named"], 1)
        self.assertEqual(out["named_gated"], 1)

    def test_wrong_file_does_not_count(self):
        finding = {"id": "R1", "path": "src/gamma/other.ts",
                   "claim": "parseWidget swallowed a malformed payload, returning an "
                            "empty list to callers"}
        out = score.score_recall([finding], self.DEFECTS, reserved=set(), permutations=1)
        self.assertEqual(out["named"], 0)

    def test_holdout_defects_leave_the_denominator(self):
        out = score.score_recall([], self.DEFECTS, reserved={"d1"}, permutations=1)
        self.assertEqual(out["eligible"], 0)

    def test_a_pathless_finding_is_not_labelled_file_gated(self):
        """The gate only runs when the finding carries a path to test."""
        finding = {"id": "R1", "path": None,
                   "claim": "parseWidget swallowed a malformed payload, returning an "
                            "empty list to callers"}
        out = score.score_recall([finding], self.DEFECTS, reserved=set(), permutations=1)
        self.assertEqual(out["named"], 1)
        self.assertEqual(out["named_gated"], 0)
        self.assertEqual(out["named_ungated"], 1)
        self.assertFalse(out["hits"][0]["gated"])


class TestPermutationNull(unittest.TestCase):
    """The null is the harness's central statistical claim, so its dead regimes have to
    announce themselves instead of printing a lift of 1.0 as though it were measured."""

    DEFECT = {"id": "d1", "diff_visible": "yes", "defect_class": "swallowed-error",
              "text": "parseWidget swallowed a malformed payload and returned an empty "
                      "list, so callers reported zero widgets instead of failing"}

    def test_null_is_dead_when_no_defect_carries_a_path(self):
        defects = [dict(self.DEFECT, paths=[])]
        findings = [{"id": "R1", "path": None, "claim": self.DEFECT["text"]},
                    {"id": "R2", "path": None, "claim": "an unrelated naming nit"}]
        out = score.score_recall(findings, defects, reserved=set(), permutations=20)
        self.assertEqual(out["null_dead_defects"], 1)
        self.assertEqual(out["null_live_defects"], 0)
        self.assertEqual(out["null_status"], "degenerate")
        self.assertIsNone(out["lift"])
        self.assertIsNone(out["p_value"])

    def test_null_is_dead_when_no_finding_carries_a_path(self):
        defects = [dict(self.DEFECT, paths=["src/alpha/parser.ts"])]
        findings = [{"id": "R1", "path": None, "claim": self.DEFECT["text"]},
                    {"id": "R2", "path": None, "claim": "an unrelated naming nit"}]
        out = score.score_recall(findings, defects, reserved=set(), permutations=20)
        self.assertEqual(out["null_status"], "degenerate")

    def test_null_is_dead_when_every_finding_shares_one_basename(self):
        defects = [dict(self.DEFECT, paths=["src/alpha/parser.ts"])]
        findings = [{"id": "R1", "path": "src/alpha/parser.ts",
                     "claim": self.DEFECT["text"]},
                    {"id": "R2", "path": "other/parser.ts", "claim": "a naming nit"}]
        out = score.score_recall(findings, defects, reserved=set(), permutations=20)
        self.assertEqual(out["null_status"], "degenerate")

    def test_null_is_live_when_the_file_gate_excludes_someone(self):
        defects = [dict(self.DEFECT, paths=["src/alpha/parser.ts"])]
        findings = [{"id": "R1", "path": "src/alpha/parser.ts",
                     "claim": self.DEFECT["text"]},
                    {"id": "R2", "path": "src/beta/store.ts",
                     "claim": "a different claim about unrelated storage behaviour"}]
        out = score.score_recall(findings, defects, reserved=set(), permutations=20)
        self.assertEqual(out["null_live_defects"], 1)
        self.assertEqual(out["null_dead_defects"], 0)
        self.assertEqual(out["named"], 1)
        self.assertNotEqual(out["null_status"], "degenerate")
        self.assertIsNotNone(out["p_value"])

    def test_p_value_resolution_follows_the_permutation_count(self):
        """The estimator bottoms out at 1/(n+1), so the permutation count IS the best
        p-value the harness can report."""
        defects = [dict(self.DEFECT, paths=["src/alpha/parser.ts"])]
        findings = [{"id": "R1", "path": "src/alpha/parser.ts",
                     "claim": self.DEFECT["text"]},
                    {"id": "R2", "path": "src/beta/store.ts",
                     "claim": "a different claim about unrelated storage behaviour"}]
        out = score.score_recall(findings, defects, reserved=set(), permutations=200)
        self.assertEqual(out["permutations"], 200)
        self.assertGreaterEqual(out["p_value"], 1 / 201)
        self.assertLess(1 / (score.PERMUTATIONS + 1), 0.05)

    def test_the_strongest_outcome_is_not_reported_as_a_missing_number(self):
        """null_mean of 0 is the best result the harness can produce and the one a bare
        `named / null_mean` renders as `None`."""
        recall = {"null_mean": 0.0, "nulls": [0] * 20, "permutations": 20,
                  "null_live_defects": 1, "null_dead_defects": 0,
                  "null_status": "null_never_fired", "lift": None,
                  "p_value": 1 / 21, "threshold": score.RECALL_THRESHOLD}
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            score._report_null(recall)
        self.assertIn("UNBOUNDED", buffer.getvalue())
        self.assertNotIn("None", buffer.getvalue())

    def test_naming_nothing_against_a_zero_null_is_not_an_unbounded_lift(self):
        """0 named against a 0 null is the weakest outcome and shares its arithmetic with
        the strongest one."""
        defects = [dict(self.DEFECT, paths=["src/alpha/parser.ts"])]
        findings = [{"id": "R1", "path": "src/alpha/parser.ts",
                     "claim": "an entirely unrelated claim about button colours"},
                    {"id": "R2", "path": "src/beta/store.ts",
                     "claim": "another unrelated claim about spacing tokens"}]
        out = score.score_recall(findings, defects, reserved=set(), permutations=20)
        self.assertEqual(out["named"], 0)
        self.assertEqual(out["null_mean"], 0.0)
        self.assertEqual(out["null_status"], "nothing_named")
        self.assertIsNone(out["lift"])
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            score._report_null(out)
        self.assertIn("weakest", buffer.getvalue())
        self.assertNotIn("UNBOUNDED", buffer.getvalue())

    def test_a_degenerate_null_prints_no_lift_at_all(self):
        recall = {"null_mean": 2.0, "nulls": [2] * 20, "permutations": 20,
                  "null_live_defects": 0, "null_dead_defects": 4,
                  "null_status": "degenerate", "lift": None, "p_value": None,
                  "threshold": score.RECALL_THRESHOLD}
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            score._report_null(recall)
        self.assertIn("NO LIFT REPORTED", buffer.getvalue())
        self.assertNotIn("lift x", buffer.getvalue())


class TestContentFreeFindings(unittest.TestCase):
    FROZEN = frozen("F1", "src/alpha/parser.ts", 100,
                    "parseWidget swallows a malformed payload and returns an empty list")

    def test_a_claimless_finding_cannot_reach_accept_on_path_and_line(self):
        junk = {"id": "JUNK", "pr": 7, "path": "src/alpha/parser.ts", "line_start": 100,
                "claim": ""}
        s, parts = matcher.score_pair(junk, self.FROZEN)
        self.assertIsNone(parts["claim"])
        self.assertLess(s, matcher.ACCEPT)

    def test_a_claimless_finding_does_not_evict_the_real_one(self):
        junk = {"id": "JUNK", "pr": 7, "path": "src/alpha/parser.ts", "line_start": 100,
                "claim": ""}
        real = {"id": "REAL", "pr": 7, "path": "src/alpha/parser.ts", "line_start": 100,
                "claim": "malformed payload swallowed by parseWidget, empty list "
                         "returned to callers"}
        result = matcher.match([junk, real], [self.FROZEN])
        self.assertEqual([m["replay"]["id"] for m in result["matched"]], ["REAL"])
        self.assertNotIn("JUNK", [m["replay"]["id"] for m in result["matched"]])

    def test_the_run_parser_really_can_emit_a_claimless_finding(self):
        """The eviction path is reachable through the documented pipeline, not just
        through a hand-built dict."""
        kept, _ = runner.parse_findings(
            "Severity: Serious\nFile: src/alpha/parser.ts:100\nCategory: Silent\n", 7)
        self.assertEqual(len(kept), 1)
        self.assertNotIn("claim", kept[0])

    def test_a_missing_line_still_does_not_penalise(self):
        without = matcher.score_pair(dict(self.FROZEN, line_start=None), self.FROZEN)[0]
        self.assertAlmostEqual(without, 1.0, places=6)


class TestRecallEvidenceFloor(unittest.TestCase):
    LONG = ("resolveTenantScope is called after the write, so a foreign tenant row is "
            "persisted before the ownership check runs and the audit log records the "
            "wrong account for every affected request in the batch")

    def test_a_single_generic_word_cannot_reach_the_threshold(self):
        self.assertLess(matcher.recall_score("persisted", self.LONG),
                        score.RECALL_THRESHOLD)

    def test_containment_is_measured_against_the_claim_not_the_shorter_side(self):
        claim = "alpha beta gamma delta epsilon zeta"
        self.assertAlmostEqual(
            matcher._containment(matcher._words(claim), matcher._words("alpha beta")),
            2 / 6, places=6)

    def test_a_full_claim_naming_the_defect_still_scores(self):
        claim = "resolveTenantScope runs after the write so a foreign tenant row persists"
        self.assertGreater(matcher.recall_score(claim, self.LONG),
                           score.RECALL_THRESHOLD)


class TestAnchorQualityIsUsed(unittest.TestCase):
    def test_a_multi_site_anchor_scores_below_an_exact_one(self):
        f = frozen("F1", "src/a/x.ts", 10, "widgetCache never invalidates on write")
        exact = dict(f, id="R1", anchor_quality="exact")
        multi = dict(f, id="R2", anchor_quality="multi")
        self.assertLess(matcher.score_pair(multi, f)[0],
                        matcher.score_pair(exact, f)[0])

    def test_a_glob_anchor_is_weaker_than_a_multi_site_one(self):
        f = frozen("F1", "src/a/x.ts", 10, "widgetCache never invalidates on write")
        multi = matcher.score_pair(dict(f, anchor_quality="multi"), f)[0]
        glob = matcher.score_pair(dict(f, anchor_quality="glob"), f)[0]
        self.assertLess(glob, multi)


class TestFieldAliases(unittest.TestCase):
    def test_an_unrelated_number_field_is_not_read_as_a_pr(self):
        """`number` is the commonest field name there is, and the PR check hard-rejects,
        so accepting it silently rejects every record the row is compared against."""
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "f.json"
            p.write_text(json.dumps([{"file": "src/a.ts", "issue": "a real claim",
                                      "severity": "serious", "number": 4321}]))
            loaded = score.load_findings(p)
        self.assertIsNone(loaded[0]["pr"])


class TestHoldoutIsAuditable(unittest.TestCase):
    def test_an_empty_holdout_says_so_rather_than_printing_a_digest(self):
        reserved, meta = score.holdout_split([])
        self.assertEqual(reserved, set())
        self.assertEqual(meta["n_holdout"], 0)
        self.assertIn("EMPTY", meta["holdout_digest"])


class TestExitGate(unittest.TestCase):
    class Args:
        def __init__(self, gold=False, min_match_rate=score.MIN_MATCH_RATE):
            self.gold = gold
            self.min_match_rate = min_match_rate

    def _headline(self, graded, false):
        return {"review-pr-skill": {"graded": graded, "false": false,
                                    "fp_rate": (false / graded) if graded else None,
                                    "verdict": "NO-DATA" if not graded else
                                    ("PASS" if false / graded <= 0.05 else "FAIL")}}

    def test_a_clean_run_within_target_exits_zero(self):
        result = {"matched": [1] * 10}
        status, blockers = score.gate(self.Args(), result, [1] * 10,
                                      self._headline(10, 0))
        self.assertEqual(status, score.EXIT_OK)
        self.assertEqual(blockers, [])

    def test_a_rate_over_target_is_a_regression(self):
        result = {"matched": [1] * 10}
        status, blockers = score.gate(self.Args(), result, [1] * 10,
                                      self._headline(10, 5))
        self.assertEqual(status, score.EXIT_REGRESSION)

    def test_a_low_match_rate_cannot_certify(self):
        """Precision over a minority of findings describes the matcher."""
        result = {"matched": [1] * 3}
        status, blockers = score.gate(self.Args(), result, [1] * 10,
                                      self._headline(3, 0))
        self.assertEqual(status, score.EXIT_UNCERTIFIABLE)
        self.assertTrue(any("match rate" in b for b in blockers))

    def test_nothing_graded_is_not_green(self):
        result = {"matched": []}
        status, blockers = score.gate(self.Args(), result, [], {})
        self.assertEqual(status, score.EXIT_UNCERTIFIABLE)
        self.assertNotEqual(status, score.EXIT_OK)

    def test_gold_mode_cannot_gate_precision(self):
        result = {"matched": [1] * 10}
        status, blockers = score.gate(self.Args(gold=True), result, [1] * 10, {})
        self.assertEqual(status, score.EXIT_UNCERTIFIABLE)

    def test_a_regression_outranks_an_uncertifiable_run(self):
        result = {"matched": [1] * 3}
        status, _ = score.gate(self.Args(), result, [1] * 10, self._headline(3, 3))
        self.assertEqual(status, score.EXIT_REGRESSION)


def _write_benchmark(root, verdict_files, escaped=None, gold=None):
    """Build a throwaway benchmark directory in the shape the loaders expect."""
    (root / "verdicts").mkdir(parents=True, exist_ok=True)
    (root / "sessions").mkdir(parents=True, exist_ok=True)
    for name, rows in verdict_files.items():
        (root / "verdicts" / name).write_text(json.dumps(rows))
    (root / "sessions" / "sessions_synthetic.json").write_text(
        json.dumps(escaped if escaped is not None else []))
    if gold is not None:
        (root / "sessions" / "goldstandard_synthetic.json").write_text(json.dumps(gold))


VERDICT_ROWS = [
    {"pr": 7, "path": "src/alpha/parser.ts", "line": 100, "severity": "serious",
     "claim": "parseWidget swallows a malformed payload and returns an empty list",
     "verdict": "CORRECT"},
    {"pr": 7, "path": "src/beta/store.ts", "line": 40, "severity": "serious",
     "claim": "saveWidget writes before validateOwner runs so a foreign tenant wins",
     "verdict": "CORRECT"},
    {"pr": 8, "path": "src/gamma/cache.ts", "line": 12, "severity": "minor",
     "claim": "widgetCache never invalidates after a write", "verdict": "CORRECT"},
]

ESCAPED_ROWS = [
    {"defect_class": "swallowed-error", "would_a_diff_show_it": "yes",
     "file_hint": "src/alpha/parser.ts",
     "symptom": "callers saw zero widgets",
     "root_cause": "parseWidget swallowed a malformed payload and returned an empty "
                   "list instead of raising, so every caller read it as no widgets"},
    {"defect_class": "race", "would_a_diff_show_it": "no",
     "file_hint": "src/beta/store.ts", "symptom": "two writers raced on one row"},
]


class TestVerdictLoader(unittest.TestCase):
    def test_a_re_export_numbered_differently_is_still_detected(self):
        """The dedup key must not move with row position, or a consolidated export whose
        rows are ordered differently loads on top of the files it was built from."""
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"part.json": VERDICT_ROWS[1:],
                                    "all.json": list(reversed(VERDICT_ROWS))})
            records, notes = bench.load_verdicts(root)
        self.assertEqual(len(records), len(VERDICT_ROWS))
        self.assertTrue(any("subsumed" in n for n in notes))

    def test_two_byte_identical_exports_do_not_both_load(self):
        """Strict-subset subsumption cannot see equality: neither file is a proper subset
        of the other, so both load and every finding is counted twice."""
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"export_a.json": VERDICT_ROWS,
                                    "export_b.json": VERDICT_ROWS})
            records, notes = bench.load_verdicts(root)
        self.assertEqual(len(records), len(VERDICT_ROWS))
        self.assertTrue(any("subsumed" in n for n in notes))

    def test_a_partial_overlap_warns_because_no_file_subsumes_the_other(self):
        """Whole-file subsumption cannot remove a partial overlap, so the arithmetic is
        re-checked against what actually loaded and the inflation is stated."""
        extra = {"pr": 9, "path": "src/delta/api.ts", "line": 3, "severity": "serious",
                 "claim": "handleRequest never validates the tenant header",
                 "verdict": "CORRECT"}
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"left.json": VERDICT_ROWS,
                                    "right.json": VERDICT_ROWS[1:] + [extra]})
            records, notes = bench.load_verdicts(root)
        # 3 + 3 rows load because neither file covers the other, but only 4 findings are
        # distinct — the 2 in the intersection are counted twice.
        self.assertEqual(len(records), 6)
        warning = [n for n in notes if n.startswith("WARNING partition check failed")]
        self.assertEqual(len(warning), 1)
        self.assertIn("2 are duplicates", warning[0])

    def test_a_clean_partition_does_not_warn(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"left.json": VERDICT_ROWS[:2],
                                    "right.json": VERDICT_ROWS[2:]})
            records, notes = bench.load_verdicts(root)
        self.assertEqual(len(records), 3)
        self.assertFalse(any(n.startswith("WARNING") for n in notes))

    def test_duplicates_would_otherwise_be_invisible_downstream(self):
        """Ids are built from the corpus stem, so a duplicate gets a distinct id and
        surfaces as a benchmark finding the run 'failed to reproduce'."""
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"left.json": VERDICT_ROWS,
                                    "right.json": VERDICT_ROWS[1:]})
            records, _ = bench.load_verdicts(root)
        self.assertEqual(len({r["id"] for r in records}), len(records))


class TestEscapedAndGoldLoaders(unittest.TestCase):
    def test_escaped_defects_carry_visibility_paths_and_text(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"v.json": VERDICT_ROWS}, escaped=ESCAPED_ROWS)
            records, notes = bench.load_escaped(root)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["diff_visible"], "yes")
        self.assertEqual(records[0]["paths"], ["src/alpha/parser.ts"])
        self.assertIn("parseWidget", records[0]["text"])
        self.assertTrue(any("2 defects" in n for n in notes))

    def test_gold_findings_load_with_no_verdict_and_their_own_tier(self):
        gold = {"prs": [{"pr": 7, "findings": [
            {"title": "empty list on malformed payload",
             "mechanism": "parseWidget swallows the error and returns an empty list",
             "severity": "critical", "locations": ["src/alpha/parser.ts:100",
                                                   "src/alpha/other.ts:8"]}]}]}
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"v.json": VERDICT_ROWS}, gold=gold)
            records, _ = bench.load_gold(root)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source"], "gold")
        self.assertEqual(records[0]["tier"], "high")
        self.assertIsNone(records[0]["verdict"])
        self.assertEqual(records[0]["anchor_quality"], "multi")
        self.assertIn("parseWidget", records[0]["claim"])


class TestReportAndMain(unittest.TestCase):
    """report() and main() were the two functions the suite never executed, which is
    where a formatting crash could take the JSON artifact and the exit code with it."""

    def _run_main(self, argv):
        buffer = io.StringIO()
        original = sys.argv
        sys.argv = ["score.py"] + argv
        try:
            with contextlib.redirect_stdout(buffer):
                status = score.main()
        finally:
            sys.argv = original
        return status, buffer.getvalue()

    def test_self_check_runs_end_to_end_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"v.json": VERDICT_ROWS}, escaped=ESCAPED_ROWS)
            out = root / "results.json"
            status, text = self._run_main(
                ["--benchmark", str(root), "--self-check", "--json", str(out),
                 "--permutations", "5"])
            payload = json.loads(out.read_text())
        self.assertEqual(status, score.EXIT_OK)
        self.assertIn("MATCH RATE", text)
        self.assertIn("HEADLINE", text)
        self.assertIn("RECALL", text)
        self.assertEqual(payload["exit"]["status"], score.EXIT_OK)

    def test_gold_mode_reports_instead_of_raising_on_ungraded_buckets(self):
        """Gold records carry no verdict, so every high-tier bucket grades zero and the
        headline rate is None — which used to be formatted as a percentage and raise."""
        gold = {"prs": [{"pr": 7, "findings": [
            {"title": "empty list on malformed payload",
             "mechanism": "parseWidget swallows the error and returns an empty list",
             "severity": "critical", "locations": ["src/alpha/parser.ts:100"]}]}]}
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"v.json": VERDICT_ROWS}, escaped=ESCAPED_ROWS,
                             gold=gold)
            out = root / "results.json"
            status, text = self._run_main(
                ["--benchmark", str(root), "--gold", "--self-check", "--json", str(out),
                 "--permutations", "5"])
            payload = json.loads(out.read_text())
        self.assertEqual(status, score.EXIT_UNCERTIFIABLE)
        self.assertIn("NO-DATA", text)
        self.assertIn("RECALL", text)
        self.assertEqual(payload["headline"]["gold"]["graded"], 0)

    def test_the_json_artifact_survives_a_report_that_cannot_be_formatted(self):
        """CI reads the JSON; it must not be hostage to the human-readable printer."""
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"v.json": VERDICT_ROWS}, escaped=ESCAPED_ROWS)
            out = root / "results.json"
            original = score.report

            def exploding_report(*args, **kwargs):
                raise RuntimeError("formatting blew up")

            score.report = exploding_report
            try:
                with self.assertRaises(RuntimeError):
                    self._run_main(["--benchmark", str(root), "--self-check",
                                    "--json", str(out), "--permutations", "5"])
            finally:
                score.report = original
            self.assertTrue(out.exists())
            self.assertIn("headline", json.loads(out.read_text()))

    def test_a_regressing_run_exits_one_and_a_crashed_one_never_does(self):
        rows = [dict(r, verdict="FALSE_POSITIVE") for r in VERDICT_ROWS]
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"v.json": rows}, escaped=ESCAPED_ROWS)
            status, text = self._run_main(
                ["--benchmark", str(root), "--self-check", "--permutations", "5"])
        self.assertEqual(status, score.EXIT_REGRESSION)
        self.assertIn("REGRESSION", text)

    def test_show_holdout_prints_the_reserved_ids_and_stops(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"v.json": VERDICT_ROWS}, escaped=ESCAPED_ROWS)
            status, text = self._run_main(["--benchmark", str(root), "--show-holdout"])
        self.assertEqual(status, 0)
        self.assertIn("holdout_digest", text)
        self.assertNotIn("MATCH RATE", text)


class TestStream(unittest.TestCase):
    def test_a_child_that_stops_printing_is_still_killed_at_the_deadline(self):
        """The deadline used to be checked only when a line arrived, so a child that
        hung without printing was never timed out at all."""
        cmd = [sys.executable, "-c",
               "import time,sys; sys.stdout.write('x\\n'); sys.stdout.flush(); "
               "time.sleep(30)"]
        _, run = runner.stream(cmd, cwd=".", timeout=1)
        self.assertEqual(run["error"], "timeout")
        self.assertLess(run["seconds"], 15)

    def test_a_silent_child_is_killed_at_the_deadline(self):
        cmd = [sys.executable, "-c", "import time; time.sleep(30)"]
        _, run = runner.stream(cmd, cwd=".", timeout=1)
        self.assertEqual(run["error"], "timeout")
        self.assertLess(run["seconds"], 15)

    def test_stderr_reaches_the_caller_instead_of_being_discarded(self):
        cmd = [sys.executable, "-c",
               "import sys; sys.stderr.write('fatal auth error\\n'); sys.exit(3)"]
        _, run = runner.stream(cmd, cwd=".", timeout=10)
        self.assertIn("fatal auth error", run["error"])
        self.assertIn("exit 3", run["error"])

    def test_a_clean_run_reports_no_error(self):
        event = json.dumps({"type": "result", "total_cost_usd": 1.5,
                            "result": "Severity: Serious"})
        cmd = [sys.executable, "-c", f"print({event!r})"]
        text, run = runner.stream(cmd, cwd=".", timeout=10)
        self.assertIsNone(run["error"])
        self.assertEqual(run["cost_usd"], 1.5)
        self.assertEqual(run["denials"], [])
        self.assertIn("Severity: Serious", text)

    def test_refused_tool_calls_are_carried_out_of_the_transcript(self):
        """The CLI reports them once, in the result event. Left there they are invisible,
        and a run that was never allowed to read the PR looks like a clean review."""
        event = json.dumps({"type": "result", "total_cost_usd": 0.1, "result": "",
                            "permission_denials": [
                                {"tool_name": "Bash",
                                 "tool_input": {"command": "gh pr diff https://x/pull/1"}}]})
        cmd = [sys.executable, "-c", f"print({event!r})"]
        _, run = runner.stream(cmd, cwd=".", timeout=10)
        self.assertEqual(len(run["denials"]), 1)
        self.assertEqual(run["denials"][0]["tool_name"], "Bash")

    def test_denials_from_every_result_event_are_kept(self):
        """A subagent's refusals arrive in its own result event; the parent's final one
        lists none. The skill reviews inside subagents, so reading only the last event
        would miss nearly every refusal there is."""
        subagent = json.dumps({"type": "result", "result": "", "permission_denials": [
            {"tool_name": "Bash", "tool_input": {"command": "gh pr comment 7 --body x"}}]})
        parent = json.dumps({"type": "result", "result": "Severity: Serious",
                             "permission_denials": []})
        cmd = [sys.executable, "-c", f"print({subagent!r}); print({parent!r})"]
        _, run = runner.stream(cmd, cwd=".", timeout=10)
        self.assertEqual(len(run["denials"]), 1)


class TestPerturbation(unittest.TestCase):
    """The perturbation table is a published claim about the matcher, so the thing that
    produces it is tested like the matcher is."""

    def setUp(self):
        self.frozens = [
            frozen("F1", "src/alpha/parser.ts", 100,
                   "parseWidget swallows a malformed payload and returns an empty list"),
            frozen("F2", "src/beta/store.ts", 40,
                   "saveWidget writes before validateOwner runs so a foreign tenant wins",
                   verdict="FALSE_POSITIVE"),
            frozen("F3", "src/gamma/cache.ts", 12,
                   "widgetCache never invalidates after a write completes"),
        ]

    def test_zero_drift_places_every_copy_on_its_own_record(self):
        """The floor the table is read against: whatever mis-assignment the rows show is
        drift, not two records in the corpus the matcher could never tell apart."""
        row = perturb.run_scenario(self.frozens, jitter=0, drop=0.0, keep_path=True,
                                   seeds=2)
        self.assertEqual(row["match_rate"], 1.0)
        self.assertEqual(row["misassigned"], 0.0)
        self.assertEqual(row["misassigned_share"], 0.0)

    def test_more_drift_never_matches_better(self):
        light = perturb.run_scenario(self.frozens, 5, 0.20, True, seeds=3)
        heavy = perturb.run_scenario(self.frozens, 30, 0.80, True, seeds=3)
        self.assertLessEqual(heavy["match_rate"], light["match_rate"])

    def test_a_copy_carries_the_record_it_came_from(self):
        """Without `origin`, a pair landing on a neighbour in the same file is
        indistinguishable from a correct one and mis-assignment cannot be counted."""
        copy = perturb.perturb(self.frozens[0], random.Random(1), 15, 0.4, True)
        self.assertEqual(copy["origin"], "F1")
        self.assertNotEqual(copy["id"], "F1")
        self.assertLessEqual(abs(copy["line_start"] - 100), 15)

    def test_dropping_a_signal_removes_it_rather_than_falsifying_it(self):
        no_line = perturb.perturb(self.frozens[0], random.Random(1), None, 0.0, True)
        no_path = perturb.perturb(self.frozens[0], random.Random(1), 5, 0.0, False)
        self.assertIsNone(no_line["line_start"])
        self.assertIsNone(no_path["path"])

    def test_the_verdict_groups_the_bias_check_reads_are_counted(self):
        row = perturb.run_scenario(self.frozens, 5, 0.2, True, seeds=1)
        self.assertEqual(row["n_false"], 1)
        self.assertEqual(row["n_true"], 2)

    def test_the_table_and_the_bias_line_are_the_scripts_own_output(self):
        rows = VERDICT_ROWS + [
            {"pr": 8, "path": "src/delta/api.ts", "line": 5, "severity": "serious",
             "claim": "listWidgets returns rows from tenants it should filter out",
             "verdict": "FALSE_POSITIVE"}]
        buffer = io.StringIO()
        original = sys.argv
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"v.json": rows}, escaped=ESCAPED_ROWS)
            sys.argv = ["perturb.py", "--benchmark", str(root), "--seeds", "2",
                        "--bias-seeds", "2"]
            try:
                with contextlib.redirect_stdout(buffer):
                    status = perturb.main()
            finally:
                sys.argv = original
        text = buffer.getvalue()
        self.assertEqual(status, 0)
        self.assertIn("| perturbation | match | mis-assigned |", text)
        self.assertIn("FP records (n=1)", text)
        self.assertEqual(text.count("\n|"), len(perturb.SCENARIOS) + 2)

    def test_a_corpus_with_no_false_positives_says_so_instead_of_printing_zero(self):
        """Every row in this benchmark is CORRECT, so the bias check has one group. A
        0.0% FP match rate there would read as "the matcher loses every FP"."""
        buffer = io.StringIO()
        original = sys.argv
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_benchmark(root, {"v.json": VERDICT_ROWS}, escaped=ESCAPED_ROWS)
            sys.argv = ["perturb.py", "--benchmark", str(root), "--seeds", "1",
                        "--bias-seeds", "1"]
            try:
                with contextlib.redirect_stdout(buffer):
                    perturb.main()
            finally:
                sys.argv = original
        self.assertIn("NOT MEASURED", buffer.getvalue())


class TestPermissionPolicy(unittest.TestCase):
    """The invocation is the only thing standing between a measurement and a review that
    posts to somebody's PR, so it is asserted rather than read."""

    def test_the_command_grants_phase_ones_reads_and_never_prompts(self):
        cmd = runner.build_command("https://github.com/o/r/pull/7", 8.0, None)
        self.assertIn("--permission-mode", cmd)
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "dontAsk")
        self.assertIn("--allowedTools", cmd)
        self.assertIn("Bash(gh pr view:*)", cmd)
        self.assertIn("Bash(gh pr diff:*)", cmd)
        self.assertIn("Read", cmd)

    def test_the_subagent_dispatch_tool_is_granted_under_both_its_names(self):
        """The skill is built on subagents. The CLI has called that tool `Task` and now
        `Agent`; granting only one name denies every dispatch on the other build."""
        for name in ("Agent", "Task"):
            self.assertIn(name, runner.ALLOW)

    def test_the_posting_path_stays_denied(self):
        cmd = runner.build_command("https://github.com/o/r/pull/7", 8.0, "opus")
        self.assertIn("--disallowed-tools", cmd)
        for rule in ("Bash(gh pr review:*)", "Bash(gh pr comment:*)", "Bash(git push:*)"):
            self.assertIn(rule, cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "opus")

    def test_nothing_that_writes_is_granted(self):
        """A replay reads. A write rule reaching ALLOW would let the benchmark modify the
        checkout it is measuring, and a rule granted and denied at once is a policy whose
        effect depends on precedence nobody should have to remember."""
        for rule in ("Write", "Edit", "NotebookEdit"):
            self.assertIn(rule, runner.DENY)
            self.assertNotIn(rule, runner.ALLOW)
        for rule in runner.ALLOW:
            tool, _, prefix = rule.partition("(")
            prefix = prefix.rstrip(")").removesuffix(":*")
            self.assertFalse(
                any(runner._rule_covers(denied, tool, prefix) for denied in runner.DENY),
                f"{rule} is granted and denied at once")


class TestDenialClassification(unittest.TestCase):
    def test_a_denial_the_deny_list_explains_is_the_guard_working(self):
        blocked, refused = runner.classify_denials([
            {"tool_name": "Bash", "tool_input": {"command": "gh pr comment 7 --body x"}},
            {"tool_name": "Bash", "tool_input": {"command": "gh api graphql -f q=x"}},
        ])
        self.assertEqual(len(blocked), 2)
        self.assertEqual(refused, [])

    def test_a_tool_level_rule_matches_a_call_with_no_command(self):
        blocked, refused = runner.classify_denials([{"tool_name": "Write",
                                                     "tool_input": {"file_path": "a.md"}}])
        self.assertEqual(blocked, ["Write"])
        self.assertEqual(refused, [])

    def test_an_unanswerable_checkpoint_is_policy_not_misconfiguration(self):
        """The skill offers choices and there is no human. That is a known property of
        replaying it, not a machine that failed to grant something."""
        blocked, refused = runner.classify_denials([
            {"tool_name": "AskUserQuestion", "tool_input": {"questions": []}}])
        self.assertEqual(blocked, ["AskUserQuestion"])
        self.assertEqual(refused, [])

    def test_a_chained_or_piped_command_is_matched_per_segment(self):
        """The skill chains and pipes freely. Matching a prefix against the whole string
        files the guard stopping a post as a harness failure, and lets a denied read hide
        behind a leading `cd`."""
        blocked, refused = runner.classify_denials([
            {"tool_name": "Bash",
             "tool_input": {"command": "cd repo && gh pr comment 7 --body x"}},
            {"tool_name": "Bash",
             "tool_input": {"command": "cd repo && gh pr diff 7 | head -200"}},
        ])
        self.assertEqual(len(blocked), 1)
        self.assertEqual(len(refused), 1)
        self.assertIn("gh pr diff", refused[0])

    def test_a_denial_with_no_readable_input_still_names_something(self):
        blocked, refused = runner.classify_denials([{"tool_name": "", "tool_input": {}}])
        self.assertEqual(blocked, [])
        self.assertEqual(refused, ["unnamed tool call"])

    def test_an_empty_pattern_covers_nothing(self):
        """`Tool()` read as "matches everything" would file every refusal as expected and
        silence the exit code permanently."""
        self.assertFalse(runner._rule_covers("Bash()", "Bash", "gh pr view 7"))
        self.assertTrue(runner._rule_covers("Bash", "Bash", "gh pr view 7"))

    def test_a_denial_nothing_asked_for_is_a_refusal(self):
        """`gh pr view` refused is the environment failing the harness, not the harness
        stopping the skill — and it is the case that reads as an empty review."""
        blocked, refused = runner.classify_denials([
            {"tool_name": "Bash", "tool_input": {"command": "gh pr view https://x/pull/1"}}])
        self.assertEqual(blocked, [])
        self.assertEqual(len(refused), 1)
        self.assertIn("gh pr view", refused[0])


class TestRunExitCodes(unittest.TestCase):
    """A refused run and an empty one used to be the same exit code and the same output.
    They are the two things this harness most needs to tell apart."""

    TRANSCRIPT = ("Severity: Serious\nFile: src/alpha/parser.ts:10\n"
                  "Issue: parseWidget swallows a malformed payload\n")

    def _run_main(self, text, denials, error=None, dispatches=4, argv=()):
        buffer = io.StringIO()
        original_argv, original_stream = sys.argv, runner.stream
        telemetry = {"cost_usd": 0.5, "seconds": 1.0, "denials": denials,
                     "dispatches": dispatches, "error": error}
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "run.json"
            sys.argv = ["run.py", "--pr", "https://github.com/o/r/pull/7",
                        "--out", str(out), *argv]
            runner.stream = lambda *a, **k: (text, telemetry)
            try:
                with contextlib.redirect_stdout(buffer):
                    status = runner.main()
                # A pre-flight failure returns before the CLI is launched, so there is
                # no run to record and no file to read.
                payload = json.loads(out.read_text()) if out.exists() else None
            finally:
                sys.argv, runner.stream = original_argv, original_stream
        return status, payload, buffer.getvalue()

    def test_findings_and_no_denials_pass(self):
        status, payload, _ = self._run_main(self.TRANSCRIPT, [])
        self.assertEqual(status, runner.EXIT_OK)
        self.assertEqual(len(payload["findings"]), 1)
        self.assertEqual(payload["permissions"]["refused"], [])

    def test_a_refused_read_is_not_reported_as_an_empty_review(self):
        status, payload, text = self._run_main("", [
            {"tool_name": "Bash", "tool_input": {"command": "gh pr diff https://x/pull/7"}}])
        self.assertEqual(status, runner.EXIT_PERMISSION_REFUSED)
        self.assertIn("PERMISSION REFUSED", text)
        self.assertIn("gh pr diff", payload["permissions"]["refused"][0])

    def test_a_refusal_warns_but_does_not_throw_away_a_run_that_produced_findings(self):
        """A partially refused run is worth less than a clean one and far more than
        nothing; discarding its findings over one denied command is the wrong trade."""
        status, payload, text = self._run_main(self.TRANSCRIPT, [
            {"tool_name": "Bash", "tool_input": {"command": "bash -c 'find packages'"}}])
        self.assertEqual(status, runner.EXIT_OK)
        self.assertIn("PERMISSION REFUSED", text)
        self.assertEqual(len(payload["permissions"]["refused"]), 1)

    def test_a_genuinely_empty_review_keeps_its_own_code(self):
        status, _, text = self._run_main("no findings here", [])
        self.assertEqual(status, runner.EXIT_NO_FINDINGS)
        self.assertNotIn("PERMISSION REFUSED", text)

    def test_the_skill_being_stopped_from_posting_is_not_a_failure(self):
        status, payload, _ = self._run_main(self.TRANSCRIPT, [
            {"tool_name": "Bash", "tool_input": {"command": "gh pr review 7 --comment"}}])
        self.assertEqual(status, runner.EXIT_OK)
        self.assertEqual(len(payload["permissions"]["blocked_by_policy"]), 1)

    def test_a_dead_cli_outranks_everything_else(self):
        status, _, _ = self._run_main("", [], error="exit 1: not logged in")
        self.assertEqual(status, runner.EXIT_CLI_ERROR)

    def test_an_unreadable_review_gets_its_own_code_and_keeps_its_text(self):
        review = TestFormatFailure.MARKDOWN_REVIEW
        status, payload, text = self._run_main(review, [])
        self.assertEqual(status, runner.EXIT_FORMAT_FAILURE)
        self.assertIn("FORMAT FAILURE", text)
        self.assertTrue(payload["format"]["failure"])
        self.assertEqual(payload["findings"], [])
        self.assertIn("cache is never invalidated", payload["raw_review"]["text"])

    def test_an_unrelated_refusal_is_not_reported_as_the_cause_of_an_empty_run(self):
        """Both happened on the live run and neither caused the other. Exit 3 claimed the
        refused command was why nothing parsed; the format change was."""
        status, _, text = self._run_main(TestFormatFailure.MARKDOWN_REVIEW, [
            {"tool_name": "Bash",
             "tool_input": {"command": "for n in 1 2; do sed -n \"${n}p\" a.ts; done"}}])
        self.assertEqual(status, runner.EXIT_FORMAT_FAILURE)
        self.assertIn("PERMISSION REFUSED", text)
        self.assertIn("separate question", text)
        self.assertLess(text.index("PERMISSION REFUSED"), text.index("FORMAT FAILURE"))

    def test_a_clean_run_is_still_reported_as_clean_not_as_a_format_failure(self):
        status, payload, text = self._run_main(TestFormatFailure.CLEAN_REVIEW, [])
        self.assertEqual(status, runner.EXIT_NO_FINDINGS)
        self.assertNotIn("FORMAT FAILURE", text)
        self.assertFalse(payload["format"]["failure"])

    def test_a_single_pass_run_says_so_next_to_its_finding_count(self):
        status, payload, text = self._run_main(self.TRANSCRIPT, [], dispatches=0)
        self.assertEqual(status, runner.EXIT_OK)
        self.assertEqual(payload["subagent_dispatches"], 0)
        self.assertIn("subagents=0", text)
        self.assertIn("SINGLE-PASS", text)

    def test_a_multi_agent_run_records_its_dispatches_and_does_not_warn(self):
        _, payload, text = self._run_main(self.TRANSCRIPT, [], dispatches=4)
        self.assertEqual(payload["subagent_dispatches"], 4)
        self.assertNotIn("SINGLE-PASS", text)

    def test_the_run_states_which_skill_produced_it(self):
        _, payload, _ = self._run_main(self.TRANSCRIPT, [])
        self.assertIn("skill", payload)
        self.assertEqual(payload["skill"]["name"], "review-pr")

    def test_a_skill_mismatch_fails_before_the_budget_is_spent(self):
        """The CLI is never launched: the run as configured would measure a different
        artifact than the one named, and finding that out costs a full review."""
        with tempfile.TemporaryDirectory() as branch:
            status, payload, text = self._run_main(
                self.TRANSCRIPT, [], argv=("--skill-dir", branch))
        self.assertEqual(status, runner.EXIT_CLI_ERROR)
        self.assertIn("SKILL MISMATCH", text)
        self.assertIsNone(payload)


class TestFormatFailure(unittest.TestCase):
    """The counters that exist to make silent loss loud only catch output that *almost*
    parsed. A review emitted in a wholly different shape trips none of them: no findings,
    no unparsed blocks, no orphan fields — every number agreeing nothing was lost."""

    # A real review in a shape the field grammar cannot see: headings instead of
    # `Severity:` lines, and the field labels bolded so the `^\s*field\s*:` anchor misses.
    MARKDOWN_REVIEW = ("# Review of the widget cache\n\n"
                       "### Critical - the cache is never invalidated after a write\n\n"
                       "`src/alpha/cache.ts:42` - Rule-class `stale-read`\n\n"
                       "**Why it matters**: a second reader sees the pre-write value.\n"
                       "**Suggested fix**: drop the entry inside the same transaction.\n"
                       "**Inverse risk**: dropping it outside re-opens the window.\n\n"
                       "### Serious - parseWidget swallows a malformed payload\n\n"
                       "`src/alpha/parser.ts:118` - Rule-class `swallowed-error`\n\n"
                       "**Suggested fix**: raise instead of returning an empty list.\n"
                       "**Class-sites**: 2 of 3 parsers.\n") + "prose. " * 300

    CLEAN_REVIEW = ("# Review of the widget cache\n\nNothing blocking. "
                    "Verified clean: the invalidation runs inside the transaction, the "
                    "parser raises on a malformed payload, and the two callers agree on "
                    "units.\n") + "I checked each hunk against its caller. " * 100

    def test_a_review_the_parser_cannot_read_is_not_an_empty_pr(self):
        findings, dropped = runner.parse_findings(self.MARKDOWN_REVIEW, 7)
        self.assertEqual(findings, [])
        self.assertEqual(dropped, {"blocks": 0, "orphan_fields": 0})
        self.assertTrue(runner.diagnose_format(self.MARKDOWN_REVIEW, findings,
                                               dropped)["failure"])

    def test_a_clean_review_is_never_called_a_format_failure(self):
        """The false direction that matters: calling a real clean run a harness failure
        teaches the operator to disbelieve the signal."""
        findings, dropped = runner.parse_findings(self.CLEAN_REVIEW, 7)
        self.assertGreater(len(self.CLEAN_REVIEW), runner.MIN_REVIEW_CHARS)
        self.assertFalse(runner.diagnose_format(self.CLEAN_REVIEW, findings,
                                                dropped)["failure"])

    def test_one_recognised_field_line_means_the_grammar_survived(self):
        """A run that parsed something is an ordinary parse with drops, not a format
        change, however much unparsed vocabulary surrounds it."""
        text = self.MARKDOWN_REVIEW + "\nSeverity: Minor\nFile: src/beta/store.ts\n" \
                                      "Issue: storeWidget crosses the module boundary\n"
        findings, dropped = runner.parse_findings(text, 7)
        self.assertEqual(len(findings), 1)
        self.assertFalse(runner.diagnose_format(text, findings, dropped)["failure"])

    def test_an_orphan_field_alone_still_counts_as_the_grammar_surviving(self):
        text = self.MARKDOWN_REVIEW + "\nCategory: Correctness\n"
        findings, dropped = runner.parse_findings(text, 7)
        self.assertEqual(dropped["orphan_fields"], 1)
        self.assertFalse(runner.diagnose_format(text, findings, dropped)["failure"])

    def test_a_short_output_cannot_trip_the_gate(self):
        """Below a page of text there is no review to have lost, whatever words it used."""
        text = "**Suggested fix**: rename it.\n**Inverse risk**: none.\n"
        findings, dropped = runner.parse_findings(text, 7)
        self.assertLess(len(text), runner.MIN_REVIEW_CHARS)
        self.assertFalse(runner.diagnose_format(text, findings, dropped)["failure"])

    def test_one_stray_marker_in_long_prose_is_a_turn_of_phrase(self):
        text = self.CLEAN_REVIEW + "\nNo suggested fix is needed for any of it.\n"
        findings, dropped = runner.parse_findings(text, 7)
        self.assertEqual(runner.diagnose_format(text, findings, dropped)["markers"], 1)
        self.assertFalse(runner.diagnose_format(text, findings, dropped)["failure"])


class TestRawReviewSurvivesTheParser(unittest.TestCase):
    """An output nothing can parse is an output nobody can audit. The review has to
    outlive the grammar that failed to read it."""

    def test_the_review_text_is_persisted_verbatim(self):
        kept = runner.raw_review(TestFormatFailure.MARKDOWN_REVIEW)
        self.assertIn("cache is never invalidated", kept["text"])
        self.assertEqual(kept["chars"], len(TestFormatFailure.MARKDOWN_REVIEW))
        self.assertFalse(kept["truncated"])

    def test_an_oversized_review_is_clipped_and_says_how_long_it_really_was(self):
        text = "x" * (runner.RAW_REVIEW_LIMIT + 5000)
        kept = runner.raw_review(text)
        self.assertTrue(kept["truncated"])
        self.assertEqual(kept["chars"], len(text))
        self.assertEqual(len(kept["text"]), runner.RAW_REVIEW_LIMIT)

    def test_score_py_never_reads_the_raw_review_as_findings(self):
        """Prose scored against adjudicated verdicts would invent a measurement out of
        text nobody structured."""
        payload = {"findings": [], "raw_review": runner.raw_review(
            TestFormatFailure.MARKDOWN_REVIEW)}
        tmp = pathlib.Path(__file__).with_name("_test_raw_review.json")
        tmp.write_text(json.dumps(payload))
        try:
            self.assertEqual(score.load_findings(tmp), [])
        finally:
            tmp.unlink()


class TestResultEchoIsNotCountedTwice(unittest.TestCase):
    def test_the_final_result_event_does_not_duplicate_the_review(self):
        """The CLI's result event restates the last assistant message verbatim. Appended
        blind it doubles every finding parsed out of it, and the matcher can only report
        the copies as unmatched — a duplicate-driven drop in the measured match rate."""
        review = ("Severity: Serious\nFile: src/alpha/parser.ts:118\n"
                  "Issue: parseWidget swallows a malformed payload\n")
        assistant = json.dumps({"type": "assistant",
                                "message": {"content": [{"type": "text", "text": review}]}})
        result = json.dumps({"type": "result", "total_cost_usd": 1.0, "result": review})
        cmd = [sys.executable, "-c", f"print({assistant!r}); print({result!r})"]
        text, _ = runner.stream(cmd, cwd=".", timeout=10)
        findings, _ = runner.parse_findings(text, 7)
        self.assertEqual(len(findings), 1)

    def test_a_result_with_no_assistant_text_before_it_is_still_kept(self):
        result = json.dumps({"type": "result", "total_cost_usd": 1.0,
                             "result": "Severity: Serious\nFile: a.ts:1\nIssue: x\n"})
        cmd = [sys.executable, "-c", f"print({result!r})"]
        text, _ = runner.stream(cmd, cwd=".", timeout=10)
        self.assertEqual(len(runner.parse_findings(text, 7)[0]), 1)


class TestSubagentDispatchCount(unittest.TestCase):
    """Zero dispatches means the phases that live inside subagents never ran. The run
    that exposed this counted permission denials but never counted dispatches, so a
    single-pass review was indistinguishable in the JSON from a four-agent one."""

    def _stream_with(self, tool_names):
        content = [{"type": "text", "text": "working"}]
        content += [{"type": "tool_use", "name": n, "input": {}} for n in tool_names]
        event = json.dumps({"type": "assistant", "message": {"content": content}})
        cmd = [sys.executable, "-c", f"print({event!r})"]
        return runner.stream(cmd, cwd=".", timeout=10)[1]

    def test_dispatches_are_counted_under_both_tool_names(self):
        self.assertEqual(self._stream_with(["Agent", "Task", "Agent"])["dispatches"], 3)

    def test_other_tool_calls_are_not_counted_as_dispatches(self):
        self.assertEqual(self._stream_with(["Read", "Grep", "Bash"])["dispatches"], 0)

    def test_a_run_with_no_dispatches_reports_zero_rather_than_nothing(self):
        self.assertEqual(self._stream_with([])["dispatches"], 0)


class TestSkillProvenance(unittest.TestCase):
    """`--model` pins the model; the artifact actually under measurement was neither
    pinned nor recorded, so a scored run could not state which skill produced it."""

    def _skill(self, root, body="---\nname: review-pr\n---\nreview it\n"):
        d = pathlib.Path(root) / ".claude" / "skills" / "review-pr"
        (d / "references").mkdir(parents=True)
        (d / "SKILL.md").write_text(body)
        (d / "references" / "finding-output-format.md").write_text("Severity:\nFile:\n")
        return d

    def test_the_skill_the_cli_will_load_is_resolved_and_fingerprinted(self):
        with tempfile.TemporaryDirectory() as d:
            skill = self._skill(d)
            found = runner.resolve_skill(d, home=d)
            self.assertEqual(found["resolved"], str(skill.resolve()))
            self.assertEqual(len(found["fingerprint"]), 12)

    def test_editing_the_skill_moves_the_fingerprint(self):
        with tempfile.TemporaryDirectory() as d:
            skill = self._skill(d)
            before = runner.fingerprint_skill(skill)
            (skill / "SKILL.md").write_text("---\nname: review-pr\n---\nreview it well\n")
            self.assertNotEqual(runner.fingerprint_skill(skill), before)

    def test_renaming_a_reference_moves_the_fingerprint(self):
        """A hash over contents alone would call a renamed reference file the same skill."""
        with tempfile.TemporaryDirectory() as d:
            skill = self._skill(d)
            before = runner.fingerprint_skill(skill)
            reference = skill / "references" / "finding-output-format.md"
            reference.rename(reference.with_name("output-format.md"))
            self.assertNotEqual(runner.fingerprint_skill(skill), before)

    def test_a_directory_the_cli_will_load_is_recorded_as_pinned(self):
        with tempfile.TemporaryDirectory() as d:
            skill = self._skill(d)
            found = runner.resolve_skill(d, requested=str(skill), home=d)
            self.assertTrue(found["pinned"])
            self.assertEqual(found["requested"], str(skill.resolve()))

    def test_asking_for_a_directory_the_cli_will_not_load_is_not_pinned(self):
        """The failure the operator hit: the run measured the published skill while the
        branch under test sat in a directory the CLI never looked at."""
        with tempfile.TemporaryDirectory() as installed, \
                tempfile.TemporaryDirectory() as branch:
            self._skill(installed)
            found = runner.resolve_skill(installed, requested=branch, home=installed)
            self.assertFalse(found["pinned"])
            self.assertNotEqual(found["resolved"], found["requested"])

    def test_an_unresolvable_skill_says_so_instead_of_guessing(self):
        with tempfile.TemporaryDirectory() as d:
            found = runner.resolve_skill(d, home=d)
            self.assertIsNone(found["resolved"])
            self.assertIsNone(found["fingerprint"])


class TestOrphanFields(unittest.TestCase):
    def test_fields_arriving_before_any_severity_are_counted_not_swallowed(self):
        transcript = ("File: src/orphan.ts:10\n"
                      "Issue: this block lost its severity line\n"
                      "Severity: Serious\n"
                      "File: src/real.ts:20\n"
                      "Issue: a genuine finding\n")
        kept, dropped = runner.parse_findings(transcript, 7)
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped["orphan_fields"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
