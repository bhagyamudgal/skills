"""Regression coverage for the fence-derived verifier checks.

These rules exist to catch documents that make a claim about their own sequence
which the sequence does not satisfy. The first draft of the orphan-function rule
could never fire: its call detector matched the definition line itself, so it
reported nothing on a planted defect and looked exactly like a pass. Manual
planting found that; nothing preserved it. These tests do.

Every rule below is asserted in both directions. A check only seen passing is a
check nobody has tested.
"""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = (ROOT / "tools" / "verify_skills.py").read_text(encoding="utf-8")

_NS: dict = {}
exec(SRC[: SRC.index("\ndef main():")], _NS)  # noqa: S102 - module has no import guard

bash_blocks = _NS["_bash_blocks"]
fenced_spans = _NS["_fenced_spans"]


class BashFenceParser(unittest.TestCase):
    def test_plain_fence_body_starts_after_the_fence(self):
        blocks = bash_blocks(["intro", "```bash", "FOO=1", "```"])
        self.assertEqual([(3, ["FOO=1"])], blocks)

    def test_indented_fence_is_seen(self):
        self.assertEqual(1, len(bash_blocks(["  ```bash", "  FOO=1", "  ```"])))

    def test_four_backtick_fence_is_seen(self):
        self.assertEqual(1, len(bash_blocks(["````bash", "FOO=1", "````"])))

    def test_longer_fence_may_contain_a_shorter_one(self):
        lines = ["````bash", "echo a", "```", "echo b", "````"]
        self.assertEqual([(2, ["echo a", "```", "echo b"])], bash_blocks(lines))

    def test_non_bash_fence_is_not_a_bash_block_but_is_still_a_span(self):
        lines = ["```python", "x = 1", "```"]
        self.assertEqual([], bash_blocks(lines))
        self.assertEqual(1, len(fenced_spans(lines)))


class Collector:
    """Captures fail/warn so a rule can be asserted without running main()."""

    def __init__(self):
        self.fails, self.warns = [], []

    def install(self):
        _NS["fail"] = lambda t, m: self.fails.append(m)
        _NS["warn"] = lambda t, m: self.warns.append(m)


def run_checks(tmpdir, body):
    path = pathlib.Path(tmpdir) / "SKILL.md"
    path.write_text(body, encoding="utf-8")
    _NS["EVERY_MD"] = [path]
    _NS["read"] = lambda p: p.read_text(encoding="utf-8").split("\n")
    _NS["rel"] = lambda p: "SKILL.md"
    got = Collector()
    got.install()
    _NS["check_placeholder_consistency"]()
    _NS["check_bash_block_chain"]()
    return got


import tempfile  # noqa: E402 - kept beside its only user


class PlaceholderConsistency(unittest.TestCase):
    def test_a_name_written_both_ways_fails(self):
        body = "```bash\nBOARD=1\necho \"$BOARD\"\n```\n\n```bash\ngh x --owner <BOARD>\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertTrue(any("written as both" in m for m in got.fails), got.fails)

    def test_distinct_names_pass(self):
        body = "```bash\nBOARD_ID=1\necho \"$BOARD_ID\"\n```\n\n```bash\ngh x --owner <OWNER>\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertEqual([], [m for m in got.fails if "written as both" in m])


class OrphanFunction(unittest.TestCase):
    def test_defined_and_never_named_again_fails(self):
        body = "```bash\nunused() {\n  echo hi\n}\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertTrue(any("never called" in m for m in got.fails), got.fails)

    def test_single_fence_file_is_still_checked(self):
        """A one-fence file used to skip function analysis entirely."""
        body = "only one fence\n\n```bash\nunused() { :; }\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertTrue(any("never called" in m for m in got.fails), got.fails)

    def test_a_call_from_another_fence_passes(self):
        body = "```bash\nhelper() {\n  echo hi\n}\n```\n\n```bash\nhelper\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertEqual([], [m for m in got.fails if "never called" in m])

    def test_a_mention_in_prose_counts_as_a_call(self):
        """review-pr defines a cleanup helper and invokes it from instructions."""
        body = "Run `helper` before posting.\n\n```bash\nhelper() {\n  echo hi\n}\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertEqual([], [m for m in got.fails if "never called" in m])


class UnsetRead(unittest.TestCase):
    def test_read_with_no_assignment_anywhere_warns(self):
        body = "```bash\necho \"$NOWHERE/x\"\n```\n\n```bash\necho done\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertTrue(any("NOWHERE" in m for m in got.warns), got.warns)

    def test_assignment_after_the_read_still_warns(self):
        """An assignment in a later block does not make an earlier read safe."""
        body = "```bash\necho \"$LATE/x\"\n```\n\n```bash\nLATE=/tmp\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertTrue(any("LATE" in m for m in got.warns), got.warns)

    def test_read_then_assign_inside_one_fence_warns(self):
        """Ordering is by line, not by fence. Comparing fence indexes scored a
        read and a later assignment in the same block equal and stayed silent,
        while the unsafe read still executes first."""
        body = "```bash\necho \"$SAME/x\"\nSAME=/tmp\n```\n\n```bash\necho done\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertTrue(any("SAME" in m for m in got.warns), got.warns)

    def test_assign_then_read_inside_one_fence_passes(self):
        body = "```bash\nSAME=/tmp\necho \"$SAME/x\"\n```\n\n```bash\necho done\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertEqual([], [m for m in got.warns if "SAME" in m])

    def test_assign_and_read_on_one_line_passes(self):
        """`WORK=$(mktemp -d); echo "$WORK"` is the ordinary setup shape. A
        strict line comparison rejected the assignment and warned falsely, which
        is how fixing the within-fence false negative created a false positive."""
        body = "```bash\nONELINE=$(mktemp -d); echo \"$ONELINE\"\n```\n\n```bash\necho done\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertEqual([], [m for m in got.warns if "ONELINE" in m])

    def test_read_then_assign_on_one_line_warns(self):
        body = "```bash\necho \"$ONELINE\"; ONELINE=v\n```\n\n```bash\necho done\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertTrue(any("ONELINE" in m for m in got.warns), got.warns)

    def test_assignment_after_a_shell_operator_is_seen(self):
        """`[ -z "$C" ] && MID=a || MID=b` assigns, but an `^\\s*` anchored
        pattern never sees it and every later read warns falsely."""
        body = "```bash\n[ -z \"$C\" ] && MID=a || MID=b\necho \"$MID\"\n```\n\n```bash\necho done\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertEqual([], [m for m in got.warns if "MID" in m])

    def test_assignment_before_the_read_passes(self):
        body = "```bash\nEARLY=/tmp\n```\n\n```bash\necho \"$EARLY/x\"\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertEqual([], [m for m in got.warns if "EARLY" in m])

    def test_a_guard_before_the_read_passes(self):
        body = "```bash\n: \"${GUARDED:?set it}\"\necho \"$GUARDED/x\"\n```\n\n```bash\necho done\n```\n"
        with tempfile.TemporaryDirectory() as d:
            got = run_checks(d, body)
        self.assertEqual([], [m for m in got.warns if "GUARDED" in m])


if __name__ == "__main__":
    unittest.main()
