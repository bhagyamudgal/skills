# False-positive rules table (Phase 3 step 4.6)

Loaded by main at Phase 3 step 4.6, whenever at least one finding survives step 4.5. SKILL.md keeps the iterator contract — `id` / `trigger` or `applies_to` / optional `exempt_lenses` / `evidence_check` / `action`, applied in order, every fire logged to Filtered Out with the rule `id`. This file holds the rules that iterator runs, and is the single source of truth for false-positive filtering: adding a new false-positive class is a one-row edit here.

The table is consulted per finding, not read linearly. Rules carry one of two selectors, and may carry an off-switch:

- `trigger` — a regex matched against the finding's `Issue` / `Why` text. Run the `evidence_check` only when the regex hits.
- `applies_to` — no text match. The rule runs on every finding in the class it names, and states what the reviewer must have done before the finding may be emitted at all.
- `exempt_lenses` — optional, and not a selector: a list of lens ids that switches the rule OFF for a finding. Evaluated BEFORE that rule's `trigger` or `applies_to`. When the finding's `Lens:` line names any listed lens, the rule returns `inapplicable` for that finding — no regex is matched, no `evidence_check` runs, no action applies — and the skip is logged to Filtered Out as `<rule-id> inapplicable — exempt lens <Lx>`, so which rule did NOT run is as auditable as which one fired. A rule carrying no `exempt_lenses` key runs on every finding. A `Lens:` line of the form `none — <check>` names no lens and is never exempt.

`applies_to` rules are listed first, and run first: they correct the anchor and the suggested fix that the later rules' `evidence_check` bodies read, so running them last would mean the text rules verified against a line the emitted finding no longer points at.

At most one severity change per finding per pass. When several rules fire, apply the strongest action once — `drop` beats `strip-fix` beats a downgrade — and log every rule `id` that fired. Two independent soft grounds must not compound into a two-step downgrade.

**Lens exemptions.** `intent-alignment` fires only on findings whose own text claims a change is undeclared — unscoped, out of scope, not in the description, silently changes behavior. For a claim of that shape, overlap with the PR's stated intent refutes it: the change was declared after all, the finding is noise, and killing it is the rule's whole purpose, which the exemption leaves standing. The exempt lenses share that vocabulary without making that claim. Both ask about a scope belonging to the **code** rather than to the PR — who else a changed guard now admits, what a changed validator now accepts — and neither can state its finding without the words the regex matches. An author who intended to widen a guard has said nothing about whether they intended to admit everyone the widening admits; the admitted set is precisely the set nobody enumerated, which is why the lens exists at all. For these findings, overlap with intent is structurally guaranteed and carries no information about whether the code is right, so measuring it decides nothing and costs a tier — and at Minor, the finding.

**Exempt only a finding that does the exempt lens's work.** It must state what that lens asks for: for an authorization or validation scope, the set admitted or accepted before the change and after it, or a count or name of what is newly reachable. A finding whose entire content is that a guard changed and the description does not mention it is making the scope-creep claim after all, carries no delta, and stays subject to the rule. A `Lens:` line is not a way to buy immunity for one.

**An exemption is not immunity, and does not suspend the one-change cap.** It removes a single rule from one finding's candidate set; every other rule still runs on it. A widening finding asserting that most stored records are now reachable still owes `publish-the-command-or-do-not-claim` a query it can paste and run, and still loses that claim and a tier without one. Because only one severity change applies per pass, exempting `intent-alignment` changes the outcome only where its action would have been the strongest to fire: an exemption can never raise a severity, and never rescues a finding that another rule drops on its own grounds.

---

```yaml
rules:
  - id: re-derive-the-anchor
    applies_to: |
      Every finding carrying a File: <path>:<line>, before any other rule reads that line.
    evidence_check: |
      Require an anchor_text — the exact source line the finding is about, as the reviewer read it.
      If the finding carries none, adopt the line the citation currently points at in the post-image,
      and only when that line contains the symbol named in Issue; otherwise treat as no match.
      Re-derive the line by searching the POST-image for anchor_text:
        - stashed diff, new side, first
        - gh api repos/<owner>/<repo>/contents/<path>?ref=<head-sha> when the file is not fully stashed
      One match     → rewrite File: to that match's post-image line number.
      Many matches  → take the occurrence inside the finding's Enclosing-symbol; still ambiguous → demote to file-level.
      No match      → DROP.
      Never carry a line number over from the pre-image / old side, an earlier round's state file,
      a prior review comment, another reviewer's output, or the position where it was first noticed.
      A rebase moves lines and leaves the file right; the anchor must be recomputed, not inherited.
    action: re-anchor-or-drop
    log_reason: "re-derive-the-anchor — <path>:<old> -> <new>, or dropped when anchor_text is absent from the post-image at <head-sha>"

  - id: open-the-callee
    applies_to: |
      Every finding carrying a Suggested fix:, after step 4.56 has derived its Inverse risk.
    evidence_check: |
      List every symbol the suggested fix calls, awaits, constructs, spreads, or reads a field from.
      Exclude language built-ins and symbols whose definition sits in a diff hunk already in context.
      For each remaining symbol, the reviewer must have OPENED its definition — all four hold:
        1. read at <head-sha> via Read or gh api contents — not from memory, not from a grep hit, not from a call site
        2. the read spanned the signature AND the body, not the first line alone
        3. the source is an implementation file, not a declaration (see declaration-is-not-implementation)
        4. the reviewer can state from that read: parameter list and order, return type, whether it is
           async, whether it can return null/undefined, whether it throws
      Any symbol failing any of the four is NOT opened. Then:
        finding stands without the fix → keep severity, replace the fix with
          "no verified fix — <symbol> not read", attach note
        finding IS the fix (Issue asserts only that the code should call <symbol>) → DROP
      /fix-pr-review applies these verbatim; a fix written against a guessed signature ships as a defect.
    action: strip-fix
    note: "Note: fix withdrawn — <symbol> was never opened, so its signature, nullability and throwing behaviour are unverified."
    log_reason: "open-the-callee — <symbol> not read at <head-sha>; Suggested fix stripped"

  - id: wrapped-coercion
    trigger: |
      (?i)\.toFixed\(|\.toString\(|\.toLocaleString\(|String\(
    evidence_check: |
      Verify cited line in stashed diff. Drop if the call is structurally enclosed by
      Number(...) / parseFloat(...) / parseInt(...) / unary +(...) on the SAME line.
      Anchored patterns:
        =\s*(Number|parseFloat|parseInt|\+)\s*\(\s*<call>
        :\s*(Number|parseFloat|parseInt|\+)\s*\(\s*<call>
        return\s+(Number|parseFloat|parseInt|\+)\s*\(\s*<call>
      Do NOT match across lines, do NOT match sibling args (e.g., foo(bar.toFixed(1), Number(y))).
    action: drop
    log_reason: "wrapped-coercion FP — call wrapped in Number(...) on same line"

  - id: intent-alignment
    exempt_lenses: [L2, L18]   # see "Lens exemptions" above
    trigger: |
      (?i)unscoped|semantic (drift|change)|not mentioned|not in (the )?description|scope creep|out of scope|outside (the )?stated goal|beyond PR scope|undeclared change|silently changes behavior
    evidence_check: |
      Tokenize PR intent (title + linked-issue title + first 200 chars body):
        - Split on whitespace, [_\-\.\/], camelCase boundaries
        - Lowercase, drop tokens <= 2 chars, drop stop words (add fix update refactor use new the a of in for to and or is be)
      Tokenize finding's claim (cited File: + symbol from Issue) same way.
      Precondition: |finding_tokens| >= 3 AND |intent_tokens| >= 3. If either < 3, INAPPLICABLE.
      Compute overlap = |intent ∩ finding| / |finding|.
      If overlap >= 0.5 → return evidence_present (downgrade).
      If overlap = 1.0 AND severity = Minor → return evidence_present_drop (drop).
    action: downgrade-1-and-note   # plus drop-if-Minor for overlap=1.0 case
    note: "Note: this change aligns with PR intent (\"<keywords>\"). Re-verify before merging — may be intentional."
    log_reason: "intent-alignment downgrade — <N>/<M> finding tokens match PR intent"

  - id: library-behavior-citation
    trigger: |
      (?i)<Library> (does|returns|is)|float precision|IEEE 754|floating-point|fragile|unsafe edge case
    evidence_check: |
      Check if Why or Fix contains a citation:
        - node_modules/<lib>/ path matching the library named in Issue
        - URL on official docs (github.com/<org>/<lib>, <lib>.dev, docs.<lib>.io) or spec/RFC
        - Reproducible code snippet with concrete input/output values
        - Linked repo issue or failing test case
      If NO citation found:
        Critical → downgrade to Serious + note (evidence_present_partial)
        Serious  → downgrade to Moderate + note
        Moderate → DROP
        Minor    → DROP
    action: severity-conditional   # see severity ladder above
    note: "Note: unverified library-behavior claim — empirical check required before acting."
    log_reason: "library-claim — <severity> with no citation"

  - id: default-fallback
    trigger: |
      (?i)\b(dropped|stripped|lost in|never propagated|not (propagated|passed|forwarded|carried))\b|falls? back to|fallback to
    evidence_check: |
      Extract claimed-dropped field name (backtick-quoted ID, or first camelCase/snake_case token near matched verb).
      Search stashed diff first; fetch via gh api contents only if needed (cache per critic pass).
      Look for ANY of:
        - ALL_CAPS constant whose name contains a camelCase segment of the field
          (e.g., field currencyCode → match DEFAULT_CURRENCY_CODE, FALLBACK_CURRENCY)
        - camelCase default: \b(default|fallback|initial)[A-Z]\w*\b ending with field segment
        - config-object default: config\.(default|fallback)\w*, defaults\.\w+, <obj>\.fallback\w*
        - Coalesce on receiving side: ??\s*<const>, ||\s*<const>
        - Comment within 10 lines: (?i)defaults? to|always|intentionally|by design|only\s+\w+\s+(makes sense|is supported|applies)
      If a "by design" / "only X makes sense" / "always X" comment is found → evidence_present_drop (DROP).
      Else if any named-default signal → evidence_present (downgrade).
    action: downgrade-1-and-note   # plus DROP if "by design" comment found
    note: "Note: a named default (<CONST>) handles the absent value — likely intentional design, not a propagation bug."
    log_reason: "default-fallback — found <CONST>"

  - id: declaration-is-not-implementation
    trigger: |
      (?i)\.d\.ts|\bdeclare\s+(module|function|const|class|namespace)\b|\binterface\b|\babstract\b|z\.infer|\btype\s+\w+\s*=|the (type|signature|schema|interface) (says|declares|shows|guarantees)|@(param|returns)\b
    evidence_check: |
      Applies when the finding asserts RUNTIME behaviour — returns, throws, never null, always defined,
      validates, sanitizes, retries, mutates, awaits — and EVERY source it cites is a declaration:
      a .d.ts, a declare block, an interface, a type alias, an abstract method signature, an
      ORM/Zod-inferred model type, or a @param/@returns doc comment.
      Claims about the type itself — assignability, a widened union, a missing discriminant, an
      unsound cast — are INAPPLICABLE: the declaration IS the subject there.
      Declaration-only evidence for a behaviour claim leaves it unproven; a declaration states a
      contract, and the defect being reviewed is precisely a divergence between contract and code.
        Critical → downgrade to Serious + note
        Serious  → downgrade to Moderate + note
        Moderate → DROP
        Minor    → DROP
      Evidence that clears the rule: the implementing body at <head-sha>, a test exercising the
      behaviour, or a runtime log/trace line showing it.
    action: severity-conditional   # see severity ladder above
    note: "Note: claim rests on a type declaration, not an implementation — read <symbol>'s body before acting."
    log_reason: "declaration-is-not-implementation — <severity> proven only from <decl-source>"

  - id: publish-the-command-or-do-not-claim
    trigger: |
      (?i)\b(always|never|rarely|usually|mostly|typically|almost never)\s+(null|undefined|empty|set|populated|happens|occurs|fires|used)|\ball (rows|records|accounts|tenants|users)\b|\bmost (rows|records|accounts|tenants|users|requests)\b|\bonly a (few|handful)\b|\bno (rows|records|users|accounts) (have|has|are)\b|\b\d+(\.\d+)?\s*%|\b(row|record|request) counts?\b|\bin (production|prod|the wild)\b|\bthis (never|always) happens\b|\baffects? (only|just)\b
    evidence_check: |
      Precondition: the claim quantifies over stored data or observed traffic OUTSIDE this diff —
      rows, records, documents, accounts, tenants, requests, jobs, events, log lines.
      A claim quantifying over CODE is INAPPLICABLE — "this branch is never reached", "the guard
      always returns early", "every caller passes a string", "the loop always runs once" are settled
      by reading the code, and the File: anchor already tells a reader where to read.
      Require a command in Why / Evidence / Fix that a reader can paste and run UNMODIFIED:
        - psql / docker exec ... psql carrying a full SELECT with real table and column names
        - a script or CLI invocation with every argument bound
        - gh api ... --jq, or a log/analytics query including its time window
        - grep -rE '<pattern>' <path> when the claim is about occurrences in the repo
      Not runnable: placeholders (<table>, YOUR_DB, ...), an English description of a query, a bare
      table name, a result with no command, a command with no result. The command must be paired
      with the number it returned.
      No such command:
        Strike every distribution sentence from Issue and Why. Do NOT soften it to "may be",
        "likely", "in many cases" — an unrunnable claim is not a weaker claim, it is no claim.
        Then:
          finding still names a concrete defect at its cited line → keep, severity - 1, attach note
          finding's existence or severity rested on the volume    → DROP at any severity
    action: severity-conditional   # strike the claim first, then keep-minus-one or drop
    note: "Note: an unquantified data claim was removed from this finding — re-state it only with the query and the number it returned."
    log_reason: "publish-the-command — distribution claim with no re-runnable command"
```
