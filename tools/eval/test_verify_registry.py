"""Regression coverage for the skill-registry verifier check.

The first draft of the hidden-skill rule matched only the exact serialization
`internal: true` with nothing after it, so a trailing YAML comment
(`internal: true # hidden`) sailed through while the installer still hid the
skill. Manual planting found that; nothing preserved it. These tests do.

Every rule below is asserted in both directions. A check only seen passing is a
check nobody has tested.
"""
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = (ROOT / "tools" / "verify_skills.py").read_text(encoding="utf-8")

_NS: dict = {}
exec(SRC[: SRC.index("\ndef main():")], _NS)  # noqa: S102 - module has no import guard

check_skill_registry = _NS["check_skill_registry"]

README = """# Fixture

## Skills (slash commands)

| Skill | Description |
|-------|-------------|
| `alpha` | Test skill |

## Usage

```
{usage}
```

## Bundled tooling (not slash commands)

| Folder | Purpose |
|---|---|
| `coderabbit-config/` | Template sidecar. |
"""

SKILL = """---
name: alpha
description: Test skill.
{extra}---

# Alpha
"""


def _write(root, extra="", usage="/alpha  # test"):
    skill = root / "skills" / "alpha"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(SKILL.format(extra=extra), encoding="utf-8")
    (root / "coderabbit-config").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(README.format(usage=usage), encoding="utf-8")


def _run(root):
    old = (_NS["ROOT"], _NS["SKILLS"],
           _NS["fails"], _NS["warns"], _NS["notes"])
    skills = root / "skills"
    _NS["ROOT"] = skills
    _NS["SKILLS"] = sorted(
        (p for p in skills.iterdir() if p.is_dir() and (p / "SKILL.md").exists()),
        key=lambda p: p.name,
    )
    _NS["fails"], _NS["warns"], _NS["notes"] = [], [], []
    try:
        check_skill_registry()
        return [msg for _, msg in _NS["fails"]]
    finally:
        (_NS["ROOT"], _NS["SKILLS"],
         _NS["fails"], _NS["warns"], _NS["notes"]) = old


class SkillRegistry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name)

    def test_clean_layout_passes(self):
        _write(self.root)
        self.assertEqual([], _run(self.root))

    def test_trailing_comment_internal_fails(self):
        _write(self.root, extra="metadata:\n  internal: true # hidden\n")
        fails = _run(self.root)
        self.assertTrue(any("alpha" in f and "internal" in f for f in fails),
                        f"no internal failure in {fails}")

    def test_truthy_spellings_fail(self):
        for spelling in ["true", "True", "TRUE"]:
            with self.subTest(spelling=spelling):
                _write(self.root,
                       extra=f"metadata:\n  internal: {spelling}\n")
                fails = _run(self.root)
                self.assertTrue(any("internal" in f for f in fails),
                                f"{spelling} produced no failure")

    def test_yaml12_strings_pass(self):
        for spelling in ["yes", "on", "tRuE", "Yes", "On"]:
            with self.subTest(spelling=spelling):
                _write(self.root,
                       extra=f"metadata:\n  internal: {spelling}\n")
                self.assertEqual([], _run(self.root))

    def test_quoted_true_is_a_string_and_passes(self):
        _write(self.root, extra='metadata:\n  internal: "true"\n')
        self.assertEqual([], _run(self.root))

    def test_missing_usage_line_fails(self):
        _write(self.root, usage="")
        fails = _run(self.root)
        self.assertTrue(any("alpha" in f and "Usage" in f for f in fails),
                        f"no usage failure in {fails}")


if __name__ == "__main__":
    unittest.main()
