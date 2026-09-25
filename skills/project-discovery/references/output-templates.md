# Output Templates

## 1. CLAUDE.md (or PROJECT.md)

```markdown
# Project: [Name]

## Overview
[2-3 sentences on what this is]

## Tech stack
- Frontend: Next.js 15 (App Router)
- Backend: Next.js API Routes
- Database: PostgreSQL (Supabase)
- ORM: Drizzle
- Auth: Lucia + GitHub OAuth
- Styling: Tailwind + shadcn/ui
- Hosting: Vercel

## Key decisions
- Using Result<T> pattern, services never throw
- All dates UTC, convert in frontend
- Feature-based folder structure
- Direct imports, no barrel exports

## Code patterns
[Document specific patterns agreed on]

## Features
- [ ] Auth (GitHub OAuth)
- [ ] User profile
- [ ] ...
```

Every category in `stack-menu.md` gets a line here, including the ones decided as
"not needed" and why.

## 2. Initial Folder Structure

```
src/
  app/
  components/
    ui/
  lib/
    db.ts
    env.ts
    errors.ts        ← Standard error types
    logger.ts        ← pino structured logging
    try-catch.ts     ← Error handling utility
  features/
  types/
```

## 3. Config Files

- `tsconfig.json` with strict mode + path aliases
- `.env.example` with all required vars
- `drizzle.config.ts` (if using Drizzle)
- `.eslintrc` with import ordering
- `.prettierrc` for formatting
