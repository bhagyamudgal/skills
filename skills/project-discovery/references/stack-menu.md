# Stack Menu — Discovery Categories 2-10

Category 1 (PROJECT OVERVIEW) is in `SKILL.md`. Use the option list and the
separating questions for whichever layer the interview has reached.

### 2. TECH STACK

Open each category with a recommendation fitted to their constraints; let them push back.

**Frontend Framework**
- Next.js (App Router) — Full-stack, great DX, Vercel-optimized
- Remix — Better data loading patterns, more control
- SvelteKit — Simpler mental model, less boilerplate
- Astro — Content-heavy sites, partial hydration
- Plain React + Vite — Maximum flexibility, no opinions

*Questions to ask:*
- SSR needed or SPA fine?
- SEO important?
- Team's React experience?
- Deploying to Vercel or self-hosted?

**Backend Framework**
- Next.js API Routes — Simplest if already using Next
- Hono — Fast, lightweight, runs everywhere
- NestJS — Enterprise patterns, DI, structure
- Fastify — Fast, great plugin ecosystem
- Go/Rust — Performance-critical, team knows it

*Questions to ask:*
- WebSocket/real-time needs?
- Background jobs needed?
- Existing backend experience?
- Deployment target constraints?

**Language**
- TypeScript strict — Catch errors early, better DX
- TypeScript relaxed — Faster iteration, gradual adoption
- Multiple languages — Right tool for each job

### 3. DATABASE

This decision affects everything downstream.

**Options**
- PostgreSQL — Best default, handles 90% of use cases
- MySQL — If team knows it, legacy integration
- SQLite — Embedded, simple deploys, surprisingly capable
- MongoDB — Document model fits naturally, schema flexibility needed
- Supabase — Postgres + auth + realtime + storage bundled

*Critical questions:*
- Self-hosted or managed?
- Expected data volume? (GB, TB, PB?)
- Query patterns — heavy reads, heavy writes, analytics?
- Multi-tenant? How isolated?
- Compliance requirements affecting data location?

**ORM/Query Builder**
- Drizzle — Type-safe, fast, SQL-like, no codegen
- Prisma — Great DX, larger ecosystem, slower
- Kysely — Type-safe query builder, no ORM magic
- Raw SQL — Maximum control, no abstraction

*Questions:*
- Complex queries or mostly CRUD?
- Team's SQL comfort level?
- Need migrations in CI/CD?

**Caching**
- Redis — Session, cache, queues, pubsub
- Upstash — Serverless Redis
- In-memory — Simple apps, single instance
- None — Start without, add when needed

### 4. AUTH & SECURITY

Get this wrong and you're rebuilding later.

**Auth Method**
- Email/password — Traditional, users expect it
- Magic link — No passwords to manage, better UX
- OAuth only — Delegate to Google/GitHub/etc
- SSO/SAML — Enterprise requirement
- API keys — Service-to-service, developer platforms

**Auth Library**
- Lucia — Flexible, self-hosted, good DX
- NextAuth/Auth.js — Quick setup, many providers
- Clerk — Managed, beautiful UI, costs money
- Supabase Auth — If using Supabase already
- Custom JWT — Full control, more work

*Questions:*
- Which OAuth providers?
- 2FA requirement?
- Session vs JWT?
- Where do tokens live? (httpOnly cookies vs localStorage)

**Authorization**
- Simple roles — admin/user, good for most apps
- RBAC — Role-based, permissions per role
- ABAC — Attribute-based, fine-grained
- Multi-tenant — Per-org roles, data isolation

*Critical questions:*
- What roles exist?
- Resource-level permissions? (user can edit own posts only)
- Row-level security needed?
- How do permissions change over time?

**Compliance**
- HIPAA — Healthcare, PHI protection, audit logs
- GDPR — EU data, consent, right to deletion
- SOC2 — Enterprise sales requirement

*If any apply:*
- Data residency requirements?
- Audit logging needs?
- Data retention policies?
- Encryption at rest/in transit?

### 5. API DESIGN

How frontend talks to backend.

**Style**
- REST — Universal, cacheable, well understood
- tRPC — End-to-end type safety, Next.js native
- GraphQL — Flexible queries, higher complexity
- Server Actions — Next.js 14+, simplest for forms

**Validation**
- Zod — TypeScript-first, great inference
- Valibot — Smaller bundle, similar API
- AJV — JSON Schema, language agnostic

**Error Handling**
- Result<T,E> pattern — Explicit, no throwing
- Throw + catch — Simple, familiar
- Error codes — API consistency

*Questions:*
- Public API or internal only?
- Versioning needed?
- Rate limiting requirements?
- Documentation approach?

### 6. FRONTEND ARCHITECTURE

**Styling**
- Tailwind — Utility-first, consistent, great DX
- CSS Modules — Scoped, no runtime
- Styled Components — CSS-in-JS, dynamic styles
- Vanilla CSS — No build step, simpler mental model

**UI Components**
- shadcn/ui — Copy-paste, customizable, Tailwind
- Radix — Unstyled primitives, accessible
- Headless UI — Tailwind Labs, simpler API
- Build custom — Maximum control

**State Management**
- React Query / TanStack — Server state, caching
- Zustand — Simple global state
- Jotai — Atomic state, bottom-up
- Just useState — Often enough

**Forms**
- React Hook Form — Performance, validation
- Conform — Progressive enhancement, server actions
- Native + Zod — Simple forms

*Questions:*
- Design system or ad-hoc?
- Dark mode?
- Mobile-first?
- Accessibility requirements?
- i18n needed?

### 7. INFRASTRUCTURE

**Hosting**
- Vercel — Best Next.js DX, preview deploys, costs scale
- Coolify — Self-hosted PaaS, Docker-based
- Railway — Simple deploys, good free tier
- Fly.io — Edge, containers, good for global
- Hetzner + Docker — Cheapest, most control
- AWS/GCP — Enterprise, complex, powerful

*Questions:*
- Preview environments per PR?
- Edge deployment needed?
- Budget constraints?
- Team's ops experience?

**CI/CD**
- GitHub Actions — Integrated, free for public
- GitLab CI — If using GitLab
- None for now — Manual deploys initially

**Monitoring**
- Sentry — Errors, performance, sessions
- Axiom/LogTail — Logs, cheap
- Grafana stack — Self-hosted, powerful
- PostHog — Analytics + session replay

**Domains**
- Main app domain
- API subdomain? (api.example.com)
- Separate marketing site?

### 8. INTEGRATIONS

**Email**
- Resend — Best DX, React Email
- Postmark — Reliable, great deliverability
- AWS SES — Cheapest at scale

**Payments**
- Stripe — Best overall, most features
- LemonSqueezy — Simpler, handles tax
- Paddle — SaaS-focused, MoR

**Other common needs:**
- SMS (Twilio, AWS SNS)
- File storage (S3, R2, Supabase Storage)
- Search (Algolia, Meilisearch, Typesense)
- AI/LLM (OpenAI, Anthropic, local models)
- Analytics (PostHog, Mixpanel, Plausible)

### 9. CODE PATTERNS

Establish conventions early.

**Folder Structure**
```
Feature-based (recommended):
src/
  features/
    auth/
      components/
      api/
      hooks/
    patients/
      ...

Layer-based:
src/
  components/
  services/
  api/
  hooks/
```

**Naming Conventions**
- Files: kebab-case (`user-service.ts`) or match export (`UserService.ts`)
- Components: PascalCase (`PatientCard.tsx`)
- Functions: camelCase (`getPatientById`)
- Constants: SCREAMING_SNAKE (`MAX_RETRY_COUNT`)

**Imports**
- Direct imports (tree-shakeable): `import { Button } from '@/components/ui/button'`
- Path aliases: `@/` for src root
- Avoid barrel exports (slower builds)

**Error Handling Pattern**

Pick Result or throw+catch — both are written out in `coding-standards.md`.
Decide here; the type is defined there, once.

**Git Workflow**
- Conventional commits: `feat:`, `fix:`, `chore:`
- Feature branches: `feature/add-auth`
- Trunk-based: direct to main with feature flags

### 10. TESTING

**Strategy**
- Unit + Integration — Test business logic, API contracts
- E2E only — Test user flows, less maintenance
- Minimal for MVP — Ship fast, test critical paths
- TDD — If team practices it

**Frameworks**
- Vitest — Fast, Vite-native, Jest-compatible
- Playwright — E2E, best cross-browser
- Testing Library — Component testing
