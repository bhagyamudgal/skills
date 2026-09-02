---
name: backend-perf
description: Backend and database performance checklist. Use when writing or reviewing any backend endpoint, service, or DB query, when adding a WHERE clause or index, or when a query rewrite is proposed. Triggers on "endpoint is slow", "N+1", "race condition".
---

# Backend performance checklist

I walk every check below against the code in hand and state a verdict on each one. Applied, clean, or not applicable and why. A check I did not name is a check I did not run.

Checks marked `[pg]` are PostgreSQL-specific. I skip them on other stores rather than translating them.

- I run independent async work together. I wrap 2+ independent async calls in `Promise.all`.
- I never query inside a sequential loop. I mean `for` and `for await` loops. I batch with `IN` clauses or a join instead. Note that `Promise.all(items.map(q => oneQuery(q)))` with N small index-friendly queries is not a sequential N+1. It runs in parallel. I keep the parallel shape unless `EXPLAIN` shows the batched join runs faster, because batching often defeats the per-row index.
- I return count and rows from one query. I use a `count(*) OVER ()` window or a single CTE, not a separate `COUNT(*)` next to the data query.
- `[pg]` I cover every production `WHERE` clause with a matching index. When I write `similarity(col, ...)`, `@@ to_tsvector(...)`, or `LIKE '%pattern%'`, the same PR adds the matching `gin (col gin_trgm_ops)` or `gin (to_tsvector('lang', col))` index, or carries an explicit comment that justifies the sequential scan.
- `[pg]` I compute STABLE values once. `pg_trgm.similarity` and `ts_rank` are STABLE, not IMMUTABLE, so PostgreSQL does not reliably memoize duplicate calls in one SELECT. When I need the value twice, for example once in the projection and once in `GREATEST(...)`, I compute it once in a `WITH ... AS MATERIALIZED` CTE. A plain subquery alias does not guarantee this. The planner can flatten it and evaluate per row.
- I project explicitly in list endpoints. I name the columns instead of selecting the whole row.
- I reuse a row I already fetched. A row fetched for an ownership check is the row the handler returns. I do not fetch it again by id.
- `[pg]` I measure before I rewrite. Any query restructure, batching, joining, indexing, or replacement of parallel-N with batched-1 ships `EXPLAIN (ANALYZE, BUFFERS)` numbers for current versus proposed shape on representative data, and I keep the faster shape. A rewrite that looks faster in the diff can run 10-100× slower on real data.
- I close races. When 2+ writers can touch one row, I use a transaction. Async completion order is not source order. I make ordering explicit with `await` or `Promise.all` instead of relying on accidental serialization. When a check plus a write must stay atomic, I use `SELECT ... FOR UPDATE` on `[pg]` or a unique constraint, not application-level locking.
