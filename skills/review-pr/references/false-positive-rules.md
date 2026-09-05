# False-positive rules table (Phase 3 step 4.6)

Loaded by main at Phase 3 step 4.6, whenever at least one finding survives step 4.5. SKILL.md keeps the iterator contract, `id` / `trigger` / `evidence_check` / `action`, applied in order, every fire logged to Filtered Out with the rule `id`. This file holds the rules that iterator runs, and is the single source of truth for false-positive filtering: adding a new false-positive class is a one-row edit here.

The table is consulted per finding, not read linearly. Match a finding's `Issue` / `Why` text against each `trigger` in order; run the `evidence_check` only when the trigger hits.

---

```yaml
rules:
  - id: wrapped-coercion
    trigger: |
      (?i)\.toFixed\(|\.toString\(|\.toLocaleString\(|String\(
    evidence_check: |
      Verify cited line in stashed diff. Drop if the call is structurally enclosed by
      Number(...) / parseFloat(...) / unary +(...) on the SAME line.
      parseInt(...) counts ONLY for a verified-integer field
      (DB integer/bigint, Zod z.number().int() per
      <SKILL_DIR>/references/q5-type-coercion.md) whose source is verified
      integer-formatted and within Number.MAX_SAFE_INTEGER, or where explicit
      truncation intent is documented at the write site.
      Anchored patterns:
        =\s*(Number|parseFloat|parseInt|\+)\s*\(\s*<call>
        :\s*(Number|parseFloat|parseInt|\+)\s*\(\s*<call>
        return\s+(Number|parseFloat|parseInt|\+)\s*\(\s*<call>
      Do NOT match across lines, do NOT match sibling args (e.g., foo(bar.toFixed(1), Number(y))).
    action: drop
    log_reason: "wrapped-coercion FP: call wrapped in Number(...) on same line"

  - id: intent-alignment
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
    note: "Note: this change aligns with PR intent (\"<keywords>\"). Re-verify before merging. It may be intentional."
    log_reason: "intent-alignment downgrade: <N>/<M> finding tokens match PR intent"

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
    note: "Note: unverified library-behavior claim. Empirical check required before acting."
    log_reason: "library-claim: <severity> with no citation"

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
    note: "Note: a named default (<CONST>) handles the absent value. Likely intentional design, not a propagation bug."
    log_reason: "default-fallback: found <CONST>"
```
