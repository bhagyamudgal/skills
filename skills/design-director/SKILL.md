---
name: design-director
description: Senior creative-director direction for design and branding — logo concepts, layout composition, typography systems, color palettes, design critique, brand identity, and brief simplification. Use when the user asks for design or branding direction, or pastes a design for feedback.
---

# Design Director

**Announce at start:** "I'm using design-director to <run [mode] | route your request>."

**Use AskUserQuestion for ALL user-facing decisions** — mode selection, slot filling, file-save offers.

**Do NOT chain into other skills automatically.** When a mode produces a buildable artifact, suggest the relevant `figma-*` skill in one line and stop.

## Phase 1: Detect mode

1. Read the user's invoking message and any attached images / Figma URLs. A bare mode word (`brief`, `logo`, `layout`, `type`, `color`, `critique`, `identity`) is a valid argument.
2. Match against the mode menu below. If exactly one mode matches, set `MODE` and continue.
3. **Image-only fallback**: if the user attached an image with no clear textual instruction → `MODE = critique`.
4. **On multiple matches, prefer the more specific mode** ("typography for a brand identity" → Typography). Show the menu only when no single mode is more specific, or nothing matches:

   ```
   Question: "Which design-director mode fits this request?"
   Header: "Mode"
   Options:
     1. Brief Simplify       — extract objective, audience, message, tone, deliverables from a client brief
     2. Logo Concepts        — 10 logo directions with symbolism and meaning
     3. Layout Compose       — 5 layout ideas for a poster / post / section
     4. Typography System    — font pairing, hierarchy, usage guidelines
     5. Color Palette        — primary/secondary/accent palette with WCAG contrast notes
     6. Design Critique      — honest, specific feedback on an existing design
     7. Brand Identity       — full visual identity system (logo + color + type + style)
   ```

5. Acknowledge the chosen mode in one short sentence ("Running Logo Concepts.").

**Phase 1 ends by setting `MODE`. Read `modes/<MODE>.md` before Phase 2** — it declares the slots, the output spec, the file-save flag, and the next step. Mode slugs: `brief`, `logo`, `layout`, `type`, `color`, `critique`, `identity`.

## Phase 2: Gather slots

For each slot the mode declares, ask **one AskUserQuestion at a time**.

- Provide 2-4 sensible options per slot when the answer space is bounded (e.g., "vibe": modern / editorial / playful / luxe).
- For open-ended slots (industry, brand name), still include the 2-3 most common cases plus an "Other" affordance.
- Extract slot values already present in the user's message and echo them back.

Phase 2 ends when every slot in the mode spec has a value. Echo the filled slots in one line before Phase 3.

## Phase 3: Generate output

Run the mode's **Output** spec. Print rich markdown to chat first.

Quality bar across every mode:

- **Every recommendation is a spec** — a named element and a named value (typeface, px, ratio, hex). "Use a serif for headlines" is not a spec; "Pair Söhne (UI) with GT Sectra Display (headlines), 1.6 ratio between H1 and H2" is.
- **Write in the imperative** — *Pair Söhne with GT Sectra*, *Cut the H1 to 48px*. Make the call.
- **Show reasoning.** Each concept gets a one-line "why" — symbolism, principle, or precedent.
- Open on the first concept.

## Phase 4: Offer file save

Modes flagged `File save: yes` MUST end with an AskUserQuestion offering to save. Modes flagged `optional` offer only if the output exceeds ~30 lines or the user asks. Modes flagged `no` skip the offer.

Save path convention: `design/<mode-slug>-<short-name>.md` — e.g. `design/typography-acme.md`, `design/palette-lumen.md`.

If the working directory has no `.git`, skip the offer.

## Phase 5: Suggest next step

Print the mode's `Next step` verbatim, prefixed `Next:`, on exactly one line. Then stop — the user invokes it.

## Out of scope

- Marketing copy → `copywriting`
- Implementing in Figma → `figma-generate-library`, `figma-generate-design`
- Implementing in code → `figma-design-to-code`, `frontend-design:frontend-design`
- Naming, taglines, mood boards and iconography systems are outside this skill
