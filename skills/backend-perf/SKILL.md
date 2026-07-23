---
name: backend-perf
description: Performance checklist for backend services and database queries — parallel async, N+1 detection, single-pass pagination counts, index coverage, STABLE function reuse, column selection, EXPLAIN-evidence for rewrites, and race-condition handling. Use when writing or reviewing any backend endpoint, service, or DB query (SQL, Drizzle, Prisma, Convex), when adding a WHERE clause or index, or when a perf rewrite/batching/join restructure is proposed. Triggers on "optimize this query", "endpoint is slow", "add an index", "N+1", "race condition".
---

# Backend Performance Checklist

Apply these checks to every backend service and database query.

- **Parallel async**: If 2+ async calls are independent, wrap in `Promise.all` — never sequential awaits for unrelated data
- **N+1 queries**: Never query inside a SEQUENTIAL loop (`for`/`for await`) — batch with `IN` clauses or join instead. NOTE: `Promise.all(items.map(q => oneQuery(q)))` with N small index-friendly queries is NOT a sequential N+1 — it's parallel. Don't blindly rewrite it into a single batched LATERAL/VALUES join; that often defeats the index. Before replacing parallel-N with batched-1, run `EXPLAIN (ANALYZE, BUFFERS)` on both shapes against representative data and keep the faster one.
- **Pagination counts**: Use a single-pass count + data helper — never run a separate `COUNT(*)` query alongside the data query
- **Index coverage**: Every `WHERE` clause used in production queries must have a matching index. If you write `similarity(col, ...)`, `@@ to_tsvector(...)`, or `LIKE '%pattern%'`, the same PR must add the matching `gin (col gin_trgm_ops)` / `gin (to_tsvector('lang', col))` index — or include an explicit comment justifying the seq scan.
- **STABLE function reuse**: `pg_trgm.similarity` and `ts_rank` are STABLE, not IMMUTABLE — PostgreSQL won't reliably memoize duplicate calls in the same SELECT. If you need the value twice (e.g., once in the projection, once in `GREATEST(...)`), compute it once via a subquery alias.
- **Select only needed columns**: Use `.select({ field1, field2 })` not `.select()` for list endpoints
- **Avoid redundant queries**: If you already fetched data for validation, reuse it
- **Perf rewrites need evidence**: When proposing a query restructure (batching, joining, indexing) in code review, ship `EXPLAIN (ANALYZE, BUFFERS)` numbers for current vs proposed. Without measurement, a rewrite that _looks_ faster on the diff can be 10-100× slower under real data.
- **Concurrency / race conditions**: If 2+ writers can touch the same row, use a transaction. Async code order ≠ source code order — be explicit about ordering with `await` or `Promise.all`, never rely on accidental serialization. If a check + write must be atomic, use `SELECT ... FOR UPDATE` or a unique constraint, not application-level locking.
