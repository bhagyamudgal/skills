---
name: backend-perf
description: Backend and database performance checklist. Use when writing or reviewing any backend endpoint, service, or DB query, when adding a WHERE clause or index, or when a query rewrite is proposed. Triggers on "endpoint is slow", "N+1", "race condition".
---

# Backend Performance Checklist

Walk every check below against the code in hand. State the verdict on each — applied, clean, or not applicable and why. **A check you did not name is a check you did not run.**

Checks marked `[pg]` are PostgreSQL-specific; skip them on other stores rather than translating them.

- **Parallel async**: If 2+ async calls are independent, wrap in `Promise.all`
- **N+1 queries**: Never query inside a SEQUENTIAL loop (`for`/`for await`) — batch with `IN` clauses or join instead. NOTE: `Promise.all(items.map(q => oneQuery(q)))` with N small index-friendly queries is NOT a sequential N+1 — it's parallel. Keep parallel-N unless `EXPLAIN` shows the batched join faster; batching often defeats the per-row index.
- **Pagination counts**: Return count and rows from one query — a `count(*) OVER ()` window or a single CTE — not a separate `COUNT(*)` alongside the data query
- **Index coverage** `[pg]`: Every `WHERE` clause used in production queries must have a matching index. If you write `similarity(col, ...)`, `@@ to_tsvector(...)`, or `LIKE '%pattern%'`, the same PR must add the matching `gin (col gin_trgm_ops)` / `gin (to_tsvector('lang', col))` index — or include an explicit comment justifying the seq scan.
- **STABLE function reuse** `[pg]`: `pg_trgm.similarity` and `ts_rank` are STABLE, not IMMUTABLE — PostgreSQL won't reliably memoize duplicate calls in the same SELECT. If you need the value twice (e.g., once in the projection, once in `GREATEST(...)`), compute it once via a subquery alias.
- **Select only needed columns**: Project explicitly in list endpoints — name the columns rather than selecting the whole row
- **Reuse fetched rows**: A row fetched for an ownership check is the row the handler returns — don't re-fetch it by id
- **EXPLAIN before rewriting** `[pg]`: Any query restructure — batching, joining, indexing, or replacing parallel-N with batched-1 — ships `EXPLAIN (ANALYZE, BUFFERS)` numbers for current vs proposed on representative data; keep the faster shape. A rewrite that _looks_ faster on the diff can be 10-100× slower under real data.
- **Race conditions**: If 2+ writers can touch the same row, use a transaction. Async completion order is not source order — make ordering explicit with `await` or `Promise.all` rather than relying on accidental serialization. If a check + write must be atomic, use `SELECT ... FOR UPDATE` `[pg]` or a unique constraint, not application-level locking.
