#!/usr/bin/env python3
"""Offline tests for tools/eval/harness.py.

These exist so the extraction that created harness.py could be proven safe without
re-running the eval suites, which cost roughly $30 and a half hour between them. Every
assertion runs on synthetic transcripts and temporary directories. Nothing here calls the
API, so a failure is always a real defect and never a flake.

    python3 tools/eval/test_harness.py
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

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


class TruncatedTranscript(unittest.TestCase):
    """A killed or overloaded run leaves a draft, and a draft is short and unfinished in
    exactly the direction that reads as cleaner prose. Scoring one as a finished answer is
    how a failed run becomes a false improvement."""

    def test_no_result_event_is_an_error(self):
        text, _, error = harness.parse_transcript(
            '{"type":"assistant","message":{"content":[{"type":"text","text":"Draft"}]}}')
        self.assertEqual(text, "Draft")
        self.assertIsNotNone(error)
        self.assertIn("truncated", error)

    def test_a_half_written_result_line_is_an_error(self):
        # iter_events drops the unparsable line, so nothing else would notice.
        _, _, error = harness.parse_transcript(
            '{"type":"assistant","message":{"content":[{"type":"text","text":"Draft"}]}}\n'
            '{"type":"result","is_error":true,"api_error_status":529,"result":"Overl')
        self.assertIsNotNone(error)

    def test_a_complete_clean_result_is_not_an_error(self):
        _, _, error = harness.parse_transcript(
            '{"type":"result","result":"done","is_error":false}')
        self.assertIsNone(error)

    def test_failure_subtype_without_is_error(self):
        self.assertIsNotNone(harness.format_result_error(
            {"is_error": False, "subtype": "error_max_turns", "result": "capped"}))
        self.assertIsNone(harness.format_result_error(
            {"is_error": False, "subtype": "success", "result": "fine"}))


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

    def test_a_drained_transcript_is_not_concatenated_with_the_partial(self):
        """communicate() after a TimeoutExpired returns the whole accumulated buffer, not the
        remainder, so appending the caller's partial would duplicate every early event."""
        proc = self._spawn(
            "import time\nprint('EARLY', flush=True)\ntime.sleep(1.5)\nprint('LATE')")
        try:
            proc.communicate(timeout=0.6)
        except subprocess.TimeoutExpired as expiry:
            partial = expiry.stdout
            if isinstance(partial, bytes):
                partial = partial.decode()
            self.assertIn("EARLY", partial)
            stdout, _ = harness.kill_process_group(proc, partial or "")
            self.assertEqual(stdout.count("EARLY"), 1)


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

    def test_skill_injection_into_codex_directory(self):
        repo = self._make(skills=[self.skill], skill_directory=".agents/skills")
        self.assertTrue((repo / ".agents" / "skills" / "demo" / "SKILL.md").is_file())

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

    def test_setup_failure_removes_the_allocated_root(self):
        allocated = pathlib.Path(tempfile.mkdtemp(prefix="harness-test-parent-")) / "root"
        self.addCleanup(lambda: allocated.parent.rmdir() if allocated.parent.exists() else None)
        missing = self.source / "missing"
        with mock.patch.object(harness.tempfile, "mkdtemp", return_value=str(allocated)):
            with self.assertRaises(OSError):
                harness.make_sandbox("ignored-", missing)
        self.assertFalse(allocated.exists())


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


class RegisterStaging(unittest.TestCase):
    """The rename that keeps a sandbox-injected skill from colliding with the copy the user
    already has installed. If it silently stopped working, both arms of an A/B run would
    load the same prose and every delta would be zero for the wrong reason."""

    def setUp(self):
        import run_register
        self.register = run_register
        self.source = pathlib.Path(tempfile.mkdtemp(prefix="stage-test-src-")) / "file-pr"
        (self.source / "references").mkdir(parents=True)
        (self.source / "SKILL.md").write_text(
            "---\nname: file-pr\ndescription: opens a PR\n---\n\n# File PR\n\nBody.\n")
        (self.source / "references" / "checks.md").write_text("reference body\n")
        self.into = pathlib.Path(tempfile.mkdtemp(prefix="stage-test-dest-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.source.parent, ignore_errors=True)
        shutil.rmtree(self.into, ignore_errors=True)

    def test_slug_is_rewritten_in_directory_and_frontmatter(self):
        staged = self.register.stage_under_unique_name(
            self.source, "file-pr-under-test", self.into)
        self.assertEqual(staged.name, "file-pr-under-test")
        self.assertIn("name: file-pr-under-test", (staged / "SKILL.md").read_text())
        self.assertNotIn("name: file-pr\n", (staged / "SKILL.md").read_text())

    def test_reference_files_come_along(self):
        staged = self.register.stage_under_unique_name(
            self.source, "file-pr-under-test", self.into)
        self.assertTrue((staged / "references" / "checks.md").is_file())

    def test_body_prose_is_untouched(self):
        staged = self.register.stage_under_unique_name(
            self.source, "file-pr-under-test", self.into)
        self.assertIn("# File PR\n\nBody.\n", (staged / "SKILL.md").read_text())

    def test_codex_canary_is_staged_without_changing_the_source(self):
        marker = "<!-- register-skill-loaded:file-pr-under-test -->"
        staged = self.register.stage_under_unique_name(
            self.source, "file-pr-under-test", self.into, canary=marker)
        self.assertIn(marker, (staged / "SKILL.md").read_text())
        self.assertNotIn(marker, (self.source / "SKILL.md").read_text())

    def test_a_skill_with_no_name_line_fails_loudly(self):
        (self.source / "SKILL.md").write_text("---\ndescription: no name here\n---\nBody\n")
        with self.assertRaises(ValueError):
            self.register.stage_under_unique_name(
                self.source, "file-pr-under-test", self.into)

    def test_every_case_prompt_carries_the_placeholder(self):
        import json as json_module
        spec = json_module.loads(self.register.CASES.read_text())
        self.assertTrue(spec["cases"])
        for case in spec["cases"]:
            self.assertIn("$SKILL_UNDER_TEST", case["prompt"], case["id"])
            self.assertTrue((self.register.SKILLS / case["skill"] / "SKILL.md").is_file(),
                            case["skill"])

    def test_bounded_prompt_leaves_scoring_margin(self):
        import json as json_module
        spec = json_module.loads(self.register.CASES.read_text())
        bounded = [case for case in spec["cases"] if "max_words" in case]
        self.assertTrue(bounded)
        for case in bounded:
            match = self.register.re.search(
                r"in (\d+) to (\d+) prose words total", case["prompt"])
            self.assertIsNotNone(match, case["id"])
            target_minimum, target_maximum = map(int, match.groups())
            self.assertLess(target_minimum, target_maximum, case["id"])
            self.assertGreaterEqual(
                target_minimum - case["min_words"], 20, case["id"])
            self.assertGreaterEqual(
                case["max_words"] - target_maximum, 20, case["id"])

    def test_no_case_grants_bash(self):
        self.assertNotIn("Bash", self.register.CASE_TOOLS)


class CodexRegisterTranscript(unittest.TestCase):
    def setUp(self):
        import run_register
        self.register = run_register
        self.marker = "<!-- register-skill-loaded:file-pr-under-test -->"

    def test_complete_turn_returns_the_final_agent_message(self):
        transcript = "\n".join([
            '{"type":"thread.started","thread_id":"thread-1"}',
            '{"type":"turn.started"}',
            '{"type":"item.completed","item":{"id":"item-1","type":"agent_message",'
            '"text":"Draft"}}',
            '{"type":"item.completed","item":{"id":"item-2","type":"agent_message",'
            '"text":"Final\\n<!-- register-skill-loaded:file-pr-under-test -->"}}',
            '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}',
        ])
        text, error = self.register.parse_codex_transcript(transcript)
        self.assertEqual(text, f"Final\n{self.marker}")
        self.assertIsNone(error)

    def test_missing_turn_completion_is_an_error(self):
        text, error = self.register.parse_codex_transcript("\n".join([
            '{"type":"thread.started","thread_id":"thread-1"}',
            '{"type":"turn.started"}',
            '{"type":"item.completed","item":{"type":"agent_message","text":"Draft"}}',
        ]))
        self.assertEqual(text, "Draft")
        self.assertIn("truncated", error)

    def test_turn_failure_is_an_error(self):
        transcript = "\n".join([
            '{"type":"thread.started","thread_id":"thread-1"}',
            '{"type":"turn.started"}',
            '{"type":"turn.failed","error":{"message":"rate limited"}}',
        ])
        _, error = self.register.parse_codex_transcript(transcript)
        self.assertIn("rate limited", error)

    def test_complete_turn_without_an_agent_message_is_an_error(self):
        _, error = self.register.parse_codex_transcript("\n".join([
            '{"type":"thread.started","thread_id":"thread-1"}',
            '{"type":"turn.started"}',
            '{"type":"turn.completed"}',
        ]))
        self.assertIn("agent message", error)

    def test_malformed_json_line_rejects_an_otherwise_complete_turn(self):
        transcript = "\n".join([
            '{"type":"thread.started","thread_id":"thread-1"}',
            '{"type":"turn.started"}',
            '{"type":"error","message":"broken"',
            '{"type":"item.completed","item":{"type":"agent_message","text":"Final"}}',
            '{"type":"turn.completed"}',
        ])
        _, error = self.register.parse_codex_transcript(transcript)
        self.assertIn("malformed JSONL", error)

    def test_agent_message_after_completion_is_rejected(self):
        transcript = "\n".join([
            '{"type":"thread.started","thread_id":"thread-1"}',
            '{"type":"turn.started"}',
            '{"type":"turn.completed"}',
            '{"type":"item.completed","item":{"type":"agent_message","text":"Late"}}',
        ])
        _, error = self.register.parse_codex_transcript(transcript)
        self.assertIn("after terminal", error)

    def test_recovered_error_can_finish_cleanly(self):
        transcript = "\n".join([
            '{"type":"thread.started","thread_id":"thread-1"}',
            '{"type":"turn.started"}',
            '{"type":"error","message":"Reconnecting... 2/5"}',
            '{"type":"item.completed","item":{"type":"agent_message","text":"Final"}}',
            '{"type":"turn.completed"}',
        ])
        text, error = self.register.parse_codex_transcript(transcript)
        self.assertEqual(text, "Final")
        self.assertIsNone(error)

    def test_model_reroute_rejects_an_otherwise_complete_turn(self):
        transcript = "\n".join([
            '{"type":"thread.started","thread_id":"thread-1"}',
            '{"type":"turn.started"}',
            '{"type":"item.completed","item":{"type":"error",'
            '"message":"model rerouted: gpt-a -> gpt-b (capacity)"}}',
            '{"type":"item.completed","item":{"type":"agent_message","text":"Final"}}',
            '{"type":"turn.completed"}',
        ])
        _, error = self.register.parse_codex_transcript(transcript)
        self.assertIn("model rerouted", error)

    def test_codex_command_pins_model_and_disables_installed_skill(self):
        command = self.register.build_codex_command(
            "prompt", "file-pr", "gpt-5.6-sol")
        self.assertEqual(command[command.index("--model") + 1], "gpt-5.6-sol")
        override = command[command.index("--config") + 1]
        installed = pathlib.Path.home() / ".agents" / "skills" / "file-pr" / "SKILL.md"
        self.assertIn(str(installed), override)
        self.assertIn("enabled=false", override)
        self.assertIn("--ignore-user-config", command)

    def test_canary_is_required_and_removed_before_scoring(self):
        cleaned, error = self.register.validate_codex_canary(
            f"PR body\n\n{self.marker}\n", self.marker)
        self.assertEqual(cleaned, "PR body")
        self.assertIsNone(error)

    def test_missing_canary_rejects_the_run(self):
        text, error = self.register.validate_codex_canary("PR body", self.marker)
        self.assertEqual(text, "PR body")
        self.assertIn("canary", error)


class RegisterProtocol(unittest.TestCase):
    def setUp(self):
        import run_register
        self.register = run_register

    def test_seeded_schedule_balances_each_pair(self):
        arms = [("baseline", pathlib.Path("old")), ("variant", pathlib.Path("new"))]
        schedule = self.register.build_arm_schedule(arms, repeat=5, seed=37)
        self.assertEqual(len(schedule), 10)
        for pair_index in range(5):
            pair = schedule[pair_index * 2:(pair_index + 1) * 2]
            self.assertEqual({entry[0] for entry in pair}, {"baseline", "variant"})
            self.assertEqual({entry[2] for entry in pair}, {pair_index})

    def test_seeded_schedule_is_reproducible(self):
        arms = [("baseline", pathlib.Path("old")), ("variant", pathlib.Path("new"))]
        first = self.register.build_arm_schedule(arms, repeat=8, seed=91)
        second = self.register.build_arm_schedule(arms, repeat=8, seed=91)
        self.assertEqual(first, second)

    def test_skill_digest_is_independent_of_file_creation_order(self):
        first = pathlib.Path(tempfile.mkdtemp(prefix="digest-first-"))
        second = pathlib.Path(tempfile.mkdtemp(prefix="digest-second-"))
        self.addCleanup(shutil.rmtree, first, True)
        self.addCleanup(shutil.rmtree, second, True)
        (first / "b.md").write_text("two")
        (first / "a.md").write_text("one")
        (second / "a.md").write_text("one")
        (second / "b.md").write_text("two")
        self.assertEqual(
            self.register.skill_directory_digest(first),
            self.register.skill_directory_digest(second),
        )

    def test_skill_digest_changes_with_content(self):
        skill = pathlib.Path(tempfile.mkdtemp(prefix="digest-change-"))
        self.addCleanup(shutil.rmtree, skill, True)
        path = skill / "SKILL.md"
        path.write_text("before")
        before = self.register.skill_directory_digest(skill)
        path.write_text("after")
        self.assertNotEqual(before, self.register.skill_directory_digest(skill))

    def test_arm_snapshot_is_immutable_after_the_source_changes(self):
        source_root = pathlib.Path(tempfile.mkdtemp(prefix="arm-source-"))
        self.addCleanup(shutil.rmtree, source_root, True)
        skill = source_root / "file-pr"
        skill.mkdir()
        source_file = skill / "SKILL.md"
        source_file.write_text("before")
        snapshot, arms, digests = self.register.snapshot_arm_roots(
            [("baseline", source_root)], "file-pr")
        self.addCleanup(snapshot.cleanup)
        source_file.write_text("after")
        snapshot_file = arms[0][1] / "file-pr" / "SKILL.md"
        self.assertEqual(snapshot_file.read_text(), "before")
        self.assertEqual(
            digests["baseline"],
            self.register.skill_directory_digest(arms[0][1] / "file-pr"),
        )

    def test_claude_rejects_a_model_flag_it_cannot_apply(self):
        done = subprocess.run([
            sys.executable,
            str(pathlib.Path(self.register.__file__)),
            "--runner", "claude",
            "--model", "ignored-model",
        ], capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("only valid with --runner codex", done.stderr)


class RegisterStatistics(unittest.TestCase):
    """The delta verdict decides whether a 90,000-word rewrite goes ahead, so the yardstick
    it uses has to be the right one."""

    def setUp(self):
        import run_register
        self.sigma = run_register.difference_sigma

    def test_identical_arms_report_zero(self):
        arm = {"mean": 2.37, "stdev": 0.77}
        change, sigma, _, _ = self.sigma(arm, arm, 5, 5)
        self.assertEqual(change, 0)
        self.assertEqual(sigma, 0)

    def test_uses_standard_error_not_raw_spread(self):
        # Real pr-body baseline after the language-aware code strip: nominalisation mean
        # 3.23, stdev 0.36 at n=5. A 0.46 improvement is 2 sigma on the standard error of
        # the difference and would have read as noise against the raw stdev.
        baseline = {"mean": 3.23, "stdev": 0.36}
        variant = {"mean": 2.77, "stdev": 0.36}
        _, sigma, _, _ = self.sigma(baseline, variant, 5, 5)
        self.assertLess(sigma, -1.9)
        self.assertGreater(abs(sigma), 0.46 / 0.36)

    def test_a_single_run_per_arm_cannot_be_judged(self):
        _, sigma, _, _ = self.sigma({"mean": 1.0, "stdev": 0.0}, {"mean": 5.0, "stdev": 0.0}, 1, 1)
        self.assertIsNone(sigma)

    def test_zero_spread_in_both_arms_is_not_infinite_confidence(self):
        _, sigma, _, _ = self.sigma({"mean": 1.0, "stdev": 0.0}, {"mean": 5.0, "stdev": 0.0}, 5, 5)
        self.assertIsNone(sigma)

    def test_more_runs_raise_confidence_for_the_same_change(self):
        baseline = {"mean": 3.23, "stdev": 0.36}
        variant = {"mean": 2.95, "stdev": 0.36}
        _, at_five, _, _ = self.sigma(baseline, variant, 5, 5)
        _, at_twenty, _, _ = self.sigma(baseline, variant, 20, 20)
        self.assertGreater(abs(at_twenty), abs(at_five))

    def test_improvement_is_negative(self):
        _, sigma, _, _ = self.sigma({"mean": 5.0, "stdev": 0.5}, {"mean": 3.0, "stdev": 0.5}, 5, 5)
        self.assertLess(sigma, 0)

    def test_zero_spread_is_not_diagnosed_as_too_few_runs(self):
        _, sigma, _, why = self.sigma(
            {"mean": 0.0, "stdev": 0.0}, {"mean": 12.5, "stdev": 0.0}, 8, 8)
        self.assertIsNone(sigma)
        self.assertIn("variance", why)
        self.assertNotIn("2+", why)

    def test_too_few_runs_says_so(self):
        _, sigma, _, why = self.sigma({"mean": 1.0, "stdev": 0.0}, {"mean": 5.0, "stdev": 0.0}, 1, 1)
        self.assertIsNone(sigma)
        self.assertIn("2+", why)


class SignificanceThreshold(unittest.TestCase):
    def setUp(self):
        import run_register
        self.register = run_register

    def test_small_samples_demand_more_than_two_sigma(self):
        self.assertGreater(self.register.t_critical(4), 2.7)

    def test_threshold_falls_toward_the_normal_limit(self):
        self.assertLess(self.register.t_critical(500), 2.0)
        self.assertGreater(self.register.t_critical(500), 1.9)

    def test_thresholds_decrease_monotonically(self):
        values = [self.register.t_critical(df) for df in range(1, 40)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_matches_the_published_t_table(self):
        """Monotonicity alone let t_critical(30) return 1.96 where the table holds 2.042: a
        wrongly low value still decreases. Only checking against real values catches that."""
        for degrees, expected in {1: 12.706, 4: 2.776, 8: 2.306, 20: 2.086,
                                  30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980}.items():
            self.assertEqual(self.register.t_critical(degrees), expected, f"df={degrees}")

    def test_never_returns_below_the_smallest_finite_row(self):
        for degrees in range(1, 400):
            self.assertGreaterEqual(self.register.t_critical(degrees), 1.980, f"df={degrees}")

    def test_there_is_no_normal_limit_cliff(self):
        """1.960 is the df=infinity value and every finite df sits above it, so returning it
        past the table handed out a threshold below the true cutoff. The previous version of
        this test pinned that behaviour by asserting t_critical(200) == 1.960."""
        self.assertEqual(self.register.t_critical(120), self.register.t_critical(120.1))
        for degrees in (121, 200, 1000, 100000):
            self.assertGreater(self.register.t_critical(degrees), 1.960, f"df={degrees}")

    def test_fractional_welch_df_does_not_jump_a_row(self):
        # Welch degrees of freedom are fractional, so the boundary is reachable in practice.
        self.assertEqual(self.register.t_critical(30.0), self.register.t_critical(30.9))
        self.assertGreater(self.register.t_critical(29.9), self.register.t_critical(30.0))

    def test_an_untabulated_df_rounds_down_not_up(self):
        # Rounding up returns a smaller critical value than the true df warrants, which is
        # the direction that invents significance.
        self.assertEqual(self.register.t_critical(11), self.register.t_critical(10))
        self.assertGreater(self.register.t_critical(11), self.register.t_critical(12))

    def test_welch_df_collapses_when_one_arm_is_noisier(self):
        # 20x variance ratio at n=3: pooled says df=4 and t=2.776, Welch says df=2 and
        # t=4.303, and a sigma of 3.0 sits between them.
        quiet = {"mean": 1.0, "stdev": 0.1}
        noisy = {"mean": 4.47, "stdev": 2.0}
        degrees = self.register.welch_degrees_of_freedom(quiet, noisy, 3, 3)
        self.assertLess(degrees, 3)
        self.assertGreater(self.register.t_critical(degrees), 4.0)

    def test_equal_variance_welch_df_matches_the_pooled_value(self):
        arm = {"mean": 3.0, "stdev": 0.5}
        self.assertAlmostEqual(
            self.register.welch_degrees_of_freedom(arm, dict(arm), 5, 5), 8.0, places=6)

    def test_unequal_variances_are_not_called_significant_below_95(self):
        quiet = {"mean": 1.0, "stdev": 0.1}
        noisy = {"mean": 4.47, "stdev": 2.0}
        _, sigma, degrees, _ = self.register.difference_sigma(quiet, noisy, 3, 3)
        self.assertGreater(abs(sigma), 2.776)
        self.assertLess(abs(sigma), self.register.t_critical(degrees))

    def test_one_metric_decides_and_it_is_tracked(self):
        self.assertIn(self.register.PRIMARY_METRIC, self.register.TRACKED_MEASURES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
