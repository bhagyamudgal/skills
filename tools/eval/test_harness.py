#!/usr/bin/env python3
"""Offline tests for tools/eval/harness.py.

These exist so the extraction that created harness.py could be proven safe without
re-running the eval suites, which cost roughly $30 and a half hour between them. Every
assertion runs on synthetic transcripts and temporary directories. Nothing here calls the
API, so a failure is always a real defect and never a flake.

    python3 tools/eval/test_harness.py
"""
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import harness


class FormatResultError(unittest.TestCase):
    def test_success_is_none(self):
        self.assertIsNone(harness.format_result_error({"is_error": False, "result": "ok"}))
        self.assertIsNone(harness.format_result_error({}))

    def test_api_status_and_reason_and_detail(self):
        self.assertEqual(
            harness.format_result_error({
                "is_error": True,
                "api_error_status": 529,
                "terminal_reason": "budget_exceeded",
                "result": "overloaded",
            }),
            "api error 529: budget_exceeded: overloaded",
        )

    def test_completed_reason_is_suppressed(self):
        self.assertEqual(
            harness.format_result_error(
                {"is_error": True, "terminal_reason": "completed", "result": "boom"}),
            "boom",
        )

    def test_newlines_flattened_and_detail_truncated(self):
        got = harness.format_result_error(
            {"is_error": True, "result": "a\nb" + "x" * 400})
        self.assertNotIn("\n", got)
        self.assertEqual(len(got), 160)

    def test_empty_error_still_reports(self):
        self.assertEqual(
            harness.format_result_error({"is_error": True, "result": "   "}), "result-error")

    def test_detail_source_overrides_result(self):
        self.assertEqual(
            harness.format_result_error({"is_error": True, "result": "ignored"}, "used"),
            "used",
        )


class ParseSkillNames(unittest.TestCase):
    def _assistant(self, *blocks):
        return {"type": "assistant", "message": {"content": list(blocks)}}

    def test_non_assistant_events_yield_nothing(self):
        self.assertEqual(harness.parse_skill_names({"type": "result"}), [])
        self.assertEqual(harness.parse_skill_names({}), [])

    def test_single_skill(self):
        event = self._assistant(
            {"type": "tool_use", "name": "Skill", "input": {"skill": "git-commit"}})
        self.assertEqual(harness.parse_skill_names(event), ["git-commit"])

    def test_preserves_order_of_several_skills(self):
        event = self._assistant(
            {"type": "tool_use", "name": "Skill", "input": {"skill": "unslop"}},
            {"type": "tool_use", "name": "Skill", "input": {"skill": "done"}},
        )
        self.assertEqual(harness.parse_skill_names(event), ["unslop", "done"])

    def test_ignores_other_tools_and_text(self):
        event = self._assistant(
            {"type": "text", "text": "Skill"},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
            {"type": "tool_use", "name": "Skill", "input": {"skill": "simplify"}},
        )
        self.assertEqual(harness.parse_skill_names(event), ["simplify"])

    def test_missing_input_yields_none_entry(self):
        event = self._assistant({"type": "tool_use", "name": "Skill"})
        self.assertEqual(harness.parse_skill_names(event), [None])


class Verdict(unittest.TestCase):
    def test_all_hits_pass(self):
        self.assertEqual(harness.verdict(3, 3), "PASS")

    def test_partial_is_flaky(self):
        self.assertEqual(harness.verdict(1, 3), "FLAKY")

    def test_zero_is_fail(self):
        self.assertEqual(harness.verdict(0, 3), "FAIL")

    def test_error_outranks_a_clean_sweep(self):
        self.assertEqual(harness.verdict(3, 3, has_error=True), "ERROR")


class IterEvents(unittest.TestCase):
    def test_skips_unparsable_lines(self):
        text = '{"a": 1}\nnot json\n\n{"b": 2}\n'
        self.assertEqual(list(harness.iter_events(text)), [{"a": 1}, {"b": 2}])


class KillProcessGroup(unittest.TestCase):
    def _spawn(self, script):
        proc = subprocess.Popen(
            [sys.executable, "-c", script], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, start_new_session=True)
        self.addCleanup(harness.kill_process_group, proc)
        return proc

    def test_drains_what_the_child_already_wrote(self):
        proc = self._spawn("print('hello', flush=True)\nimport time; time.sleep(30)")
        time.sleep(0.5)
        stdout, _ = harness.kill_process_group(proc)
        self.assertIn("hello", stdout)

    def test_falls_back_to_partial_when_the_child_wrote_nothing(self):
        proc = self._spawn("import time; time.sleep(30)")
        stdout, _ = harness.kill_process_group(proc, partial_stdout="earlier")
        self.assertEqual(stdout, "earlier")

    def test_an_already_exited_process_does_not_raise(self):
        proc = self._spawn("pass")
        proc.wait()
        stdout, _ = harness.kill_process_group(proc, partial_stdout="kept")
        self.assertEqual(stdout, "kept")

    def test_child_is_actually_dead_afterwards(self):
        proc = self._spawn("import time; time.sleep(30)")
        harness.kill_process_group(proc)
        self.assertIsNotNone(proc.poll())


class MakeSandbox(unittest.TestCase):
    def setUp(self):
        self.source = pathlib.Path(tempfile.mkdtemp(prefix="harness-test-src-"))
        (self.source / "src").mkdir()
        (self.source / "src" / "user.ts").write_text("export const VERSION = 1;\n")
        self.skill = pathlib.Path(tempfile.mkdtemp(prefix="harness-test-skill-")) / "demo"
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_text("# demo\n")
        self.roots = []

    def tearDown(self):
        import shutil
        for root in self.roots:
            shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(self.source, ignore_errors=True)
        shutil.rmtree(self.skill.parent, ignore_errors=True)

    def _make(self, **kwargs):
        root, repo = harness.make_sandbox("harness-test-", self.source, **kwargs)
        self.roots.append(root)
        return repo

    def test_fixture_lands_at_repo_root_and_is_committed(self):
        repo = self._make()
        self.assertTrue((repo / "src" / "user.ts").is_file())
        tracked = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True)
        self.assertIn("src/user.ts", tracked.stdout)

    def test_sandbox_is_outside_the_source_tree(self):
        repo = self._make()
        self.assertNotIn(self.source, repo.parents)

    def test_nested_destination(self):
        repo = self._make(fixture_dest="tools/eval/fixture")
        self.assertTrue((repo / "tools" / "eval" / "fixture" / "src" / "user.ts").is_file())

    def test_skill_injection(self):
        repo = self._make(skills=[self.skill])
        self.assertTrue((repo / ".claude" / "skills" / "demo" / "SKILL.md").is_file())

    def test_post_commit_edit_leaves_a_dirty_tree(self):
        def edit(repo):
            path = repo / "src" / "user.ts"
            path.write_text(path.read_text() + "export const VERSION = 2;\n")

        repo = self._make(post_commit_edit=edit)
        status = subprocess.run(["git", "status", "--short"],
                                cwd=repo, capture_output=True, text=True)
        self.assertIn("src/user.ts", status.stdout)

    def test_without_post_commit_edit_the_tree_is_clean(self):
        repo = self._make()
        status = subprocess.run(["git", "status", "--short"],
                                cwd=repo, capture_output=True, text=True)
        self.assertEqual(status.stdout.strip(), "")


class MigratedCallers(unittest.TestCase):
    """Guards the two harnesses against a regression in the extraction that created
    harness.py. Everything here runs offline, so it can gate a commit."""

    def setUp(self):
        import run_triggers
        import run_verify_claims
        self.triggers = run_triggers
        self.claims = run_verify_claims
        self.roots = []

    def tearDown(self):
        import shutil
        for root in self.roots:
            shutil.rmtree(root, ignore_errors=True)

    def test_trigger_sandbox_has_a_diff_to_review(self):
        root, repo = self.triggers.make_sandbox()
        self.roots.append(root)
        status = subprocess.run(["git", "status", "--short"],
                                cwd=repo, capture_output=True, text=True)
        self.assertIn("src/user.ts", status.stdout)

    def test_claims_fixture_lands_where_the_prompts_address_it(self):
        root, repo = self.claims.make_sandbox()
        self.roots.append(root)
        # The case prompts name this path literally. If it moves, every Read in every
        # prompt misses and the run fails for a reason no assertion names.
        self.assertTrue((repo / "tools" / "eval" / "verify-claims-fixture"
                         / "code" / "discount.py").is_file())
        self.assertTrue((repo / ".claude" / "skills" / "verify-claims" / "SKILL.md").is_file())

    def test_claims_parse_stream_still_reads_a_transcript(self):
        transcript = "\n".join([
            '{"type":"assistant","message":{"content":['
            '{"type":"text","text":"draft"},'
            '{"type":"tool_use","id":"t1","name":"Read","input":{"file_path":"discount.py"}}]}}',
            '{"type":"user","message":{"content":['
            '{"type":"tool_result","tool_use_id":"t1","content":"def calculate_discount"}]}}',
            'garbage that is not json',
            '{"type":"result","result":"**State:** verified","is_error":false}',
        ])
        final_text, tool_calls, error = self.claims.parse_stream(transcript)
        self.assertEqual(final_text, "**State:** verified")
        self.assertIsNone(error)
        self.assertEqual([call["name"] for call in tool_calls], ["Read"])
        self.assertEqual(tool_calls[0]["result"], "def calculate_discount")

    def test_claims_parse_stream_reports_a_failed_result(self):
        transcript = ('{"type":"result","result":"boom","is_error":true,'
                      '"api_error_status":529}')
        _, _, error = self.claims.parse_stream(transcript)
        self.assertEqual(error, "api error 529: boom")

    def test_trigger_ambient_default_covers_the_global_rule(self):
        self.assertIn("unslop", self.triggers.AMBIENT_SKILLS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
