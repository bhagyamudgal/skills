# Mode — Color Palette

- **Slots**:
  1. Industry / category
  2. Brand vibe (same options as Typography)
  3. Mood keywords (2-4 words, e.g., "trustworthy + warm + premium")
- **Output**:
  - **Primary** (1-2 colors with hex, role description)
  - **Secondary** (1-2 colors with hex, role description)
  - **Accent** (1 color with hex, "use sparingly for X")
  - **Light theme** (background, surface, foreground, muted, border, brand, and accent tokens with hex)
  - **Dark theme** (the same semantic roles chosen independently, not produced by simple inversion)
  - **Semantic** (success / warning / danger / info — with hex)
  - **Contrast proof**: classify each intended use, then apply the WCAG 2.2 criteria in the main skill to measured mark, text, and accent pairings in both themes. Label presentation-only colors instead of treating them as accessible text colors.
  - **Usage ratio**: a one-line 60/30/10 or similar split showing how the palette should be balanced in real layouts
- **File save**: yes
- **Next step**: → `/figma-generate-library` to add as color variables
