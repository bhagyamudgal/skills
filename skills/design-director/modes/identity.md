# Mode — Brand Identity System

- **Slots**:
  1. Industry / category
  2. Brand name
  3. Audience (one sentence)
  4. Values (3 words)
  5. Vibe (modern / editorial / playful / luxe / technical / warm / other)
- **Stage**: treat the complete system as a proposal until the user explicitly approves it. On approval, emit an **Approved identity selection record** that `finalize` can consume.
- **Output**: complete system with these sections, in order:
  - **Positioning line** (one sentence — what the brand stands for, who it's for)
  - **Logo direction** (1-2 paragraphs — wordmark vs symbol vs lockup, why)
  - **Lockup system** (mark, wordmark, horizontal and stacked lockups; state element order, clear space, and minimum sizes)
  - **Color palette logic** (separate light and dark semantic token maps with hex and role; choose each theme rather than inverting one)
  - **Theme contrast proof** (classify each use, measure mark, text, and accent pairs on their actual light and dark backgrounds, then apply the criteria in the main skill)
  - **Typography** (display + body pairing, hierarchy in 3 lines)
  - **Visual elements** (motifs, patterns, photography style, illustration style — pick 2-3 that reinforce the brand)
  - **Overall style** (3-5 adjectives, the traits borrowed from 2-3 reference brands, and 2-3 deliberate divergence moves)
  - **Sample applications** (1-line each: business card, app icon, social avatar, packaging — describe how the system shows up there)
  - **Approved identity selection record** (approval stage only: approved brand name; editable source or deterministic construction spec with coordinate system, primitives or paths, and proportions; mark, wordmark, and approved lockups; light and dark colors; type provenance; clear space; minimum sizes; divergence moves; collision-screen status; and the legal-clearance caveat)
- **File save**: yes
- **Next step**: → re-run `design-director` in `finalize` mode after the approved identity selection record exists
