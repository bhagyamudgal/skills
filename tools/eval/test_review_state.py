import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "skills" / "review-pr" / "scripts" / "review_state.py"
SPEC = importlib.util.spec_from_file_location("review_state", SCRIPT)
review_state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review_state)

REPO = "acme/shop"
PR = 8094
HAS_RUBY = shutil.which("ruby") is not None


def finding(**overrides):
    return {"id": "9c4f2a8b1e", "file": "src/upsert.ts", "enclosing_symbol": "upsertBundle",
            "rule_class": "silent-failure", "status": "active", **overrides}


def state(**overrides):
    return {"pr": PR, "repo": REPO, "created_at": "2026-11-12T22:15:00Z", "updated_at": "2026-11-18T09:57:00Z",
            "last_round": 13, "findings": [finding()], **overrides}


def gh_reviews(*bodies, returncode=0, stderr=""):
    stdout = json.dumps({"reviews": [{"body": body} for body in bodies]})
    return subprocess.CompletedProcess(["gh"], returncode, stdout=stdout, stderr=stderr)


class StateFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name) / "review-state" / f"{PR}.json"

    def store(self, content):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(content), encoding="utf-8")


class HighestPostedRoundTest(unittest.TestCase):
    def test_takes_the_highest_marker_across_every_review(self):
        reviews = gh_reviews("<!-- review-pr:run sha=abc round=13 -->", "<!-- review-pr:run sha=def round=1 -->", None, "LGTM")
        with mock.patch.object(review_state.subprocess, "run", return_value=reviews):
            self.assertEqual(review_state.highest_posted_round(REPO, PR), 13)

    def test_no_marker_reads_as_round_zero(self):
        with mock.patch.object(review_state.subprocess, "run", return_value=gh_reviews("LGTM")):
            self.assertEqual(review_state.highest_posted_round(REPO, PR), 0)

    def test_missing_gh_raises_instead_of_a_traceback(self):
        with mock.patch.object(review_state.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(review_state.StateError, "gh is not installed"):
                review_state.highest_posted_round(REPO, PR)

    def test_unreadable_gh_output_raises(self):
        for stdout in ["not json", "{}", '{"reviews": null}']:
            with self.subTest(stdout=stdout):
                with mock.patch.object(review_state.subprocess, "run", return_value=subprocess.CompletedProcess(["gh"], 0, stdout=stdout, stderr="")):
                    with self.assertRaisesRegex(review_state.StateError, "returned unreadable reviews"):
                        review_state.highest_posted_round(REPO, PR)

    def test_failed_gh_call_raises_instead_of_reading_zero(self):
        with mock.patch.object(review_state.subprocess, "run", return_value=gh_reviews(returncode=1, stderr="HTTP 502")):
            with self.assertRaisesRegex(review_state.StateError, "HTTP 502"):
                review_state.highest_posted_round(REPO, PR)

    def test_marker_format_round_trips(self):
        marker = review_state.run_marker("a" * 40, 14)
        self.assertEqual(review_state.RUN_MARKER_ROUND.findall(marker), ["14"])


class CurrentRoundTest(StateFileTest):
    def current_round(self, posted):
        with mock.patch.object(review_state, "highest_posted_round", return_value=posted):
            return review_state.current_round(self.path, REPO, PR)

    def test_github_round_wins_over_a_stale_state_file(self):
        self.store(state(last_round=1))
        self.assertEqual(self.current_round(13), 14)

    def test_state_round_wins_when_github_lags(self):
        self.store(state(last_round=5))
        self.assertEqual(self.current_round(3), 6)

    def test_first_review_is_round_one(self):
        self.assertEqual(self.current_round(0), 1)


class ReadTest(StateFileTest):
    def test_missing_file_reads_as_empty_state(self):
        self.assertEqual(review_state.read_state(self.path, REPO, PR), {"pr": PR, "repo": REPO, "findings": [], "last_round": 0})

    def test_corrupt_json_raises_instead_of_reading_empty(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertRaisesRegex(review_state.StateError, "is not valid JSON.*never delete or replace it"):
            review_state.read_state(self.path, REPO, PR)

    @unittest.skipUnless(HAS_RUBY, "ruby converts legacy YAML state")
    def test_legacy_yaml_converts_with_iso_timestamps(self):
        self.path.parent.mkdir(parents=True)
        self.path.with_suffix(".yml").write_text(
            "pr: 8094\nrepo: acme/shop\ncreated_at: 2026-11-18T20:15:00Z\nlast_round: 14\nfindings:\n"
            "  - id: 9c4f2a8b1e\n    file: src/upsert.ts\n    status: active\n", encoding="utf-8")
        converted = review_state.read_state(self.path, REPO, PR)
        self.assertEqual((converted["last_round"], converted["created_at"], converted["findings"][0]["id"]),
                         (14, "2026-11-18T20:15:00Z", "9c4f2a8b1e"))

    @unittest.skipUnless(HAS_RUBY, "ruby converts legacy YAML state")
    def test_digit_ids_and_shas_keep_their_exact_text(self):
        self.path.parent.mkdir(parents=True)
        self.path.with_suffix(".yml").write_text(
            "last_round: 14\nfindings:\n  - id: 0012345670\n    commit_sha_resolved: 0123456\n"
            "    caused_by: 9994482375\n  - id: 9c4f2a8b1e\n    caused_by: null\n", encoding="utf-8")
        first, second = review_state.read_state(self.path, REPO, PR)["findings"]
        self.assertEqual((first["id"], first["commit_sha_resolved"], first["caused_by"], second["caused_by"]),
                         ("0012345670", "0123456", "9994482375", None))

    @unittest.skipUnless(HAS_RUBY, "ruby converts legacy YAML state")
    def test_yaml_words_stay_text_outside_typed_keys(self):
        self.path.parent.mkdir(parents=True)
        self.path.with_suffix(".yml").write_text(
            "last_round: 14\nfindings:\n  - id: 9c4f2a8b1e\n    enclosing_symbol: on\n    dismissal_reason: no\n"
            "    last_message: 1.10\n    round_first_seen: 3\n    class_sites:\n      - { site: \"a.ts::on\", handled: true }\n"
            "convergence:\n  baseline: 0123456\n", encoding="utf-8")
        converted = review_state.read_state(self.path, REPO, PR)
        entry = converted["findings"][0]
        self.assertEqual((entry["enclosing_symbol"], entry["dismissal_reason"], entry["last_message"], entry["round_first_seen"],
                          entry["class_sites"][0]["handled"], converted["convergence"]["baseline"]),
                         ("on", "no", "1.10", 3, True, "0123456"))

    @unittest.skipUnless(HAS_RUBY, "ruby converts legacy YAML state")
    def test_multi_document_legacy_yaml_is_refused(self):
        self.path.parent.mkdir(parents=True)
        self.path.with_suffix(".yml").write_text("last_round: 3\nfindings: []\n---\nfindings: []\n", encoding="utf-8")
        with self.assertRaisesRegex(review_state.StateError, "2 YAML documents"):
            review_state.read_state(self.path, REPO, PR)

    @unittest.skipUnless(HAS_RUBY, "ruby converts legacy YAML state")
    def test_legacy_shape_problem_names_the_yaml_file_and_legacy_code(self):
        self.path.parent.mkdir(parents=True)
        self.path.with_suffix(".yml").write_text("last_round: 3\nfindings:\n", encoding="utf-8")
        with self.assertRaises(review_state.StateError) as raised:
            review_state.read_state(self.path, REPO, PR)
        self.assertEqual((raised.exception.exit_code, f"{PR}.yml" in str(raised.exception)), (review_state.LEGACY_EXIT, True))

    @unittest.skipUnless(HAS_RUBY, "ruby converts legacy YAML state")
    def test_aliases_are_refused_instead_of_crossing_types(self):
        self.path.parent.mkdir(parents=True)
        self.path.with_suffix(".yml").write_text("last_round: &r 2\nfindings: []\nnote: *r\n", encoding="utf-8")
        with self.assertRaises(review_state.StateError) as raised:
            review_state.read_state(self.path, REPO, PR)
        self.assertEqual(raised.exception.exit_code, review_state.LEGACY_EXIT)

    @unittest.skipUnless(HAS_RUBY, "ruby converts legacy YAML state")
    def test_parse_failure_names_the_ruby_version(self):
        self.path.parent.mkdir(parents=True)
        self.path.with_suffix(".yml").write_text("findings:\n  - label_history: [S1, S1\n", encoding="utf-8")
        with self.assertRaisesRegex(review_state.StateError, r"ruby \d+\.\d+\.\d+ cannot parse it"):
            review_state.read_state(self.path, REPO, PR)

    def test_failed_directory_sync_still_reports_the_saved_file(self):
        err = io.StringIO()
        with mock.patch.object(review_state.os, "fsync", side_effect=[None, OSError("EINVAL")]), redirect_stderr(err):
            review_state.write_state(self.path, state())
        self.assertEqual((self.path.exists(), "but its directory could not be synced" in err.getvalue()), (True, True))

    def test_ruby_failure_without_stderr_names_its_exit_code(self):
        self.path.parent.mkdir(parents=True)
        self.path.with_suffix(".yml").write_text("last_round: 3\n", encoding="utf-8")
        failed = subprocess.CompletedProcess(["ruby"], 1, stdout="", stderr="")
        with mock.patch.object(review_state.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(review_state.StateError, "ruby exited 1"):
                review_state.read_state(self.path, REPO, PR)

    def test_state_that_is_not_an_object_is_rejected(self):
        self.store([1, 2])
        with self.assertRaisesRegex(review_state.StateError, "must hold one JSON object"):
            review_state.read_state(self.path, REPO, PR)

    def test_state_of_another_pr_is_rejected(self):
        self.store(state(pr=7))
        with self.assertRaisesRegex(review_state.StateError, "belongs to PR 7"):
            review_state.read_state(self.path, REPO, PR)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads any file")
    def test_unreadable_state_file_raises_instead_of_reading_empty(self):
        self.store(state())
        self.path.chmod(0)
        self.addCleanup(self.path.chmod, 0o644)
        with self.assertRaisesRegex(review_state.StateError, "cannot read state file"):
            review_state.read_state(self.path, REPO, PR)

    @unittest.skipUnless(HAS_RUBY, "ruby converts legacy YAML state")
    def test_unparseable_legacy_yaml_exits_with_the_legacy_code(self):
        self.path.parent.mkdir(parents=True)
        self.path.with_suffix(".yml").write_text("findings:\n  - label_history: [S1, S1\n", encoding="utf-8")
        with self.assertRaises(review_state.StateError) as raised:
            review_state.read_state(self.path, REPO, PR)
        self.assertEqual(raised.exception.exit_code, review_state.LEGACY_EXIT)

    def test_missing_ruby_exits_with_the_legacy_code(self):
        self.path.parent.mkdir(parents=True)
        self.path.with_suffix(".yml").write_text("last_round: 3\n", encoding="utf-8")
        with mock.patch.object(review_state.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaises(review_state.StateError) as raised:
                review_state.read_state(self.path, REPO, PR)
        self.assertEqual((raised.exception.exit_code, "ruby is not installed); install ruby" in str(raised.exception)),
                         (review_state.LEGACY_EXIT, True))


class WriteTest(StateFileTest):
    def test_valid_state_is_written(self):
        review_state.write_state(self.path, state())
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["last_round"], 13)

    def test_lower_last_round_is_refused_and_the_file_kept(self):
        self.store(state(last_round=13))
        with self.assertRaisesRegex(review_state.StateError, "last_round 1 is below round 13"):
            review_state.write_state(self.path, state(last_round=1))
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["last_round"], 13)

    @unittest.skipUnless(HAS_RUBY, "ruby converts legacy YAML state")
    def test_legacy_round_is_the_floor_for_the_first_json_write(self):
        self.path.parent.mkdir(parents=True)
        self.path.with_suffix(".yml").write_text("last_round: 13\nfindings: []\n", encoding="utf-8")
        with self.assertRaisesRegex(review_state.StateError, "below round 13"):
            review_state.write_state(self.path, state(last_round=1))

    def test_write_never_goes_over_an_unconverted_legacy_file(self):
        self.path.parent.mkdir(parents=True)
        self.path.with_suffix(".yml").write_text("last_round: 13\nfindings:\n  - label_history: [S1, S1\n", encoding="utf-8")
        with mock.patch.object(review_state.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaises(review_state.StateError) as raised:
                review_state.write_state(self.path, state(last_round=14))
        self.assertEqual((raised.exception.exit_code, self.path.exists()), (review_state.LEGACY_EXIT, False))

    def test_dropping_a_stored_entry_with_a_malformed_id_is_refused(self):
        self.store(state(findings=[finding(), {"id": 12345, "file": "src/x.ts"}]))
        with self.assertRaisesRegex(review_state.StateError, "drops stored findings 12345"):
            review_state.write_state(self.path, state(last_round=14))

    def test_dropping_a_stored_finding_is_refused(self):
        self.store(state(findings=[finding(), finding(id="7e2b1c9f4a", file="src/pdf.ts")]))
        with self.assertRaisesRegex(review_state.StateError, "drops stored findings 7e2b1c9f4a"):
            review_state.write_state(self.path, state(last_round=14))

    def test_named_drop_is_allowed(self):
        self.store(state(findings=[finding(), finding(id="7e2b1c9f4a", file="src/pdf.ts")]))
        review_state.write_state(self.path, state(last_round=14), drops=["7e2b1c9f4a"])
        self.assertEqual(len(json.loads(self.path.read_text(encoding="utf-8"))["findings"]), 1)

    def test_failed_replace_leaves_no_temporary_file(self):
        with mock.patch.object(review_state.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(review_state.StateError, "cannot write"):
                review_state.write_state(self.path, state())
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_label_shaped_id_is_rejected(self):
        with self.assertRaisesRegex(review_state.StateError, r"findings\[0\]\.id must be the 10-hex"):
            review_state.write_state(self.path, state(findings=[finding(id="S1")]))

    def test_missing_identity_field_is_rejected(self):
        with self.assertRaisesRegex(review_state.StateError, r"findings\[0\]\.rule_class is required"):
            review_state.write_state(self.path, state(findings=[finding(rule_class="")]))

    def test_unknown_status_is_rejected(self):
        with self.assertRaisesRegex(review_state.StateError, "status must be one of"):
            review_state.write_state(self.path, state(findings=[finding(status="deferred")]))

    def test_duplicate_id_is_rejected(self):
        with self.assertRaisesRegex(review_state.StateError, "appears more than once"):
            review_state.write_state(self.path, state(findings=[finding(), finding(status="resolved")]))

    def test_extra_top_level_blocks_are_kept(self):
        review_state.write_state(self.path, state(convergence={"result": "continue"}))
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["convergence"], {"result": "continue"})

    def test_write_leaves_no_temporary_file(self):
        review_state.write_state(self.path, state())
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()), [self.path.name])


class MainTest(StateFileTest):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = review_state.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_round_prints_the_next_round(self):
        self.store(state(last_round=1))
        with mock.patch.object(review_state, "highest_posted_round", return_value=13):
            self.assertEqual(self.run_main("round", "--repo", REPO, "--pr", str(PR), "--file", str(self.path))[:2], (0, "14\n"))

    def test_write_problem_exits_two(self):
        source = pathlib.Path(self.tmp.name) / "new.json"
        source.write_text(json.dumps(state(last_round=0)), encoding="utf-8")
        code, _, err = self.run_main("write", "--file", str(self.path), "--input", str(source))
        self.assertEqual((code, "last_round must be the round this run posted" in err), (2, True))

    def test_read_prints_json(self):
        self.store(state())
        code, out, _ = self.run_main("read", "--repo", REPO, "--pr", str(PR), "--file", str(self.path))
        self.assertEqual((code, json.loads(out)["last_round"]), (0, 13))


if __name__ == "__main__":
    unittest.main()
