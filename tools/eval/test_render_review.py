import copy
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "skills" / "review-pr" / "scripts" / "render_review.py"
SPEC = importlib.util.spec_from_file_location("render_review", SCRIPT)
render_review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_review)

SHA = "0123456789abcdef0123456789abcdef01234567"
META = {"pr": 123, "head_sha": SHA, "round": 2}
PATH = "apps/backend/src/import/address.ts"
REPO = "acme/shop"

DIFF = f"""diff --git a/{PATH} b/{PATH}
--- a/{PATH}
+++ b/{PATH}
@@ -40,3 +40,4 @@ export function resolveCountry() {{
 const account = load();
+const fallback = "DE";
 return fallback;
 }}
"""

MULTI_FILE_DIFF = "\n".join([
    "diff --git a/old.ts b/new.ts",
    "similarity index 90%",
    "rename from old.ts",
    "rename to new.ts",
    "--- a/old.ts",
    "+++ b/new.ts",
    "@@ -1 +1 @@",
    "-a",
    "+b",
    "diff --git a/gone.ts b/gone.ts",
    "deleted file mode 100644",
    "--- a/gone.ts",
    "+++ /dev/null",
    "@@ -1,2 +0,0 @@",
    "-x",
    "-y",
    "diff --git a/fresh.ts b/fresh.ts",
    "new file mode 100644",
    "--- /dev/null",
    "+++ b/fresh.ts",
    "@@ -0,0 +1,3 @@",
    "+++ looks like a header",
    "+second still second",
    "+third",
    "\\ No newline at end of file",
    'diff --git "a/caf\\303\\251.ts" "b/caf\\303\\251.ts"',
    '--- "a/caf\\303\\251.ts"',
    '+++ "b/caf\\303\\251.ts"',
    "@@ -5,2 +5,2 @@",
    " keep",
    "-old",
    "+new",
    "diff --git a/logo.png b/logo.png",
    "Binary files a/logo.png and b/logo.png differ",
    "",
])

EXPECTED_SUMMARY = f"""<!-- review-pr:run sha={SHA} round=2 -->
## PR Review: #123
❌ request-changes | 🟠 1 Serious
**Senior engineer approval**: ❌ No, The import drops rows whose country cell is blank.

**Goal**: Import client workbooks without inventing address values.
**Summary**: The parser and writer are sound. One branch still writes a placeholder country.

### Findings

| # | Sev | File | Issue |
|---|-----|------|-------|
| S1 | 🟠 | `{PATH}:42` | A blank country cell falls back to a hardcoded country. |

*Details in review comments below.*"""


def example():
    return copy.deepcopy(render_review.EXAMPLE)


def finding(**overrides):
    return {**render_review.EXAMPLE["findings"][0], **overrides}


def render(review, diff=DIFF):
    return render_review.render(review, diff, META)


def clean_approve():
    review = example()
    review.update(verdict="approve", findings=[], senior_approval={"approved": True, "reason": "Nothing blocks it."})
    return review


def verdict_line_fields(summary):
    lines = summary.splitlines()
    return lines[lines.index("## PR Review: #123") + 1].split()


class SummaryShapeTest(unittest.TestCase):
    def test_request_changes_summary_is_exact(self):
        self.assertEqual(render(example())["summary.md"], EXPECTED_SUMMARY)

    def test_rendering_is_deterministic(self):
        self.assertEqual(render(example()), render(example()))

    def test_clean_approve_keeps_the_rerun_parser_fields(self):
        self.assertEqual(verdict_line_fields(render(clean_approve())["summary.md"])[:3], ["✅", "approve", "|"])

    def test_clean_approve_says_no_findings(self):
        summary = render(clean_approve())["summary.md"]
        self.assertIn("### Findings\n\nNo findings.", summary)
        self.assertNotIn("Details in review comments", summary)

    def test_summary_never_carries_filtered_out(self):
        self.assertNotIn("Filtered out", render(example())["summary.md"])

    def test_pipe_in_issue_is_escaped_in_the_table(self):
        review = example()
        review["findings"] = [finding(issue="Type is `x: string | null` now.")]
        self.assertIn("`x: string \\| null` now. |", render(review)["summary.md"])


class DiffParsingTest(unittest.TestCase):
    def setUp(self):
        self.files = render_review.parse_diff(MULTI_FILE_DIFF)

    def test_rename_tracks_the_new_path(self):
        self.assertEqual(self.files["new.ts"], {1})

    def test_new_file_lines_ignore_header_lookalikes_and_unicode_separators(self):
        self.assertEqual(self.files["fresh.ts"], {1, 2, 3})

    def test_deleted_file_has_no_post_image_lines(self):
        self.assertNotIn("/dev/null", self.files)

    def test_quoted_path_is_unquoted(self):
        self.assertEqual(self.files["café.ts"], {5, 6})

    def test_binary_file_is_known_without_lines(self):
        self.assertEqual(self.files["logo.png"], set())

    def test_quoted_binary_header_without_hunks_is_kept(self):
        diff = ('diff --git "a/images/caf\\303\\251.png" "b/images/caf\\303\\251.png"\n'
                "index 1234567..abcdef0 100644\n"
                'Binary files "a/images/caf\\303\\251.png" and "b/images/caf\\303\\251.png" differ\n')
        self.assertEqual(render_review.parse_diff(diff), {"images/café.png": set()})

    def test_quoted_mode_only_change_is_kept(self):
        diff = 'diff --git "a/caf\\303\\251.sh" "b/caf\\303\\251.sh"\nold mode 100644\nnew mode 100755\n'
        self.assertEqual(render_review.parse_diff(diff), {"café.sh": set()})

    def test_embedded_b_slash_in_binary_path_invents_no_phantom(self):
        diff = "diff --git a/foo b/bar b/foo b/bar\nBinary files a/foo b/bar and b/foo b/bar differ\n"
        self.assertEqual(render_review.parse_diff(diff), {"foo b/bar": set()})

    def test_embedded_b_slash_in_text_path_invents_no_phantom(self):
        diff = "diff --git a/foo b/bar b/foo b/bar\n--- a/foo b/bar\n+++ b/foo b/bar\n@@ -1 +1 @@\n-a\n+b\n"
        self.assertEqual(render_review.parse_diff(diff), {"foo b/bar": {1}})

    def test_binary_copy_tracks_the_copy_target(self):
        diff = "diff --git a/x.png b/y.png\nsimilarity index 100%\ncopy from x.png\ncopy to y.png\n"
        self.assertEqual(render_review.parse_diff(diff), {"y.png": set()})

    def test_mixed_quoted_header_reads_the_quoted_target(self):
        self.assertEqual(render_review.parse_diff('diff --git a/cafe "b/caf\\303\\251"\nBinary files differ\n'), {"café": set()})

    def test_escaped_quote_inside_quoted_path(self):
        self.assertEqual(render_review.parse_diff('diff --git "a/say \\"hi\\".md" "b/say \\"hi\\".md"\nold mode 100644\nnew mode 100755\n'),
                         {'say "hi".md': set()})

    def test_quoted_copy_target_is_unquoted(self):
        diff = 'diff --git a/x.png "b/caf\\303\\251.png"\ncopy from x.png\ncopy to "caf\\303\\251.png"\n'
        self.assertEqual(render_review.parse_diff(diff), {"café.png": set()})

    def test_finding_on_quoted_binary_file_gets_a_file_thread(self):
        diff = 'diff --git "a/images/caf\\303\\251.png" "b/images/caf\\303\\251.png"\nBinary files differ\n'
        review = example()
        review["findings"] = [finding(file="images/café.png", line=None)]
        self.assertEqual(render_review.render(review, diff, META)["ids.json"][0]["tier"], "file")

    def test_hunk_header_without_counts(self):
        self.assertEqual(render_review.parse_diff("--- a/f\n+++ b/f\n@@ -3 +3 @@\n-a\n+b\n")["f"], {3})


class RoutingTest(unittest.TestCase):
    def test_line_in_diff_becomes_line_comment(self):
        self.assertEqual([(c["path"], c["line"], c["side"]) for c in render(example())["line_comments.json"]],
                         [(PATH, 42, "RIGHT")])

    def test_line_outside_diff_becomes_file_level(self):
        review = example()
        review["findings"] = [finding(line=7)]
        outputs = render(review)
        self.assertEqual((outputs["line_comments.json"], [c["label"] for c in outputs["file_level.json"]]), ([], ["S1"]))

    def test_file_outside_the_diff_goes_to_body(self):
        review = example()
        review["findings"] = [finding(file="elsewhere.ts", line=3)]
        outputs = render(review)
        self.assertEqual((outputs["line_comments.json"], outputs["file_level.json"], outputs["ids.json"][0]["tier"]), ([], [], "body"))

    def test_finding_without_file_goes_to_body(self):
        review = example()
        review["findings"] = [finding(file=None, line=None)]
        summary = render(review)["summary.md"]
        self.assertTrue("| S1 | 🟠 | *(general)* |" in summary and "### Additional findings" in summary)
        self.assertNotIn("Details in review comments", summary)

    def test_ids_map_state_ids_to_labels_and_tiers(self):
        self.assertEqual(render(example())["ids.json"],
                         [{"finding_id": "3f2a9c1d7e", "label": "S1", "tier": "line", "file": PATH, "line": 42}])


class FindingOrderTest(unittest.TestCase):
    def test_labels_follow_severity_then_input_order(self):
        review = example()
        review["findings"] = [finding(severity="Minor", issue="a."), finding(severity="Critical", issue="b."),
                              finding(severity="Minor", issue="c.")]
        self.assertEqual([(e["label"], e["finding_id"]) for e in render(review)["ids.json"]],
                         [("C1", "3f2a9c1d7e"), ("m1", "3f2a9c1d7e"), ("m2", "3f2a9c1d7e")])

    def test_pre_existing_shares_severity_counters_after_introduced(self):
        review = example()
        review["findings"] = [finding(origin="pre-existing", blame="abc1234"), finding()]
        self.assertEqual([e["label"] for e in render(review)["ids.json"]], ["S1", "S2"])

    def test_badges_count_only_introduced_findings(self):
        review = example()
        review["findings"] = [finding(), finding(origin="pre-existing", blame="abc1234", severity="Minor")]
        self.assertEqual(verdict_line_fields(render(review)["summary.md"])[3:],
                         ["🟠", "1", "Serious", "·", "⚪", "1", "Pre-existing"])


class CommentShapeTest(unittest.TestCase):
    def test_comment_carries_every_field_label_in_order(self):
        body = render(example())["line_comments.json"][0]["body"]
        labels = ["**Why it matters**:", "**Suggested fix**:", "**Inverse risk**:", "**Class-sites**:"]
        self.assertEqual(sorted(labels, key=body.index), labels)

    def test_comment_header_has_no_round_label(self):
        self.assertEqual(render(example())["line_comments.json"][0]["body"].splitlines()[0], "🟠 **Serious** · Intent")

    def test_file_level_entry_carries_ids_and_body(self):
        review = example()
        review["findings"] = [finding(line=None)]
        entry = render(review)["file_level.json"][0]
        self.assertEqual((entry["finding_id"], entry["label"], entry["path"], entry["body"].startswith("🟠 **Serious**")),
                         ("3f2a9c1d7e", "S1", PATH, True))

    def test_pre_existing_comment_carries_marker_and_blame(self):
        review = example()
        review["findings"] = [finding(origin="pre-existing", blame="abc1234")]
        review.update(verdict="approve", senior_approval={"approved": True, "reason": "Only old code is affected."})
        body = render(review)["line_comments.json"][0]["body"]
        self.assertTrue(body.endswith("<!-- review-pr:origin=pre-existing -->") and "blame abc1234" in body)

    def test_pre_existing_rows_get_their_own_section(self):
        review = example()
        review["findings"] = [finding(origin="pre-existing", blame="abc1234")]
        summary = render(review)["summary.md"]
        self.assertTrue("### Findings\n\nNo findings." in summary and "### Pre-existing" in summary)


class BlockedPathTest(unittest.TestCase):
    def blocked(self, **extra):
        review = example()
        review.update({"findings": [], "blockers": [render_review.ENTRY_SHAPES["blockers"]], **extra})
        return review

    def test_open_blockers_replace_no_findings(self):
        summary = render(self.blocked())["summary.md"]
        self.assertIn(f"| `{PATH}:12` | reviewer-login | Postcode is still trimmed twice. |", summary)
        self.assertNotIn("No findings.", summary)

    def test_blocked_path_posts_no_threads(self):
        outputs = render(self.blocked(findings=[finding(origin="pre-existing", blame="abc1234")]))
        self.assertEqual((outputs["line_comments.json"], outputs["file_level.json"]), ([], []))

    def test_blocked_path_keeps_pre_existing_detail_in_the_body(self):
        summary = render(self.blocked(findings=[finding(origin="pre-existing", blame="abc1234")]))["summary.md"]
        self.assertTrue("### Additional findings" in summary and "Details in review comments" not in summary)


class MonolithicTest(unittest.TestCase):
    def test_monolithic_points_below_not_at_comments(self):
        body = render(example())["monolithic.md"]
        self.assertTrue(render_review.DETAILS_BELOW in body and "Details in review comments" not in body)

    def test_monolithic_holds_every_threaded_finding(self):
        self.assertIn("### Finding details\n\n**S1** `" + PATH + ":42`", render(example())["monolithic.md"])


class ResolvedLineTest(unittest.TestCase):
    def test_resolved_items_render_on_one_line(self):
        review = example()
        review["resolved"] = [render_review.ENTRY_SHAPES["resolved"]]
        self.assertIn("**Resolved since last review**: S2 (`address.ts:18` missing null check, round 1 commit `abc1234`) *(threads resolved)*",
                      render(review)["summary.md"])


def reply(**overrides):
    return {**render_review.ENTRY_SHAPES["replies"], **overrides}


def with_replies(*replies):
    review = example()
    review["replies"] = list(replies)
    return review


class ReplyTest(unittest.TestCase):
    def test_no_replies_renders_an_empty_list(self):
        self.assertEqual(render(example())["replies.json"], [])

    def test_accepted_reply_names_the_reason_and_ends_with_the_marker(self):
        body = render(with_replies(reply()))["replies.json"][0]["body"]
        self.assertEqual(body, "Agreed, so I dropped this finding. The caller at `address.ts:30` already rejects a blank country, "
                               "as the reply points out.\n\n<!-- review-pr:reply to=2145678903 kind=accepted -->")

    def test_correction_quotes_the_claim_and_cites_the_head(self):
        entry = render(with_replies(reply(kind="correction", reason=None, quote="The caller trims it first.",
                                          evidence="`address.ts:30` passes the raw cell.")))["replies.json"][0]
        self.assertEqual((entry["kind"], entry["body"].splitlines()[0], "This still holds at `0123456`:" in entry["body"]),
                         ("correction", "> The caller trims it first.", True))

    def test_needs_pointer_asks_for_something_checkable(self):
        body = render(with_replies(reply(kind="needs-pointer", reason=None)))["replies.json"][0]["body"]
        self.assertTrue(body.startswith("I'm keeping this finding open.") and body.endswith("kind=needs-pointer -->"))

    def test_entry_carries_thread_and_answered_comment(self):
        entry = render(with_replies(reply()))["replies.json"][0]
        self.assertEqual((entry["thread_id"], entry["answers_comment_id"]), ("PRRT_kwDO123abc", 2145678903))

    def test_no_replies_adds_no_answers_section(self):
        self.assertNotIn("### Answers to replies", render(example())["summary.md"])

    def test_summary_carries_every_answer_by_location(self):
        review = with_replies(reply(), reply(thread_id="PRRT_two", answers_comment_id=7, kind="correction", reason=None,
                                             location="address.ts:50", quote="The caller trims it first.",
                                             evidence="`address.ts:30` passes the raw cell."))
        summary = render(review)["summary.md"]
        self.assertTrue(summary.endswith(
            "### Answers to replies\n\n"
            "- `address.ts:42`: Agreed, finding dropped. The caller at `address.ts:30` already rejects a blank country, as the reply points out.\n"
            "- `address.ts:50`: On \"The caller trims it first.\": this still holds at `0123456`. `address.ts:30` passes the raw cell.\n\n"
            "<!-- review-pr:answered 7=correction 2145678903=accepted -->"))

    def test_prior_answers_carry_forward_without_new_replies(self):
        review = example()
        review["answered"] = [{"comment_id": 9, "kind": "accepted"}, {"comment_id": 3, "kind": "needs-pointer"}]
        summary = render(review)["summary.md"]
        self.assertEqual((summary.splitlines()[-1], "### Answers to replies" in summary),
                         ("<!-- review-pr:answered 3=needs-pointer 9=accepted -->", False))

    def test_no_answers_adds_no_marker(self):
        self.assertNotIn("review-pr:answered", render(example())["summary.md"])

    def test_reply_to_an_already_answered_comment_is_rejected(self):
        review = with_replies(reply())
        review["answered"] = [{"comment_id": 2145678903, "kind": "needs-pointer"}]
        self.assertIn("replies[0] answers comment 2145678903, which is already answered; drop the reply", render_review.validate(review))

    def test_bad_answered_entry_is_rejected(self):
        review = example()
        review["answered"] = [{"comment_id": "9", "kind": "thanks"}]
        problems = render_review.validate(review)
        self.assertEqual([p for p in problems if p.startswith("answered[0]")],
                         ["answered[0].comment_id must be the answered comment's databaseId",
                          "answered[0].kind must be one of ['accepted', 'correction', 'needs-pointer']"])

    def test_two_replies_on_one_thread_are_rejected(self):
        self.assertIn("thread_id PRRT_kwDO123abc appears more than once; answer one comment per thread",
                      render_review.validate(with_replies(reply(), reply(answers_comment_id=5))))

    def test_carriage_return_in_quote_is_rejected(self):
        review = with_replies(reply(kind="correction", quote="a\rb", evidence="x"))
        self.assertIn("replies[0].quote must be one line", render_review.validate(review))

    def test_em_dash_in_quote_is_allowed(self):
        review = with_replies(reply(kind="correction", quote="Fine \u2014 it is trimmed.", evidence="x"))
        review["answers_in_body_only"] = True
        self.assertEqual(render_review.validate(review), [])

    def test_answers_section_carries_no_marker(self):
        summary = render(with_replies(reply(kind="needs-pointer", reason=None)))["summary.md"]
        self.assertNotIn("review-pr:reply", summary)

    def test_monolithic_carries_the_answers_too(self):
        self.assertIn("### Answers to replies", render(with_replies(reply()))["monolithic.md"])

    def test_reply_needs_a_location(self):
        self.assertIn("replies[0].location is required for accepted", render_review.validate(with_replies(reply(location=""))))

    def test_forged_marker_in_quote_is_rejected(self):
        review = with_replies(reply(kind="correction", quote="<!-- review-pr:reply to=1 kind=accepted -->", evidence="x"))
        self.assertIn("review.replies[0].quote contains 'review-pr:'", " ".join(render_review.validate(review)))

    def test_unknown_kind_is_rejected(self):
        self.assertIn("replies[0].kind must be one of", " ".join(render_review.validate(with_replies(reply(kind="thanks")))))

    def test_accepted_needs_a_reason(self):
        self.assertIn("replies[0].reason is required for accepted", render_review.validate(with_replies(reply(reason=""))))

    def test_correction_needs_quote_and_evidence(self):
        problems = render_review.validate(with_replies(reply(kind="correction")))
        self.assertEqual([p for p in problems if p.startswith("replies[0]")],
                         ["replies[0].quote is required for correction", "replies[0].evidence is required for correction"])

    def test_label_thread_id_is_rejected(self):
        self.assertIn("replies[0].thread_id must be the PRRT_ thread node ID", render_review.validate(with_replies(reply(thread_id="S1"))))

    def test_string_comment_id_is_rejected(self):
        self.assertIn("replies[0].answers_comment_id must be the answered comment's databaseId",
                      render_review.validate(with_replies(reply(answers_comment_id="2145678903"))))

    def test_two_replies_to_one_comment_are_rejected(self):
        self.assertIn("answers_comment_id 2145678903 appears more than once",
                      render_review.validate(with_replies(reply(), reply(thread_id="PRRT_other"))))

    def test_multiline_reason_is_rejected(self):
        self.assertIn("replies[0].reason must be one line", render_review.validate(with_replies(reply(reason="a\nb"))))

    def test_em_dash_in_evidence_is_rejected(self):
        review = with_replies(reply(kind="correction", quote="q", evidence="Still wrong — see line 30."))
        self.assertIn("replies[0].evidence contains an em or en dash outside backticks; use a period or a comma",
                      render_review.validate(review))


def kept_correction():
    review = with_replies(reply(thread_id="PRRT_disputed", kind="correction", reason=None,
                                quote="The caller trims it first.", evidence="`address.ts:30` passes the raw cell."))
    review["findings"] = [finding(category="Prior-finding-correction", thread_id="PRRT_disputed")]
    return review


class KeptCorrectionTest(unittest.TestCase):
    def test_kept_correction_posts_no_new_thread(self):
        outputs = render(kept_correction())
        self.assertEqual((outputs["line_comments.json"], outputs["file_level.json"]), ([], []))

    def test_ids_record_the_kept_thread(self):
        self.assertEqual(render(kept_correction())["ids.json"],
                         [{"finding_id": "3f2a9c1d7e", "label": "S1", "tier": "existing", "file": PATH, "line": 42,
                           "thread_id": "PRRT_disputed"}])

    def test_kept_correction_stays_in_the_findings_table(self):
        self.assertIn(f"| S1 | 🟠 | `{PATH}:42` |", render(kept_correction())["summary.md"])

    def test_kept_correction_is_not_reported_as_a_demotion(self):
        self.assertEqual(render_review.demotions(render(kept_correction())), [])

    def test_monolithic_holds_the_kept_correction_detail(self):
        self.assertIn("**Why it matters**", render(kept_correction())["monolithic.md"])

    def test_kept_thread_needs_a_correction_reply(self):
        review = kept_correction()
        review["replies"] = []
        self.assertIn("thread PRRT_disputed is kept by a finding but has no correction reply", render_review.validate(review))

    def test_correction_reply_without_its_finding_is_rejected(self):
        review = kept_correction()
        del review["findings"][0]["thread_id"]
        self.assertIn("correction reply on thread PRRT_disputed needs the finding it corrects to keep that thread",
                      render_review.validate(review))

    def test_two_findings_keeping_one_thread_are_rejected(self):
        review = kept_correction()
        review["findings"].append(finding(finding_id="aaaaaaaaaa", thread_id="PRRT_disputed"))
        self.assertIn("thread PRRT_disputed is kept by more than one finding", render_review.validate(review))

    def test_body_only_answers_keep_no_thread(self):
        review = kept_correction()
        review["answers_in_body_only"] = True
        self.assertIn("answers_in_body_only posts no thread reply, so no finding may keep a disputed thread",
                      render_review.validate(review))

    def test_body_only_correction_validates_without_a_kept_finding(self):
        review = kept_correction()
        del review["findings"][0]["thread_id"]
        review["answers_in_body_only"] = True
        self.assertEqual(render_review.validate(review), [])

    def test_correction_reply_carries_the_current_finding(self):
        body = render(kept_correction())["replies.json"][0]["body"]
        self.assertTrue("**Why it matters**" in body and "**Inverse risk**" in body and body.endswith("kind=correction -->"))

    def test_kept_correction_validates(self):
        self.assertEqual(render_review.validate(kept_correction()), [])

    def test_blocked_path_keeps_the_correction_in_the_body(self):
        review = kept_correction()
        review.update(blockers=[render_review.ENTRY_SHAPES["blockers"]],
                      senior_approval={"approved": False, "reason": "An open thread still blocks it."})
        review["findings"][0].update(origin="pre-existing", blame="abc1234")
        outputs = render(review)
        self.assertEqual((outputs["ids.json"][0]["tier"], "### Additional findings" in outputs["summary.md"]), ("body", True))

    def test_blocked_path_correction_reply_still_carries_the_finding(self):
        review = kept_correction()
        review.update(blockers=[render_review.ENTRY_SHAPES["blockers"]],
                      senior_approval={"approved": False, "reason": "An open thread still blocks it."})
        self.assertIn("**Why it matters**", render(review)["replies.json"][0]["body"])

    def test_label_shaped_kept_thread_is_rejected(self):
        review = kept_correction()
        review["findings"][0]["thread_id"] = "S1"
        self.assertIn("findings[0].thread_id must be the PRRT_ node ID of the disputed thread it keeps",
                      render_review.validate(review))


class ValidationTest(unittest.TestCase):
    def test_example_validates(self):
        self.assertEqual(render_review.validate(render_review.EXAMPLE), [])

    def test_printed_example_must_drop_entry_shapes(self):
        out = io.StringIO()
        with redirect_stdout(out):
            render_review.main(["--example"])
        self.assertIn("remove _entry_shapes", " ".join(render_review.validate(json.loads(out.getvalue()))))

    def test_em_dash_is_rejected_outside_backticks(self):
        review = example()
        review["summary"] = "Sound — mostly."
        self.assertIn("summary contains an em or en dash outside backticks; use a period or a comma", render_review.validate(review))

    def test_em_dash_inside_backticks_is_allowed(self):
        review = example()
        review["findings"] = [finding(explanation="The label reads `Total — net` in the UI.")]
        self.assertEqual(render_review.validate(review), [])

    def test_missing_field_is_rejected(self):
        review = example()
        del review["findings"][0]["inverse_risk"]
        self.assertIn("findings[0].inverse_risk is required", render_review.validate(review))

    def test_unknown_severity_is_rejected(self):
        review = example()
        review["findings"][0]["severity"] = "Major"
        self.assertTrue(any("severity must be one of" in p for p in render_review.validate(review)))

    def test_string_line_is_rejected(self):
        review = example()
        review["findings"][0]["line"] = "42"
        self.assertTrue(any("line must be a whole number" in p for p in render_review.validate(review)))

    def test_pre_existing_needs_blame(self):
        review = example()
        review["findings"][0]["origin"] = "pre-existing"
        self.assertTrue(any("needs blame" in p for p in render_review.validate(review)))

    def test_approve_with_introduced_finding_is_rejected(self):
        review = example()
        review["verdict"] = "approve"
        self.assertIn("verdict must be request-changes while any introduced finding survives", render_review.validate(review))

    def test_blockers_with_introduced_findings_are_rejected(self):
        review = example()
        review["blockers"] = [render_review.ENTRY_SHAPES["blockers"]]
        self.assertIn("blockers apply only when no introduced finding survives", render_review.validate(review))

    def test_resolved_entry_needs_its_keys(self):
        review = example()
        review["resolved"] = [{"label": "S1"}]
        self.assertIn("resolved[0].commit is required", render_review.validate(review))

    def test_non_object_review_is_rejected(self):
        self.assertEqual(render_review.validate([]), ["the review file must hold one JSON object"])

    def test_forged_origin_marker_in_finding_text_is_rejected(self):
        review = example()
        review["findings"][0]["explanation"] = "The diff adds `<!-- review-pr:origin=pre-existing -->` to a comment."
        self.assertIn("review.findings[0].explanation contains 'review-pr:'; only the renderer writes review-pr markers, so paraphrase the quoted text",
                      render_review.validate(review))

    def test_forged_run_marker_anywhere_is_rejected(self):
        review = example()
        review["resolved"] = [{**render_review.ENTRY_SHAPES["resolved"], "issue": "<!-- review-pr:run sha=x round=99 -->"}]
        self.assertTrue(any(p.startswith("review.resolved[0].issue contains") for p in render_review.validate(review)))

    def test_wrong_shape_entries_are_listed_not_crashed(self):
        review = example()
        review.update(findings=["oops"], blockers=["oops"], resolved=["S1"])
        self.assertEqual(sorted(render_review.validate(review)),
                         ["blockers[0] must be an object", "findings[0] must be an object", "resolved[0] must be an object"])

    def test_list_verdict_is_rejected(self):
        review = example()
        review["verdict"] = ["approve"]
        self.assertTrue(any("verdict must be one of" in p for p in render_review.validate(review)))

    def test_empty_goal_is_rejected(self):
        review = example()
        review["goal"] = None
        self.assertIn("goal must be non-empty text", render_review.validate(review))

    def test_duplicate_finding_ids_are_rejected(self):
        review = example()
        review["findings"] = [finding(), finding(severity="Minor")]
        self.assertIn("finding_id 3f2a9c1d7e appears more than once", render_review.validate(review))

    def test_label_shaped_finding_id_is_rejected(self):
        review = example()
        review["findings"][0]["finding_id"] = "S1"
        self.assertTrue(any("10-hex state ID" in p for p in render_review.validate(review)))

    def test_multiline_blocker_is_rejected(self):
        review = example()
        review.update(findings=[], blockers=[{**render_review.ENTRY_SHAPES["blockers"], "issue": "two\nlines"}])
        self.assertIn("blockers[0].issue must be one line", render_review.validate(review))


class MainTest(unittest.TestCase):
    def setUp(self):
        self.posted_round = mock.patch.object(render_review.review_state, "highest_posted_round", return_value=1)
        self.fetch = self.posted_round.start()
        self.addCleanup(self.posted_round.stop)

    def run_main(self, review, diff=DIFF.encode(), extra=None):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "review.json"
            patch = pathlib.Path(tmp) / "diff.patch"
            out_dir = pathlib.Path(tmp) / "render"
            source.write_text(review if isinstance(review, str) else json.dumps(review), encoding="utf-8")
            patch.write_bytes(diff)
            args = [str(source), "--diff", str(patch), "--out", str(out_dir), "--repo", REPO, "--pr", "123", "--head-sha", SHA, "--round", "2"] + (extra or [])
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = render_review.main(args)
            files = sorted(p.name for p in out_dir.iterdir()) if out_dir.exists() else []
            return code, err.getvalue(), files

    def test_valid_review_writes_every_file(self):
        self.assertEqual(self.run_main(example())[0::2],
                         (0, ["file_level.json", "ids.json", "line_comments.json", "monolithic.md", "replies.json", "summary.md"]))

    def test_invalid_review_writes_nothing(self):
        review = example()
        review["summary"] = "Sound — mostly."
        code, _, files = self.run_main(review)
        self.assertEqual((code, files), (2, []))

    def test_bad_json_is_a_listed_problem(self):
        code, err, _ = self.run_main("{not json")
        self.assertEqual((code, "cannot read" in err), (2, True))

    def test_non_utf8_diff_still_renders(self):
        self.assertEqual(self.run_main(example(), diff=DIFF.encode() + b"+Stra\xdfe\n")[0], 0)

    def test_short_sha_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "r.json"
            source.write_text(json.dumps(example()))
            patch = pathlib.Path(tmp) / "d.patch"
            patch.write_text(DIFF)
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = render_review.main([str(source), "--diff", str(patch), "--out", str(pathlib.Path(tmp) / "o"),
                                           "--repo", REPO, "--pr", "1", "--head-sha", "abc123", "--round", "1"])
        self.assertEqual((code, "full 40-character" in err.getvalue()), (2, True))

    def test_missing_out_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "r.json"
            source.write_text(json.dumps(example()))
            patch = pathlib.Path(tmp) / "d.patch"
            patch.write_text(DIFF)
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = render_review.main([str(source), "--diff", str(patch), "--out", str(pathlib.Path(tmp) / "missing" / "o"),
                                           "--repo", REPO, "--pr", "1", "--head-sha", SHA, "--round", "1"])
        self.assertEqual((code, "does not exist" in err.getvalue()), (2, True))

    def test_bodies_have_no_trailing_newline(self):
        outputs = render(example())
        self.assertFalse(outputs["summary.md"].endswith("\n") or outputs["monolithic.md"].endswith("\n"))

    def test_existing_out_dir_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "r.json"
            source.write_text(json.dumps(example()))
            patch = pathlib.Path(tmp) / "d.patch"
            patch.write_text(DIFF)
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = render_review.main([str(source), "--diff", str(patch), "--out", tmp,
                                           "--repo", REPO, "--pr", "1", "--head-sha", SHA, "--round", "1"])
        self.assertEqual((code, "already exists" in err.getvalue()), (2, True))

    def test_demotion_is_reported(self):
        review = example()
        review["findings"] = [finding(line=7)]
        code, err, _ = self.run_main(review)
        self.assertEqual((code, f"S1 {PATH}:7 is not on the diff's post-image side; posting it as file" in err), (0, True))

    def test_oversized_comment_is_rejected(self):
        review = example()
        review["findings"] = [finding(explanation="x" * (render_review.GITHUB_BODY_LIMIT + 1))]
        code, err, files = self.run_main(review)
        self.assertEqual((code, "line_comments.json[0] is over" in err, files), (2, True, []))

    def test_round_below_the_posted_round_is_rejected(self):
        self.fetch.return_value = 13
        code, err, files = self.run_main(example())
        self.assertEqual((code, "--round 2 is not above the rounds already posted" in err, files), (2, True, []))

    def test_round_equal_to_the_posted_round_is_rejected(self):
        self.fetch.return_value = 2
        self.assertEqual(self.run_main(example())[0::2], (2, []))

    def test_supplemental_review_keeps_the_posted_round(self):
        self.fetch.return_value = 2
        self.assertEqual(self.run_main(example(), extra=["--supplemental"])[0], 0)

    def test_supplemental_review_with_another_round_is_rejected(self):
        self.fetch.return_value = 1
        code, err, _ = self.run_main(example(), extra=["--supplemental"])
        self.assertEqual((code, "keeps the round of the review it completes" in err), (2, True))

    def test_round_check_reads_the_named_pr(self):
        self.run_main(example())
        self.fetch.assert_called_once_with(REPO, 123)

    def test_unreachable_github_blocks_the_render(self):
        self.fetch.side_effect = render_review.review_state.StateError("gh pr view 123 --repo acme/shop failed: offline")
        code, err, files = self.run_main(example())
        self.assertEqual((code, "cannot check --round against the PR" in err, files), (2, True, []))


if __name__ == "__main__":
    unittest.main()
