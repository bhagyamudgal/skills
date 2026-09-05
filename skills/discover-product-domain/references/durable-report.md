# Durable report format

Read this only when the user asks for a saved write-up. Otherwise the funnel
returns its recommendation in the conversation and writes no file.

## Resolve the path

Derive a snake_case slug from the free-text idea label in three ordered steps:
lowercase the label, replace non-alphanumeric runs with `_`, then strip leading
and trailing `_` characters. Require the whole slug to match the non-empty
basename pattern `^[a-z0-9]+(?:_[a-z0-9]+)*$`.

Never accept a caller-supplied output path; reject a supplied filename or slug
when it is absolute or contains a path separator or `.`/`..` path segment.
Resolve `docs/<slug>_domain_discovery.md` against the repository's resolved
`docs/` directory and write only when the result's parent is that directory.

## Contents

Include the brief, the entry route, the supplied or generated candidates,
rejected domains, finalists or survivors, and the evidence record
`references/domain-verification.md` requires per result (exact domain, status,
UTC check time, method, source or redacted endpoint, response class, errors,
plus the registrar pricing fields before any standard-price claim). Name a winner
when one exists, and a runner-up only when at least two names survive. Include
the artifacts the route actually produced:

- **Greenfield:** atom bank, first 12, user or autonomous reaction, and remixes.
- **Shortlist plus alternatives:** supplied shortlist, atom bank, its reaction,
  and remixes.
- **Remix or refinement:** supplied seeds, atom bank, reaction, and remixes.
- **Verification or ranking only:** supplied shortlist; omit or mark the first 12,
  reaction, and remixes as not applicable.
