# CodeRabbit Learnings: copy-paste-ready

Rules that attach to a file glob live in `coderabbit.yaml.template`; these are the ones that cannot. Registration steps are in `README.md`.

Recommended scope: **global**. These are personal conventions that should apply to every project.

---

## Null vs undefined

> Use `null` for intentional absence ("not found" is expected), `undefined` for optional / not-set fields. A `nickname?: string` field is undefined when not provided; a `findUser` that didn't find anything returns `null`.

## Surgical changes

> Only touch what the task requires. Don't "improve" adjacent code, comments, or formatting. Don't refactor things that aren't broken. Match existing style, even if you'd do it differently. When you notice unrelated dead code or issues, mention them in the review summary — don't fix them silently in the same PR.

## Conventional commits

> Commit messages use conventional-commits format: `feat: ...`, `fix: ...`, `refactor: ...`, `chore: ...`, `docs: ...`. The first line is under 70 characters. Body explains WHY, not WHAT (the diff already shows what).

## Branch naming

> Branch names follow these patterns: `bhagya/feat-<feature>` for new features, `bhagya/fix-<issue>` for bug fixes, `feature/<feature-name>` for shared collaborative branches. Don't suggest renaming branches; just verify PRs target sensible bases.

## Date / time handling

> Store all dates as UTC in the database. Use ISO strings for API transport. Convert to local timezone only in UI code. Use `date-fns` or `dayjs` for date manipulation, never native `Date` methods.

## Don't suggest

> Do NOT suggest "consider adding tests" as a generic finding — only when tests were expected and omitted. Do NOT suggest extracting code to a shared package unless the code is fully generic (no domain types in signature OR body) AND a suitable shared package already exists. Do NOT flag `.toFixed()` / `.toString()` as type-coercion bugs when the call is wrapped in `Number(...)` / `parseFloat(...)` / `parseInt(...)` on the same line.
