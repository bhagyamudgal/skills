---
name: project-discovery
description: Deep project discovery and architecture planning. Use when starting a new project, when user says "new project", "let's build", or asks for help architecting/planning a non-trivial application.
---

# Project Discovery Skill

A structured framework for deeply understanding a project before writing any code. Use this when starting a new project or when the user asks to architect/plan something.

## When to Use This Skill

- User says "new project", "let's build", "I want to create"
- User asks for help architecting or planning
- Starting any non-trivial application
- User seems unsure about technical decisions

## Core Philosophy

**Don't just accept answers — interrogate them.**

Bad: "What database do you want?" → "PostgreSQL" → "OK"

Good: "What database?" → "PostgreSQL" → "Self-hosted or managed? What's your expected data volume? Any compliance requirements that affect where data lives? Given you're deploying on Coolify, have you considered the backup story?"

## Discovery Approach

### 1. Be Conversational, Not Interrogative

Don't read questions like a form. React to answers, build on them, challenge assumptions.

```
❌ "What's your tech stack? What's your database? What's your auth?"

✅ "Tell me what you're building and who it's for... 
    Interesting, so doctors need to see patient schedules — that suggests real-time updates might matter. 
    Are you thinking WebSockets or polling? Actually, before that — what's your team's comfort level with different stacks?"
```

### 2. Push Back When Needed

If choices don't fit constraints, say so.

```
User: "I want microservices"
You: "What problem does microservices solve for you right now? You mentioned it's just you building this with a 3-month timeline. Microservices add operational complexity — deployment, networking, distributed tracing. A well-structured monolith might get you to market faster. What's driving the microservices thinking?"
```

### 3. Suggest Based on Context

Tailor recommendations to their situation.

```
Solo dev + tight timeline → Simpler stack, managed services
Team + enterprise client → More structure, better patterns
Healthcare/finance → Security-first, compliance awareness
```

### 4. Explain Trade-offs

Never just recommend — explain why and what you're giving up.

```
"I'd suggest Drizzle over Prisma here. Trade-off: Drizzle has a smaller ecosystem and fewer tutorials, but it's faster, has better TypeScript inference, and doesn't need a separate generate step. Given you're comfortable with SQL, you'll appreciate the query builder being closer to actual SQL."
```

---

## Discovery Categories

Work through these categories naturally in conversation. You don't need to cover every question — adapt to the project.

### 1. PROJECT OVERVIEW

Understand the what and why before the how.

| Question | Why It Matters |
|----------|----------------|
| What does this project do? Who is it for? | Frames all technical decisions |
| What problem are we solving? What's painful now? | Ensures we're solving real problems |
| How will we know if it's successful? | Defines done, prevents scope creep |
| What's the timeline? MVP vs full launch? | Determines build vs buy, complexity tolerance |
| Who's building this? Solo, small team, org? | Affects architecture, tooling choices |
| What's the budget for infrastructure/services? | Managed vs self-hosted decisions |

### 2. TECH STACK

Don't just ask — suggest based on their context.

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
```typescript
// Result pattern - explicit success/failure
type Result<T, E = Error> = 
  | { ok: true; value: T }
  | { ok: false; error: E };

// Usage
const result = await createUser(data);
if (!result.ok) {
  return handleError(result.error);
}
return result.value;
```

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

---

## Coding Patterns & Rules to Establish

This is critical. Establish these patterns BEFORE writing code. These become the project's "laws" that Claude follows in every session.

### 0. CORE PRINCIPLES (Non-Negotiable)

**DRY — Don't Repeat Yourself**
```typescript
// ❌ Repeated logic
function getPatientFullName(patient: Patient) {
  return `${patient.firstName} ${patient.lastName}`;
}
function getDoctorFullName(doctor: Doctor) {
  return `${doctor.firstName} ${doctor.lastName}`;
}

// ✅ Single reusable function
function getFullName(person: { firstName: string; lastName: string }) {
  return `${person.firstName} ${person.lastName}`;
}
```

If you write the same logic twice, extract it. This applies to:
- Utility functions
- API call patterns
- Validation logic
- UI components
- Type definitions

**Use `type` over `interface`**
```typescript
// ❌ Avoid interface
interface User {
  id: string;
  name: string;
}

// ✅ Use type
type User = {
  id: string;
  name: string;
};

// ✅ Type works better for unions, intersections, mapped types
type Status = 'pending' | 'active' | 'cancelled';
type UserWithPosts = User & { posts: Post[] };
type Nullable<T> = T | null;
```

**Use `function` keyword, not arrow functions**
```typescript
// ❌ Avoid arrow functions for declarations
const getUser = async (id: string) => {
  return db.users.find(id);
};

const UserCard = ({ user }: UserCardProps) => {
  return <div>{user.name}</div>;
};

// ✅ Use function keyword
async function getUser(id: string) {
  return db.users.find(id);
}

function UserCard({ user }: UserCardProps) {
  return <div>{user.name}</div>;
}
```

Why function keyword:
- Hoisted (can call before definition)
- Better stack traces
- Clearer intent ("this is a function")
- `this` binding is explicit

Arrow functions are OK for:
- Inline callbacks: `items.map(item => item.id)`
- Event handlers in JSX: `onClick={() => setOpen(true)}`

---

### 0.1 CODING RULES (Always Follow)

These rules apply to ALL code written. No exceptions.

#### TypeScript Strictness

**No non-null assertions (`!.`)**
```typescript
// ❌ Never do this
const name = user!.name;
const first = items[0]!;

// ✅ Handle the null case properly
const name = user?.name ?? 'Unknown';

// ✅ Use type narrowing
if (!user) {
  throw new Error('User not found');
}
const name = user.name;  // TypeScript knows it's defined

// ✅ Use early return
function getDisplayName(user: User | null): string {
  if (!user) return 'Guest';
  return user.name;
}
```

**No `any` type — define proper types, use `unknown` and narrow if types can't be defined**
```typescript
// ❌ Avoid any
function processData(data: any) {}
const result: any = fetchSomething();

// ✅ Define proper types first
type ApiResponse = {
  data: User[];
  meta: { total: number };
};

function processData(data: ApiResponse) {}

// ✅ Use unknown and narrow if types can't be defined
function processUnknownData(data: unknown) {
  if (typeof data === 'string') {
    // TypeScript knows it's string here
  }
  if (isUser(data)) {
    // Use type guard for complex types
  }
}

// ✅ Use generics for flexible typing
function processData<T>(data: T): T {}
```

**Check IDE for TypeScript errors after changes**
- Use IDE TypeScript integration to check errors for small changes, not `tsc` or `typecheck` commands
- For big changes, can use `typecheck` command if present in project
- Fix all errors before considering task complete

#### Code Quality

**No comments unless logic is complex**
```typescript
// ❌ Useless comments
// Get user by ID
function getUserById(id: string) {}

// Increment counter
counter++;

// ✅ Only comment WHY, not WHAT
// Retry 3 times because payment gateway has intermittent 503s
const MAX_RETRIES = 3;

// Using Monday as start because Swiss hospitals use ISO week
const weekStart = startOfISOWeek(date);
```

**No emoji in logs or code**
```typescript
// ❌ No emoji
console.log('✅ User created successfully');
logger.info('🚀 Server started');

// ✅ Clean logs
console.log('User created successfully');
logger.info({ port: 3000 }, 'Server started');
```

**Review code after making changes**
- Re-read the logic to verify correctness
- Check for edge cases
- Ensure error handling is complete
- Run `/code-review` command after completing tasks

#### Database Rules

**Use Drizzle query builder, not raw SQL**
```typescript
// ❌ Avoid raw SQL
const users = await db.execute(
  sql`SELECT * FROM users WHERE clinic_id = ${clinicId}`
);

// ✅ Use Drizzle functions for type safety
const users = await db.query.users.findMany({
  where: eq(users.clinicId, clinicId),
  with: { appointments: true },
});

// ✅ Raw SQL only when Drizzle can't do it
const result = await db.execute(
  sql`SELECT complex_aggregate_function(...)`
);
```

**Never run migrations without explicit permission**
- Don't run `db:push`
- Don't run `db:migrate`  
- Don't run `db:generate`
- Ask before any database schema changes

#### Additional Recommended Rules

**Prefer early returns over nesting**
```typescript
// ❌ Deeply nested
function processUser(user: User | null) {
  if (user) {
    if (user.isActive) {
      if (user.hasPermission) {
        return doSomething(user);
      }
    }
  }
  return null;
}

// ✅ Early returns
function processUser(user: User | null) {
  if (!user) return null;
  if (!user.isActive) return null;
  if (!user.hasPermission) return null;
  return doSomething(user);
}
```

**No magic numbers or strings**
```typescript
// ❌ Magic values
if (status === 1) {}
setTimeout(fn, 86400000);
if (role === 'admin') {}

// ✅ Named constants
const STATUS_ACTIVE = 1;
const ONE_DAY_MS = 24 * 60 * 60 * 1000;
const ROLES = { ADMIN: 'admin', USER: 'user' } as const;

if (status === STATUS_ACTIVE) {}
setTimeout(fn, ONE_DAY_MS);
if (role === ROLES.ADMIN) {}
```

**Use optional chaining and nullish coalescing**
```typescript
// ❌ Verbose null checks
const street = user && user.address && user.address.street;
const name = user.name || 'Unknown';  // Bug: empty string becomes 'Unknown'

// ✅ Modern operators
const street = user?.address?.street;
const name = user.name ?? 'Unknown';  // Only null/undefined trigger fallback
```

**Prefer const over let**
```typescript
// ❌ Using let when value doesn't change
let user = await getUser(id);
let total = items.reduce((sum, i) => sum + i.price, 0);

// ✅ Use const
const user = await getUser(id);
const total = items.reduce((sum, i) => sum + i.price, 0);

// let only when reassignment is needed
let attempts = 0;
while (attempts < 3) {
  attempts++;
}
```

**Prefer async/await over .then()**
```typescript
// ❌ Promise chains
function getData() {
  return fetch('/api/data')
    .then(res => res.json())
    .then(data => processData(data))
    .catch(err => handleError(err));
}

// ✅ async/await
async function getData() {
  const { data, error } = await tryCatch(fetch('/api/data').then(r => r.json()));
  if (error) return handleError(error);
  return processData(data);
}
```

**Use `tryCatch` utility instead of try-catch blocks**

Always use the `tryCatch` utility for async error handling. No raw try-catch blocks.

```typescript
// lib/try-catch.ts — Add this to every project

type Success<T> = {
  data: T;
  error: null;
};

type Failure<E> = {
  data: null;
  error: E;
};

type Result<T, E = Error> = Success<T> | Failure<E>;

// Main async wrapper
export async function tryCatch<T, E = Error>(
  promise: Promise<T>,
): Promise<Result<T, E>> {
  try {
    const data = await promise;
    return { data, error: null };
  } catch (error) {
    return { data: null, error: error as E };
  }
}

// Sync version for non-async functions that might throw
export function tryCatchSync<T, E = Error>(
  fn: () => T,
): Result<T, E> {
  try {
    const data = fn();
    return { data, error: null };
  } catch (error) {
    return { data: null, error: error as E };
  }
}

// Wrapper for functions — returns a safe version that never throws
export function withTryCatch<TArgs extends unknown[], TReturn, E = Error>(
  fn: (...args: TArgs) => Promise<TReturn>,
): (...args: TArgs) => Promise<Result<TReturn, E>> {
  return async (...args: TArgs) => {
    return tryCatch<TReturn, E>(fn(...args));
  };
}

// Retry wrapper with exponential backoff
export async function tryCatchRetry<T, E = Error>(
  promise: () => Promise<T>,
  options: {
    maxRetries?: number;
    delayMs?: number;
    backoff?: boolean;
  } = {},
): Promise<Result<T, E>> {
  const { maxRetries = 3, delayMs = 1000, backoff = true } = options;
  
  let lastError: E | null = null;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const { data, error } = await tryCatch<T, E>(promise());
    
    if (!error) {
      return { data, error: null };
    }
    
    lastError = error;
    
    if (attempt < maxRetries) {
      const delay = backoff ? delayMs * Math.pow(2, attempt) : delayMs;
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  return { data: null, error: lastError as E };
}

// Timeout wrapper
export async function tryCatchWithTimeout<T, E = Error>(
  promise: Promise<T>,
  timeoutMs: number,
  timeoutError?: E,
): Promise<Result<T, E>> {
  const timeout = new Promise<never>((_, reject) => {
    setTimeout(() => {
      reject(timeoutError ?? new Error(`Operation timed out after ${timeoutMs}ms`));
    }, timeoutMs);
  });
  
  return tryCatch<T, E>(Promise.race([promise, timeout]));
}
```

```typescript
// ❌ Avoid try-catch blocks
async function getUser(id: string) {
  try {
    const response = await fetch(`/api/users/${id}`);
    const user = await response.json();
    return user;
  } catch (error) {
    console.error('Failed to fetch user:', error);
    return null;
  }
}

// ✅ Use tryCatch utility
import { tryCatch } from '@/lib/try-catch';

async function getUser(id: string) {
  const { data: response, error: fetchError } = await tryCatch(
    fetch(`/api/users/${id}`)
  );
  if (fetchError) {
    logger.error({ id, error: fetchError.message }, 'Failed to fetch user');
    return null;
  }

  const { data: user, error: parseError } = await tryCatch(response.json());
  if (parseError) {
    logger.error({ id, error: parseError.message }, 'Failed to parse user response');
    return null;
  }

  return user;
}

// ✅ Use tryCatchSync for JSON parsing or other sync operations
import { tryCatchSync } from '@/lib/try-catch';

function parseConfig(jsonString: string) {
  const { data, error } = tryCatchSync(() => JSON.parse(jsonString));
  if (error) {
    logger.error('Invalid JSON config');
    return null;
  }
  return data;
}

// ✅ Use withTryCatch to wrap existing functions
import { withTryCatch } from '@/lib/try-catch';

const safeGetUser = withTryCatch(getUser);
const { data: user, error } = await safeGetUser('123');

// ✅ Use tryCatchRetry for flaky operations
import { tryCatchRetry } from '@/lib/try-catch';

const { data, error } = await tryCatchRetry(
  () => fetch('https://flaky-api.com/data'),
  { maxRetries: 3, delayMs: 1000, backoff: true }
);

// ✅ Use tryCatchWithTimeout for operations that might hang
import { tryCatchWithTimeout } from '@/lib/try-catch';

const { data, error } = await tryCatchWithTimeout(
  fetch('https://slow-api.com/data'),
  5000 // 5 second timeout
);
```

Why `tryCatch` over try-catch:
- Explicit error handling at each step
- No nested try-catch blocks
- Consistent destructuring pattern `{ data, error }`
- Forces you to handle errors (can't forget)
- Works great with early returns
- TypeScript knows the types after the check
- Sync version for JSON.parse, etc.
- Retry and timeout built-in for resilience

```typescript
// Multiple async operations — clean and flat
async function createOrderWithPayment(orderData: OrderInput) {
  const { data: order, error: orderError } = await tryCatch(
    orderService.create(orderData)
  );
  if (orderError) {
    return { ok: false, error: { code: 'ORDER_FAILED', cause: orderError } };
  }

  const { data: payment, error: paymentError } = await tryCatch(
    paymentService.charge(order.id, order.total)
  );
  if (paymentError) {
    // Rollback order
    await tryCatch(orderService.cancel(order.id));
    return { ok: false, error: { code: 'PAYMENT_FAILED', cause: paymentError } };
  }

  return { ok: true, data: { order, payment } };
}
```

**No nested ternaries**
```typescript
// ❌ Hard to read
const label = status === 'active' ? 'Active' : status === 'pending' ? 'Pending' : status === 'cancelled' ? 'Cancelled' : 'Unknown';

// ✅ Use object lookup or switch
const STATUS_LABELS: Record<string, string> = {
  active: 'Active',
  pending: 'Pending',
  cancelled: 'Cancelled',
};
const label = STATUS_LABELS[status] ?? 'Unknown';

// ✅ Or function with early returns
function getStatusLabel(status: string): string {
  if (status === 'active') return 'Active';
  if (status === 'pending') return 'Pending';
  if (status === 'cancelled') return 'Cancelled';
  return 'Unknown';
}
```

**Meaningful variable names**
```typescript
// ❌ Cryptic names
const d = new Date();
const u = await getUser(id);
const arr = items.filter(x => x.active);

// ✅ Descriptive names
const currentDate = new Date();
const authenticatedUser = await getUser(id);
const activeItems = items.filter(item => item.active);

// Single letters OK for: loop indices, callbacks, generics
items.map((item, i) => ({ ...item, index: i }));
function identity<T>(value: T): T { return value; }
```

**Boolean names should read as questions**
```typescript
// ❌ Unclear intent
const loading = true;
const data = false;
const permission = true;

// ✅ is/has/can/should prefixes
const isLoading = true;
const hasData = false;
const canDelete = true;
const shouldRefresh = true;
```

**Keep functions small — one function = one job**

Each function should do ONE thing. If a function is too big, divide it into smaller functions and compose them together.

**Guidelines:**
- Functions should be 5-20 lines ideally, max 30-40 lines
- If you need comments to separate "sections" inside a function, it's too big
- If you can't name it clearly, it's doing too much
- Extract until each function does exactly one thing

```typescript
// ❌ Function doing multiple jobs (too big)
async function handleUserRegistration(data: FormData) {
  // Job 1: Validate input (10 lines)
  const errors = [];
  if (!data.email) errors.push('Email required');
  if (!data.password) errors.push('Password required');
  if (data.password.length < 8) errors.push('Password too short');
  if (errors.length > 0) throw new ValidationError(errors);
  
  // Job 2: Hash password (5 lines)
  const salt = await bcrypt.genSalt(10);
  const hashedPassword = await bcrypt.hash(data.password, salt);
  
  // Job 3: Create user in DB (8 lines)
  const user = await db.insert(users).values({
    email: data.email,
    password: hashedPassword,
    createdAt: new Date(),
  }).returning();
  
  // Job 4: Send welcome email (6 lines)
  await transporter.sendMail({
    to: data.email,
    subject: 'Welcome!',
    html: renderWelcomeEmail(user),
  });
  
  // Job 5: Create audit log (5 lines)
  await db.insert(auditLogs).values({
    action: 'USER_REGISTERED',
    userId: user.id,
    timestamp: new Date(),
  });
  
  return user;
}

// ✅ Each function does ONE job
function validateRegistration(data: FormData): ValidatedRegistration {
  const errors = [];
  if (!data.email) errors.push('Email required');
  if (!data.password) errors.push('Password required');
  if (data.password.length < 8) errors.push('Password too short');
  if (errors.length > 0) throw new ValidationError(errors);
  return { email: data.email, password: data.password };
}

async function hashPassword(password: string): Promise<string> {
  const salt = await bcrypt.genSalt(10);
  return bcrypt.hash(password, salt);
}

async function createUserInDb(email: string, hashedPassword: string): Promise<User> {
  const [user] = await db.insert(users).values({
    email,
    password: hashedPassword,
    createdAt: new Date(),
  }).returning();
  return user;
}

async function sendWelcomeEmail(user: User): Promise<void> {
  await transporter.sendMail({
    to: user.email,
    subject: 'Welcome!',
    html: renderWelcomeEmail(user),
  });
}

async function logUserRegistration(userId: string): Promise<void> {
  await db.insert(auditLogs).values({
    action: 'USER_REGISTERED',
    userId,
    timestamp: new Date(),
  });
}

// ✅ Compose small functions into larger operation
async function handleUserRegistration(data: FormData): Promise<User> {
  const validated = validateRegistration(data);
  const hashedPassword = await hashPassword(validated.password);
  const user = await createUserInDb(validated.email, hashedPassword);
  await sendWelcomeEmail(user);
  await logUserRegistration(user.id);
  return user;
}
```

**Benefits of small functions:**
- Easy to test each piece in isolation
- Easy to reuse (e.g., `hashPassword` used elsewhere)
- Easy to understand — name tells you what it does
- Easy to modify without breaking other things
- Easy to compose into different workflows

**Keep files small — refactor when too large**

When files grow too large, split them. Use these limits as guidelines:

| File Type | Max LOC | When to Split |
|-----------|---------|---------------|
| React Components | 150-200 | Extract sub-components, hooks, utils |
| Custom Hooks | 80-100 | Split into smaller hooks, extract helpers |
| API Routes/Handlers | 80-100 | Extract to service layer |
| Service files | 200-250 | Split by domain/entity |
| Utility files | 100-150 | Group by functionality |
| Type definition files | 150-200 | Split by domain |
| Config files | 100 | Split by concern |

```typescript
// ❌ One massive component file (400+ lines)
// user-dashboard.tsx
export function UserDashboard() {
  // 50 lines of hooks and state
  // 100 lines of helper functions
  // 250 lines of JSX with inline logic
}

// ✅ Split into focused files
// user-dashboard/
//   index.tsx           — Main component (80 lines)
//   use-dashboard.ts    — Custom hook for state/logic (60 lines)
//   stats-card.tsx      — Sub-component (40 lines)
//   activity-feed.tsx   — Sub-component (50 lines)
//   utils.ts            — Helper functions (30 lines)
//   types.ts            — Types for this feature (20 lines)
```

**Signs a file needs refactoring:**

1. **Scrolling fatigue** — Can't see the whole file structure at once
2. **Multiple concerns** — File handles unrelated things
3. **Hard to name** — File name is vague like `utils.ts` or `helpers.ts`
4. **Difficult testing** — Need to mock too many things
5. **Frequent merge conflicts** — Multiple people editing same file
6. **Long imports** — Importing many things from one file

**How to split:**

```typescript
// Before: services/user-service.ts (400 lines)
// - User CRUD
// - User authentication
// - User permissions
// - User notifications

// After: Split by concern
// services/user/
//   user.service.ts        — CRUD operations
//   auth.service.ts        — Authentication logic
//   permission.service.ts  — Permission checks
//   notification.service.ts — User notifications
//   index.ts               — Re-exports (optional)
```

```typescript
// Before: components/form.tsx (300 lines)
// - Form component
// - All field components
// - Validation logic
// - Submit handling

// After: Split by responsibility
// components/form/
//   form.tsx              — Main form wrapper
//   form-field.tsx        — Reusable field component
//   use-form-validation.ts — Validation hook
//   form-actions.tsx      — Submit/cancel buttons
//   types.ts              — Form types
```

**Prefer named exports over default exports**
```typescript
// ❌ Default exports — harder to refactor, inconsistent imports
export default function UserCard() {}
import UserCard from './user-card';  // Can be named anything

// ✅ Named exports — explicit, refactor-friendly
export function UserCard() {}
import { UserCard } from './user-card';  // Must match
```

**Don't mutate function parameters**
```typescript
// ❌ Mutating input
function addTimestamp(obj: Record<string, unknown>) {
  obj.timestamp = Date.now();  // Mutates original!
  return obj;
}

// ✅ Return new object
function addTimestamp(obj: Record<string, unknown>) {
  return { ...obj, timestamp: Date.now() };
}
```

**No unused variables or imports**
```typescript
// ❌ Dead code
import { unused } from 'some-lib';
const temp = calculateValue();  // Never used

// ✅ Clean imports, no dead code
// ESLint will catch these — fix before committing
```

**Use destructuring**
```typescript
// ❌ Repetitive property access
function greet(user: User) {
  return `Hello ${user.firstName} ${user.lastName} from ${user.address.city}`;
}

// ✅ Destructure
function greet({ firstName, lastName, address: { city } }: User) {
  return `Hello ${firstName} ${lastName} from ${city}`;
}
```

**Use template literals**
```typescript
// ❌ String concatenation
const message = 'Hello ' + firstName + ' ' + lastName + '!';
const url = baseUrl + '/api/' + version + '/users/' + id;

// ✅ Template literals
const greeting = `Hello ${firstName} ${lastName}`;
const apiUrl = `${baseUrl}/api/${version}/users/${id}`;
```

**No console.log in production code**
```typescript
// ❌ Console in production
console.log('User created:', user);
console.error('Something went wrong');

// ✅ Use proper logger
import { logger } from '@/lib/logger';
logger.info({ userId: user.id }, 'User created');
logger.error({ err }, 'Operation failed');

// console.log OK only for:
// - Local debugging (remove before commit)
// - CLI tools
// - Development-only code
```

---

### 0.2 ADDITIONAL CODING STANDARDS

**Null vs Undefined Convention**

Use `null` for intentional absence, `undefined` for optional/not set:

```typescript
type User = {
  name: string;
  deletedAt: Date | null;  // Explicitly set to "nothing" 
  nickname?: string;       // May not exist (undefined)
};

// Return null when "not found" is an expected outcome
async function findUser(id: string): Promise<User | null> {
  const user = await db.users.find(id);
  return user ?? null;
}

// Use undefined for optional parameters
function greet(name: string, title?: string) {
  return title ? `Hello ${title} ${name}` : `Hello ${name}`;
}

// Summary:
// null = "I explicitly set this to nothing"
// undefined = "This was never set" or "This is optional"
```

**Import Type for Type-Only Imports**

Use `import type` for imports that are only used as types — they get erased at compile time:

```typescript
// ❌ Imports type at runtime (may add to bundle)
import { User, UserService } from './user';

// ✅ Type-only import (erased at compile time)
import type { User, Post } from './types';
import { UserService } from './user';

// ✅ Or inline type imports
import { UserService, type User, type CreateUserInput } from './user';

// Benefits:
// - Smaller bundle (types erased)
// - Clearer intent (this is just a type)
// - Avoids circular dependency issues
```

**Async Patterns — Parallel vs Sequential**

Run independent async operations in parallel:

```typescript
// ❌ Sequential (slow) — each waits for previous
async function loadDashboard(userId: string) {
  const user = await getUser(userId);           // 100ms
  const posts = await getPosts(userId);         // 100ms
  const notifications = await getNotifications(userId);  // 100ms
  // Total: 300ms
  return { user, posts, notifications };
}

// ✅ Parallel (fast) — all run at once
async function loadDashboard(userId: string) {
  const [user, posts, notifications] = await Promise.all([
    getUser(userId),           // 100ms
    getPosts(userId),          // 100ms  
    getNotifications(userId),  // 100ms
  ]);
  // Total: ~100ms
  return { user, posts, notifications };
}

// ✅ Parallel with tryCatch for error handling
async function loadDashboard(userId: string) {
  const [userResult, postsResult, notificationsResult] = await Promise.all([
    tryCatch(getUser(userId)),
    tryCatch(getPosts(userId)),
    tryCatch(getNotifications(userId)),
  ]);
  
  if (userResult.error) {
    // Handle user fetch error
  }
  
  return {
    user: userResult.data,
    posts: postsResult.data ?? [],
    notifications: notificationsResult.data ?? [],
  };
}

// When to use sequential:
// - When second call depends on first call's result
// - When you need to short-circuit on failure
const user = await getUser(userId);
if (!user) return null;
const posts = await getPostsByAuthor(user.authorId);  // Depends on user
```

**Date/Time Handling**

Dates are a common source of bugs. Follow these rules:

```typescript
// RULES:
// 1. Store all dates as UTC in database
// 2. Use ISO strings for API transport
// 3. Convert to local timezone only in UI layer
// 4. Use date-fns or dayjs — not native Date methods for manipulation

// ❌ Ambiguous — what timezone?
const date = new Date('2024-01-15');
const formatted = date.toLocaleDateString();

// ✅ Explicit UTC
const date = new Date('2024-01-15T00:00:00Z');

// ✅ Use date-fns for manipulation
import { addDays, format, parseISO, startOfDay } from 'date-fns';
import { formatInTimeZone } from 'date-fns-tz';

const parsed = parseISO('2024-01-15T10:30:00Z');
const nextWeek = addDays(parsed, 7);
const formatted = format(nextWeek, 'yyyy-MM-dd');

// ✅ API response — always ISO string
return Response.json({
  createdAt: user.createdAt.toISOString(),
});

// ✅ Display in UI — convert to local
const localTime = formatInTimeZone(
  appointment.startTime, 
  userTimezone, 
  'MMM d, yyyy h:mm a'
);

// ✅ Database schema — use timestamptz
const appointments = pgTable('appointments', {
  startTime: timestamp('start_time', { withTimezone: true }).notNull(),
});
```

**Standard Error Types**

Define consistent error structures across the codebase:

```typescript
// lib/errors.ts — Standard error structure
type AppError = {
  code: string;        // Machine-readable: 'USER_NOT_FOUND'
  message: string;     // Human-readable: 'User not found'
  cause?: unknown;     // Original error for debugging
  meta?: Record<string, unknown>;  // Additional context
};

// Domain-specific error codes
export const USER_ERRORS = {
  NOT_FOUND: 'USER_NOT_FOUND',
  ALREADY_EXISTS: 'USER_ALREADY_EXISTS',
  INVALID_CREDENTIALS: 'USER_INVALID_CREDENTIALS',
  EMAIL_NOT_VERIFIED: 'USER_EMAIL_NOT_VERIFIED',
} as const;

export const PAYMENT_ERRORS = {
  DECLINED: 'PAYMENT_DECLINED',
  INSUFFICIENT_FUNDS: 'PAYMENT_INSUFFICIENT_FUNDS',
  EXPIRED_CARD: 'PAYMENT_EXPIRED_CARD',
} as const;

// Usage in service
function createUserError(
  code: keyof typeof USER_ERRORS, 
  message: string,
  meta?: Record<string, unknown>
): AppError {
  return { code: USER_ERRORS[code], message, meta };
}

// Example
return { 
  ok: false, 
  error: createUserError('ALREADY_EXISTS', 'A user with this email already exists', { email }) 
};
```

**Structured Logging (Class-Based Logger)**

Use a class-based logger that accumulates context throughout a request lifecycle.

```typescript
import { Logger, createRequestLogger } from '@/lib/logger';

// ❌ Unstructured — hard to search/parse
console.log('User ' + userId + ' created order ' + orderId);

// ❌ Static context — can't accumulate
logger.info('Order created', { orderId });

// ✅ Class-based — context accumulates as you progress
const log = new Logger({ requestId: crypto.randomUUID() });

// Add context as you go through the function
log.addContext({ userId: session.user.id });
log.info('User authenticated');  // Has requestId + userId

log.addContext({ orderId: order.id });
log.info('Order created');  // Has requestId + userId + orderId

log.addContext({ paymentId: payment.id });
log.info('Payment processed');  // Has ALL previous context + paymentId
```

**Full API Handler Example:**

```typescript
export async function POST(req: Request) {
  // 1. Create logger with request ID
  const log = createRequestLogger({
    requestId: crypto.randomUUID(),
    method: 'POST',
    path: '/api/orders',
  });

  // 2. Parse input — add context
  const body = await req.json();
  log.addContext({ action: 'createOrder', itemCount: body.items.length });

  // 3. Auth — add user context
  const session = await getSession();
  if (!session) {
    log.warn('Unauthorized request');
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }
  log.addContext({ userId: session.user.id });

  // 4. Business logic — pass logger to service
  const { data: order, error } = await tryCatch(
    orderService.create(body, log)  // Logger passed to service
  );
  
  if (error) {
    log.error('Order creation failed', { error: error.message });
    return Response.json({ error: 'Failed' }, { status: 500 });
  }

  log.addContext({ orderId: order.id });
  log.info('Order created successfully');
  // Final log has: requestId, method, path, action, itemCount, userId, orderId

  return Response.json({ data: order });
}

// In service — receive logger and continue adding context
async function create(data: OrderInput, log: Logger): Promise<Order> {
  log.addContext({ step: 'orderService.create' });
  
  // Use timing
  const done = log.time('Database insert');
  const order = await db.insert(orders).values(data);
  done({ rowCount: 1 });  // Logs with duration
  
  return order;
}
```

**Key Logger Methods:**

```typescript
const log = new Logger({ requestId });

// Add to context (accumulates)
log.addContext({ userId, orderId });

// Create independent child (parent unaffected)
const childLog = log.child({ step: 'payment' });

// Timing
const done = log.time('Operation');
await doSomething();
done({ extra: 'context' });  // Logs with duration

// Async timing (auto logs start/end)
const result = await log.timeAsync('Fetch user', () => getUser(id));

// Log and return error (for tryCatch pattern)
if (error) {
  return { ok: false, error: log.logError('Failed', error) };
}

// Scoped operation (auto logs start/end with duration)
await log.scope('processPayment', async (scopedLog) => {
  scopedLog.addContext({ amount: 100 });
  // ...
});
```

**Zod Schema Patterns**

Zod schemas should be the source of truth for types:

```typescript
// 1. Schema is source of truth — derive types from it
const userSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  name: z.string().min(2).max(100),
  role: z.enum(['admin', 'user', 'guest']),
  createdAt: z.coerce.date(),
});

// Derive type from schema — single source of truth
type User = z.infer<typeof userSchema>;

// 2. Create/Update schemas extend base
const createUserSchema = userSchema.omit({ id: true, createdAt: true }).extend({
  password: z.string().min(8),
});
type CreateUserInput = z.infer<typeof createUserSchema>;

const updateUserSchema = userSchema.partial().omit({ id: true, createdAt: true });
type UpdateUserInput = z.infer<typeof updateUserSchema>;

// 3. Co-locate schemas with their usage
// api/users/route.ts
const createUserBodySchema = z.object({
  email: z.string().email(),
  name: z.string().min(2),
  password: z.string().min(8),
});

export async function POST(req: Request) {
  const body = await req.json();
  const { data: input, error } = tryCatchSync(() => createUserBodySchema.parse(body));
  if (error) {
    return Response.json({ error: { code: 'VALIDATION_ERROR' } }, { status: 400 });
  }
  // input is fully typed
}

// 4. Use .transform for data transformation
const apiResponseSchema = z.object({
  created_at: z.string(),
}).transform((data) => ({
  createdAt: new Date(data.created_at),
}));
```

**React Performance — useMemo/useCallback Rules**

Don't over-optimize. Use memo hooks only when needed:

```typescript
// useMemo — ONLY for expensive computations
// ❌ Don't memo cheap operations (adds overhead)
const fullName = useMemo(() => `${first} ${last}`, [first, last]);
const isAdmin = useMemo(() => user.role === 'admin', [user.role]);

// ✅ Memo expensive operations
const sortedAndFiltered = useMemo(
  () => items
    .filter(item => item.status === 'active')
    .sort((a, b) => complexSortFunction(a, b))
    .map(item => transformItem(item)),
  [items]
);

// ✅ Memo when creating objects/arrays passed to dependencies
const filters = useMemo(
  () => ({ status: activeStatus, search: searchTerm }),
  [activeStatus, searchTerm]
);
useEffect(() => {
  fetchData(filters);
}, [filters]);  // Now stable reference


// useCallback — ONLY when passing to memoized children
// ❌ Don't useCallback if child isn't memoized (useless)
const handleClick = useCallback(() => setOpen(true), []);
<Button onClick={handleClick} />  // Button not memoized, so useless

// ✅ useCallback when child IS memoized
const MemoizedList = memo(ItemList);

function Parent() {
  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const handleDelete = useCallback((id: string) => {
    deleteItem(id);
  }, [deleteItem]);

  return <MemoizedList onSelect={handleSelect} onDelete={handleDelete} />;
}

// Summary:
// - Don't useMemo/useCallback by default
// - Profile first, optimize second
// - useMemo for expensive computations or stable references
// - useCallback only when passing to memo() children
```

**API Route Handler Structure**

Standard pattern for all API route handlers:

```typescript
// Standard structure for every API route
export async function POST(req: Request) {
  // 1. PARSE & VALIDATE INPUT
  const { data: body, error: parseError } = await tryCatch(req.json());
  if (parseError) {
    return Response.json(
      { error: { code: 'INVALID_JSON', message: 'Invalid request body' } },
      { status: 400 }
    );
  }

  const { data: input, error: validationError } = tryCatchSync(() =>
    createUserSchema.parse(body)
  );
  if (validationError) {
    return Response.json(
      { error: { code: 'VALIDATION_ERROR', message: validationError.message } },
      { status: 400 }
    );
  }

  // 2. AUTHENTICATE (if needed)
  const session = await getSession();
  if (!session) {
    return Response.json(
      { error: { code: 'UNAUTHORIZED', message: 'Authentication required' } },
      { status: 401 }
    );
  }

  // 3. AUTHORIZE (if needed)
  if (!canCreateUser(session.user)) {
    return Response.json(
      { error: { code: 'FORBIDDEN', message: 'Insufficient permissions' } },
      { status: 403 }
    );
  }

  // 4. BUSINESS LOGIC (delegate to service)
  const { data: user, error: serviceError } = await tryCatch(
    userService.create(input)
  );
  if (serviceError) {
    logger.error({ error: serviceError.message, input }, 'Failed to create user');
    return Response.json(
      { error: { code: serviceError.code ?? 'CREATE_FAILED', message: serviceError.message } },
      { status: 400 }
    );
  }

  // 5. RETURN SUCCESS
  logger.info({ userId: user.id }, 'User created');
  return Response.json({ data: user }, { status: 201 });
}
```

**Git Commit Convention**

Use conventional commits for clean history:

```
# Format: type: short description (imperative mood)
# Max 50 chars for subject line

# Types:
feat: add user authentication
fix: resolve payment timeout issue
refactor: extract validation logic into separate module
perf: optimize database queries for dashboard
chore: update dependencies
docs: add API documentation
test: add unit tests for user service
style: format code with prettier

# Examples:
feat: add password reset functionality
fix: prevent duplicate form submissions
refactor: split UserService into smaller modules
perf: add database indexes for common queries
chore: upgrade Next.js to v15
docs: document API rate limits
test: add integration tests for payment flow

# With scope (optional):
feat(auth): add OAuth2 support
fix(api): handle null response from external service
refactor(db): migrate from Prisma to Drizzle
```

### 1. ERROR HANDLING PATTERNS

Pick one and stick to it across the entire codebase.

**Option A: Result Pattern (Recommended for services)**
```typescript
// Define once, use everywhere
type Result<T, E = Error> = 
  | { ok: true; data: T }
  | { ok: false; error: E };

// Service never throws
async function createUser(data: CreateUserInput): Promise<Result<User, CreateUserError>> {
  const existing = await db.user.findByEmail(data.email);
  if (existing) {
    return { ok: false, error: { code: 'EMAIL_EXISTS', message: 'Email already registered' } };
  }
  const user = await db.user.create(data);
  return { ok: true, data: user };
}

// Caller handles explicitly
const result = await createUser(input);
if (!result.ok) {
  return res.status(400).json({ error: result.error });
}
return res.json(result.data);
```

**Option B: Throw + Catch (Simpler, familiar)**
```typescript
// Custom error classes
class AppError extends Error {
  constructor(public code: string, message: string, public statusCode = 400) {
    super(message);
  }
}

// Service throws
async function createUser(data: CreateUserInput): Promise<User> {
  const existing = await db.user.findByEmail(data.email);
  if (existing) {
    throw new AppError('EMAIL_EXISTS', 'Email already registered');
  }
  return db.user.create(data);
}

// Global error handler catches
app.use((err, req, res, next) => {
  if (err instanceof AppError) {
    return res.status(err.statusCode).json({ code: err.code, message: err.message });
  }
  // Unknown error
  console.error(err);
  return res.status(500).json({ code: 'INTERNAL', message: 'Something went wrong' });
});
```

**Questions to establish:**
- Which pattern? Result or throw?
- Standard error codes or free-form?
- How to handle validation errors? (Zod errors → user-friendly messages)
- Logging strategy for errors?

### 2. TYPE PATTERNS

**Strict TypeScript Rules**
```typescript
// tsconfig.json essentials
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,  // array[0] is T | undefined
    "noImplicitReturns": true,
    "exactOptionalPropertyTypes": true
  }
}
```

**Type Organization**
```typescript
// Option A: Co-located with feature
src/features/users/types.ts
src/features/users/user.service.ts

// Option B: Centralized
src/types/user.types.ts
src/types/api.types.ts

// Option C: Inferred from schema (Drizzle/Prisma)
// No separate type files — derive from DB schema
type User = typeof users.$inferSelect;
type NewUser = typeof users.$inferInsert;
```

**Always use `type`, never `interface`**
```typescript
// ❌ Don't use interface
interface User {
  id: string;
  name: string;
}

interface UserCardProps {
  user: User;
  onEdit: () => void;
}

// ✅ Always use type
type User = {
  id: string;
  name: string;
};

type UserCardProps = {
  user: User;
  onEdit: () => void;
};

// Type advantages:
// - Consistent syntax for all type definitions
// - Works with unions: type Status = 'a' | 'b';
// - Works with intersections: type Extended = Base & Extra;
// - Works with mapped types: type Readonly<T> = { readonly [K in keyof T]: T[K] };
// - No declaration merging surprises
```

**Zod + TypeScript Pattern**
```typescript
// Schema is source of truth
const createUserSchema = z.object({
  email: z.string().email(),
  name: z.string().min(2).max(100),
  role: z.enum(['admin', 'user']).default('user'),
});

// Type derived from schema
type CreateUserInput = z.infer<typeof createUserSchema>;

// Validate at boundary
const input = createUserSchema.parse(req.body); // throws ZodError
```

**Questions to establish:**
- Strict mode or relaxed?
- `type` vs `interface`? (Prefer `type` for consistency, or `interface` for declaration merging)
- Where do shared types live?
- Use Zod inference or manual types?

### 3. NAMING CONVENTIONS

**Files**
```
kebab-case.ts        ← Recommended (works everywhere)
PascalCase.tsx       ← React components (optional)
camelCase.ts         ← Also common

Pick one, enforce it.
```

**Functions & Variables**
```typescript
// Functions: camelCase, verb-first
function getUserById(id: string) {}
function createOrder(data: OrderInput) {}
function validateEmail(email: string) {}

// Boolean: is/has/can/should prefix
const isLoading = true;
const hasPermission = false;
const canDelete = user.role === 'admin';

// Constants: SCREAMING_SNAKE for true constants
const MAX_RETRIES = 3;
const API_BASE_URL = process.env.API_URL;

// Env vars: SCREAMING_SNAKE
DATABASE_URL=
NEXT_PUBLIC_API_URL=
```

**Components**
```typescript
// PascalCase, noun-based
function UserCard() {}
function PatientList() {}
function AppointmentModal() {}

// Props: ComponentNameProps
interface UserCardProps {
  user: User;
  onEdit: () => void;
}
```

**Database**
```sql
-- Tables: snake_case, plural
users, appointments, medical_records

-- Columns: snake_case
created_at, updated_at, user_id

-- Foreign keys: singular_table_id
user_id (not users_id)
```

**API Routes**
```
REST: /api/v1/users/:id/appointments
kebab-case for multi-word: /api/v1/medical-records

Actions: POST /api/v1/appointments/:id/confirm
         POST /api/v1/users/:id/reset-password
```

### 4. IMPORT & EXPORT PATTERNS

**Path Aliases (Required)**
```typescript
// tsconfig.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@/components/*": ["./src/components/*"],
      "@/lib/*": ["./src/lib/*"]
    }
  }
}

// Usage
import { Button } from '@/components/ui/button';
import { db } from '@/lib/db';
```

**Import Order (enforce with ESLint)**
```typescript
// 1. Node built-ins
import path from 'path';

// 2. External packages
import { z } from 'zod';
import { eq } from 'drizzle-orm';

// 3. Internal aliases
import { db } from '@/lib/db';
import { UserCard } from '@/components/user-card';

// 4. Relative imports (same feature)
import { validateUser } from './validation';
import type { UserFormProps } from './types';

// 5. Types last (if separate)
import type { User } from '@/types';
```

**Barrel Exports: Generally Avoid**
```typescript
// ❌ Avoid barrel exports (slower builds, circular deps)
// src/components/index.ts
export * from './Button';
export * from './Card';

// ✅ Direct imports (tree-shakeable)
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
```

### 5. FOLDER STRUCTURE PATTERNS

**Option A: Feature-Based (Recommended)**
```
src/
  features/
    auth/
      components/
        login-form.tsx
        signup-form.tsx
      hooks/
        use-auth.ts
      api/
        login.ts
        signup.ts
      auth.service.ts
      auth.types.ts
    patients/
      components/
      hooks/
      api/
      patients.service.ts
  components/
    ui/              ← Shared UI (shadcn)
      button.tsx
      card.tsx
    layout/
      header.tsx
      sidebar.tsx
  lib/
    db.ts
    auth.ts
    utils.ts
  types/
    index.ts         ← Shared types only
```

**Option B: Layer-Based**
```
src/
  components/
    ui/
    forms/
    layout/
  services/
    user.service.ts
    auth.service.ts
  api/
    users/
    auth/
  hooks/
  types/
  utils/
```

**Option C: Next.js App Router Convention**
```
app/
  (auth)/
    login/page.tsx
    signup/page.tsx
  (dashboard)/
    patients/
      page.tsx
      [id]/page.tsx
    appointments/
      page.tsx
  api/
    users/route.ts
    appointments/route.ts
src/
  components/
  lib/
  services/
```

### 6. API DESIGN PATTERNS

**REST Conventions**
```typescript
// Resources are nouns, plural
GET    /api/v1/patients          // List
POST   /api/v1/patients          // Create
GET    /api/v1/patients/:id      // Get one
PATCH  /api/v1/patients/:id      // Partial update
PUT    /api/v1/patients/:id      // Full replace
DELETE /api/v1/patients/:id      // Delete

// Nested resources
GET    /api/v1/patients/:id/appointments
POST   /api/v1/patients/:id/appointments

// Actions (when CRUD doesn't fit)
POST   /api/v1/appointments/:id/confirm
POST   /api/v1/appointments/:id/cancel
POST   /api/v1/users/:id/reset-password
```

**Response Format (Consistent)**
```typescript
// Success
{
  "data": { ... },
  "meta": {
    "page": 1,
    "total": 100
  }
}

// Error
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": [
      { "field": "email", "message": "Invalid email format" }
    ]
  }
}
```

**API Handler Pattern**
```typescript
// Consistent structure for all handlers
export async function POST(req: Request) {
  // 1. Parse & validate input
  const body = await req.json();
  const input = createPatientSchema.safeParse(body);
  if (!input.success) {
    return Response.json(
      { error: { code: 'VALIDATION_ERROR', details: input.error.flatten() } },
      { status: 400 }
    );
  }

  // 2. Auth check
  const session = await getSession();
  if (!session) {
    return Response.json(
      { error: { code: 'UNAUTHORIZED' } },
      { status: 401 }
    );
  }

  // 3. Business logic (delegate to service)
  const result = await patientService.create(input.data);
  if (!result.ok) {
    return Response.json({ error: result.error }, { status: 400 });
  }

  // 4. Return success
  return Response.json({ data: result.data }, { status: 201 });
}
```

### 7. DATABASE PATTERNS

**Schema Design Rules**
```typescript
// Every table has these
const baseColumns = {
  id: uuid('id').defaultRandom().primaryKey(),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
};

// Soft delete pattern (if needed)
const softDelete = {
  deletedAt: timestamp('deleted_at'),
};

// Example table
export const patients = pgTable('patients', {
  ...baseColumns,
  ...softDelete,
  name: varchar('name', { length: 255 }).notNull(),
  email: varchar('email', { length: 255 }).unique(),
  dateOfBirth: date('date_of_birth'),
  // Foreign keys
  clinicId: uuid('clinic_id').references(() => clinics.id),
});
```

**Query Patterns**
```typescript
// Repository/Service pattern
class PatientService {
  async findById(id: string) {
    return db.query.patients.findFirst({
      where: eq(patients.id, id),
      with: { appointments: true },
    });
  }

  async findByClinic(clinicId: string, opts: { page: number; limit: number }) {
    const offset = (opts.page - 1) * opts.limit;
    return db.query.patients.findMany({
      where: and(
        eq(patients.clinicId, clinicId),
        isNull(patients.deletedAt)  // Soft delete filter
      ),
      limit: opts.limit,
      offset,
      orderBy: desc(patients.createdAt),
    });
  }
}
```

**Transaction Pattern**
```typescript
// Wrap related operations
async function createAppointmentWithNotification(data: CreateAppointmentInput) {
  return db.transaction(async (tx) => {
    const appointment = await tx.insert(appointments).values(data).returning();
    await tx.insert(notifications).values({
      userId: data.patientId,
      type: 'APPOINTMENT_CREATED',
      data: { appointmentId: appointment[0].id },
    });
    return appointment[0];
  });
}
```

### 8. COMPONENT PATTERNS

**Avoid useEffect for State Derivation**

useEffect is overused. Most "state sync" can be done without it.

```typescript
// ❌ BAD: useEffect to derive state
function UserList({ users }: { users: User[] }) {
  const [filteredUsers, setFilteredUsers] = useState<User[]>([]);
  const [search, setSearch] = useState('');

  useEffect(() => {
    setFilteredUsers(users.filter(u => u.name.includes(search)));
  }, [users, search]);

  return <List users={filteredUsers} />;
}

// ✅ GOOD: Derive during render
function UserList({ users }: { users: User[] }) {
  const [search, setSearch] = useState('');
  
  // Computed value, no effect needed
  const filteredUsers = users.filter(u => u.name.includes(search));

  return <List users={filteredUsers} />;
}

// ✅ GOOD: useMemo if expensive
function UserList({ users }: { users: User[] }) {
  const [search, setSearch] = useState('');
  
  const filteredUsers = useMemo(
    () => users.filter(u => u.name.toLowerCase().includes(search.toLowerCase())),
    [users, search]
  );

  return <List users={filteredUsers} />;
}
```

**When useEffect IS appropriate:**
- Fetching data (though prefer React Query / server components)
- Subscriptions (WebSocket, event listeners)
- DOM manipulation that can't be done declaratively
- Analytics/logging on mount
- Syncing with external systems (non-React)

**When to AVOID useEffect:**
- Deriving state from props or other state → compute during render
- Transforming data → compute or useMemo
- Resetting state when props change → use `key` prop instead
- Handling user events → use event handlers
- Initializing state from props → use initializer function

```typescript
// ❌ BAD: Reset state with useEffect
function Form({ userId }: { userId: string }) {
  const [formData, setFormData] = useState({});
  
  useEffect(() => {
    setFormData({});  // Reset when userId changes
  }, [userId]);
}

// ✅ GOOD: Use key to reset
function ParentComponent() {
  return <Form key={userId} userId={userId} />;
}

// ❌ BAD: Initialize from props with useEffect
function Editor({ initialContent }: { initialContent: string }) {
  const [content, setContent] = useState('');
  
  useEffect(() => {
    setContent(initialContent);
  }, []);
}

// ✅ GOOD: Initialize in useState
function Editor({ initialContent }: { initialContent: string }) {
  const [content, setContent] = useState(initialContent);
}
```

**Component Structure**
```typescript
// Consistent ordering within component files
// 1. Imports
// 2. Types (using type, not interface)
// 3. Component (using function keyword)
// 4. Subcomponents (if small)
// 5. Export

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import type { Patient } from '@/types';

type PatientCardProps = {
  patient: Patient;
  onEdit: (id: string) => void;
};

export function PatientCard({ patient, onEdit }: PatientCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div>
      {/* ... */}
    </div>
  );
}
```

**Prop Patterns**
```typescript
// Destructure with defaults, use function keyword
function Button({ 
  variant = 'primary', 
  size = 'md', 
  disabled = false,
  children,
  ...props 
}: ButtonProps) {
  return <button {...props}>{children}</button>;
}

// Forward ref - exception where arrow is acceptable inside forwardRef
const Input = forwardRef<HTMLInputElement, InputProps>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn(baseStyles, className)} {...props} />;
  }
);

// Compound components
function Select({ children }: SelectProps) {
  return <div>{children}</div>;
}

Select.Trigger = function SelectTrigger() { /* ... */ };
Select.Content = function SelectContent() { /* ... */ };
Select.Item = function SelectItem() { /* ... */ };
```

**Hook Patterns**
```typescript
// Naming: use + noun/verb
// Always use function keyword
function usePatients(clinicId: string) {
  const query = useQuery({ /* ... */ });
  
  return {
    patients: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

function useCreateAppointment() {
  return useMutation({ /* ... */ });
}

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);
  
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  
  return debouncedValue;
}

// Return tuple for simple state
function useToggle(initial = false): [boolean, () => void] {
  const [value, setValue] = useState(initial);
  const toggle = useCallback(() => setValue(v => !v), []);
  return [value, toggle];
}
```

### 9. ASYNC PATTERNS

**Server-Side Data Fetching (Next.js)**
```typescript
// Page component fetches data
export default async function PatientsPage() {
  const patients = await patientService.findAll();
  return <PatientList patients={patients} />;
}

// With error handling
export default async function PatientPage({ params }: { params: { id: string } }) {
  const patient = await patientService.findById(params.id);
  if (!patient) {
    notFound();
  }
  return <PatientDetail patient={patient} />;
}
```

**Client-Side Data Fetching**
```typescript
// TanStack Query pattern
function usePatients() {
  return useQuery({
    queryKey: ['patients'],
    queryFn: () => fetch('/api/patients').then(r => r.json()),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Mutations
function useCreatePatient() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: CreatePatientInput) =>
      fetch('/api/patients', {
        method: 'POST',
        body: JSON.stringify(data),
      }).then(r => r.json()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
    },
  });
}
```

### 10. SECURITY PATTERNS

**Input Validation (Always at boundaries)**
```typescript
// API route entry point
const input = schema.safeParse(body);
if (!input.success) return errorResponse(input.error);

// Never trust client data deeper in the stack
```

**Auth Checks**
```typescript
// Middleware for protected routes
export async function middleware(request: NextRequest) {
  const session = await getSession(request);
  if (!session && request.nextUrl.pathname.startsWith('/dashboard')) {
    return NextResponse.redirect(new URL('/login', request.url));
  }
}

// Service-level authorization
async function updatePatient(userId: string, patientId: string, data: UpdatePatientInput) {
  const patient = await db.query.patients.findFirst({ where: eq(patients.id, patientId) });
  
  // Check ownership or role
  if (patient?.userId !== userId && !await hasRole(userId, 'admin')) {
    return { ok: false, error: { code: 'FORBIDDEN' } };
  }
  
  // Proceed with update
}
```

**SQL Injection Prevention**
```typescript
// ✅ Parameterized (Drizzle/Prisma do this automatically)
db.query.users.findFirst({ where: eq(users.email, userInput) });

// ❌ Never interpolate user input
db.execute(`SELECT * FROM users WHERE email = '${userInput}'`); // DANGER
```

**Environment Variables**
```typescript
// Validate at startup
import { z } from 'zod';

const envSchema = z.object({
  DATABASE_URL: z.string().url(),
  JWT_SECRET: z.string().min(32),
  NEXT_PUBLIC_API_URL: z.string().url(),
});

export const env = envSchema.parse(process.env);

// Use validated env
import { env } from '@/lib/env';
console.log(env.DATABASE_URL); // Type-safe
```

### 11. LOGGING & OBSERVABILITY

**Structured Logging (Class-Based Logger)**
```typescript
import { Logger, createRequestLogger } from '@/lib/logger';

// Create logger with request context
const log = createRequestLogger({ requestId: crypto.randomUUID() });

// Add context as you progress (accumulates)
log.addContext({ userId: session.user.id });
log.addContext({ orderId: order.id });

// All logs include accumulated context
log.info('Order created');
// Output: {"level":"info","message":"Order created","requestId":"...","userId":"...","orderId":"...","timestamp":"..."}

log.error('Payment failed', { error: err.message, stack: err.stack });
```

**Request Logging with Accumulating Context**
```typescript
export async function handler(req: Request) {
  const log = createRequestLogger({
    requestId: crypto.randomUUID(),
    method: req.method,
    path: new URL(req.url).pathname,
  });

  // Add user after auth
  const session = await getSession();
  if (session) log.addContext({ userId: session.userId });

  // Time the operation
  const done = log.time('Request processed');
  const result = await processRequest(req, log);
  done({ status: result.status });
  
  return result;
}
```

### 12. DOCUMENTATION PATTERNS

**Code Comments**
```typescript
// ✅ Explain WHY, not WHAT
// We retry 3 times because the payment gateway has intermittent 503s
const MAX_RETRIES = 3;

// ❌ Useless comment
// Set max retries to 3
const MAX_RETRIES = 3;

// ✅ Document non-obvious behavior
/**
 * Returns appointments for the next 7 days.
 * Excludes cancelled appointments.
 * Results are cached for 5 minutes.
 */
async function getUpcomingAppointments(patientId: string) {}
```

**README per Feature**
```markdown
# features/appointments/README.md

## Overview
Handles appointment scheduling, rescheduling, and cancellation.

## Key Files
- `appointments.service.ts` - Business logic
- `appointments.schema.ts` - Validation schemas
- `components/` - UI components

## Domain Rules
- Appointments must be at least 24h in advance
- Max 3 appointments per patient per day
- Cancellation allowed up to 2h before

## API Endpoints
- POST /api/appointments - Create
- PATCH /api/appointments/:id - Update
- POST /api/appointments/:id/cancel - Cancel
```

---

## Conducting Discovery

### Opening

```
"Before we write any code, I want to understand what we're building and make sure we make good foundational decisions. This might take 15-30 minutes but will save hours later. Let's start with the big picture — what are we building and who is it for?"
```

### During Discovery

- Take notes mentally, summarize periodically
- Group related decisions: "So for the data layer, we're going with Postgres on Supabase with Drizzle ORM. That gives us..."
- Flag decisions that need more thought: "Let's come back to the auth flow once we understand the user types better"
- Challenge weak reasoning: "You said 'because everyone uses it' — is that the right reason for your specific case?"

### Closing Discovery

```
"Let me summarize what we've decided:

**Project**: [One sentence]
**Stack**: [Frontend] + [Backend] + [Database]
**Auth**: [Approach]
**Hosting**: [Where]
**Key patterns**: [2-3 important conventions]

**Features for MVP**:
1. [Feature]
2. [Feature]
...

Does this capture it? Anything we should revisit before we start building?"
```

---

## Output: What to Produce

After discovery, create these in the project:

### 1. CLAUDE.md (or PROJECT.md)

```markdown
# Project: [Name]

## Overview
[2-3 sentences on what this is]

## Tech Stack
- Frontend: Next.js 15 (App Router)
- Backend: Next.js API Routes
- Database: PostgreSQL (Supabase)
- ORM: Drizzle
- Auth: Lucia + GitHub OAuth
- Styling: Tailwind + shadcn/ui
- Hosting: Vercel

## Key Decisions
- Using Result<T> pattern, services never throw
- All dates UTC, convert in frontend
- Feature-based folder structure
- Direct imports, no barrel exports

## Code Patterns
[Document specific patterns agreed on]

## Features
- [ ] Auth (GitHub OAuth)
- [ ] User profile
- [ ] ...
```

### 2. PATTERNS.md (Code Patterns Reference)

```markdown
# Code Patterns

## Core Rules (Always Follow)

### DRY — Don't Repeat Yourself
If you write the same logic twice, extract it.

### TypeScript
\`\`\`typescript
// Always use type, never interface
type User = {
  id: string;
  name: string;
};

// Always use function keyword
function getUser(id: string) {
  return db.users.find(id);
}

function UserCard({ user }: UserCardProps) {
  return <div>{user.name}</div>;
}

// No non-null assertions
// ❌ user!.name
// ✅ user?.name ?? 'Unknown'

// No any type — define proper types, use unknown and narrow if types can't be defined
// ❌ data: any
// ✅ data: ApiResponse (define the type)
// ✅ data: unknown (if types can't be defined, then narrow)
\`\`\`

### React
\`\`\`typescript
// No useEffect for state derivation
// ❌ useEffect(() => setFiltered(items.filter(...)), [items])
// ✅ const filtered = items.filter(...)
// ✅ const filtered = useMemo(() => items.filter(...), [items])
\`\`\`

### Error Handling — Use tryCatch Utility

\`\`\`typescript
// lib/try-catch.ts — Required in every project
type Success<T> = { data: T; error: null };
type Failure<E> = { data: null; error: E };
type Result<T, E = Error> = Success<T> | Failure<E>;

export async function tryCatch<T, E = Error>(
  promise: Promise<T>,
): Promise<Result<T, E>> {
  try {
    const data = await promise;
    return { data, error: null };
  } catch (error) {
    return { data: null, error: error as E };
  }
}

// Also has: tryCatchSync, withTryCatch, tryCatchRetry, tryCatchWithTimeout
\`\`\`

\`\`\`typescript
// Usage
const { data: user, error } = await tryCatch(getUser(id));
if (error) {
  logger.error({ err: error }, 'Failed');
  return null;
}

// Sync: const { data, error } = tryCatchSync(() => JSON.parse(str));
// Retry: await tryCatchRetry(() => fetch(url), { maxRetries: 3 });
// Timeout: await tryCatchWithTimeout(fetch(url), 5000);
\`\`\`

### File Size Limits

| File Type | Max LOC |
|-----------|---------|
| Components | 150-200 |
| Hooks | 80-100 |
| API Routes | 80-100 |
| Services | 200-250 |
| Utils | 100-150 |
| Types | 150-200 |

When file exceeds limit → split into folder with multiple files.

### Code Quality
- No comments unless logic is complex (explain WHY, not WHAT)
- No emoji in logs or code
- Use IDE TypeScript integration to check errors for small changes, use `typecheck` for big changes if present
- Review code after making changes
- Run /code-review after tasks

### Database
- Use Drizzle query builder, not raw SQL
- Never run db:push, db:migrate, db:generate without permission

## Best Practices

\`\`\`typescript
// Small functions — one function = one job
// If too big, divide and compose
async function handleOrder(data) {
  const validated = validateOrder(data);      // one job
  const order = await createOrder(validated); // one job
  await sendConfirmation(order);              // one job
  return order;
}

// Early returns over nesting
if (!user) return null;
if (!user.isActive) return null;
return processUser(user);

// Parallel async when independent
const [user, posts] = await Promise.all([getUser(id), getPosts(id)]);

// No magic numbers
const MAX_RETRIES = 3;
const ONE_DAY_MS = 24 * 60 * 60 * 1000;

// Meaningful names
const activeUsers = users.filter(u => u.isActive);  // not "arr" or "data"

// Boolean prefixes
const isLoading = true;
const hasPermission = false;
const canDelete = user.role === 'admin';

// const over let
const user = await getUser(id);

// No nested ternaries — use lookup objects or early returns

// Named exports
export function UserCard() {}  // not export default

// Destructuring
function greet({ firstName, lastName }: User) {}

// Template literals
const msg = \`Hello \${name}\`;  // not 'Hello ' + name

// Structured logging (pino) — context FIRST, then message
logger.info({ userId, email }, 'User created');
\`\`\`

## Conventions

### Null vs Undefined
- \`null\` = intentional absence ("I set this to nothing")
- \`undefined\` = optional/not set

### Dates
- Store as UTC in database
- Transport as ISO strings in API
- Convert to local only in UI

### Types
- Use \`import type\` for type-only imports
- Zod schema = source of truth, derive types with \`z.infer<>\`

### Git Commits
\`feat:\`, \`fix:\`, \`refactor:\`, \`chore:\`, \`docs:\`, \`test:\`

## Naming
- Files: kebab-case (\`user-service.ts\`)
- Components: PascalCase (\`UserCard.tsx\`)
- Functions: camelCase, verb-first (\`getUserById\`)
- DB tables: snake_case, plural (\`medical_records\`)
- Env vars: SCREAMING_SNAKE (\`DATABASE_URL\`)

## Imports
Order: node → external → @/ aliases → relative → types

\`\`\`typescript
import path from 'path';
import { z } from 'zod';
import { db } from '@/lib/db';
import { validate } from './utils';
import type { User } from '@/types';
\`\`\`

## Service Layer — Result Pattern

\`\`\`typescript
type Result<T, E = AppError> = { ok: true; data: T } | { ok: false; error: E };

async function createUser(data): Promise<Result<User>> {
  if (exists) return { ok: false, error: { code: 'EXISTS' } };
  return { ok: true, data: user };
}
\`\`\`

## API Responses

\`\`\`typescript
// Success
{ "data": { ... } }

// Error
{ "error": { "code": "VALIDATION_ERROR", "message": "...", "details": [...] } }
\`\`\`

## Required Files
- \`lib/try-catch.ts\` — tryCatch utilities
- \`lib/errors.ts\` — standard error types
- \`lib/logger.ts\` — class-based Logger with accumulating context
- \`lib/env.ts\` — validated env vars

## After Task Complete
1. Use IDE to check for TS errors in changed files (use \`typecheck\` for big changes if present)
2. Review code logic
3. Run /code-review command
```

### 3. Initial Folder Structure

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

### 4. Required Utility Files

Create these files in every new project:

**lib/try-catch.ts**
```typescript
type Success<T> = { data: T; error: null };
type Failure<E> = { data: null; error: E };
type Result<T, E = Error> = Success<T> | Failure<E>;

// Async operations
export async function tryCatch<T, E = Error>(
  promise: Promise<T>,
): Promise<Result<T, E>> {
  try {
    const data = await promise;
    return { data, error: null };
  } catch (error) {
    return { data: null, error: error as E };
  }
}

// Sync operations (JSON.parse, etc.)
export function tryCatchSync<T, E = Error>(
  fn: () => T,
): Result<T, E> {
  try {
    const data = fn();
    return { data, error: null };
  } catch (error) {
    return { data: null, error: error as E };
  }
}

// Wrap existing functions to make them safe
export function withTryCatch<TArgs extends unknown[], TReturn, E = Error>(
  fn: (...args: TArgs) => Promise<TReturn>,
): (...args: TArgs) => Promise<Result<TReturn, E>> {
  return async (...args: TArgs) => tryCatch<TReturn, E>(fn(...args));
}

// Retry with exponential backoff
export async function tryCatchRetry<T, E = Error>(
  promise: () => Promise<T>,
  options: { maxRetries?: number; delayMs?: number; backoff?: boolean } = {},
): Promise<Result<T, E>> {
  const { maxRetries = 3, delayMs = 1000, backoff = true } = options;
  let lastError: E | null = null;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const { data, error } = await tryCatch<T, E>(promise());
    if (!error) return { data, error: null };
    lastError = error;
    if (attempt < maxRetries) {
      const delay = backoff ? delayMs * Math.pow(2, attempt) : delayMs;
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  return { data: null, error: lastError as E };
}

// With timeout
export async function tryCatchWithTimeout<T, E = Error>(
  promise: Promise<T>,
  timeoutMs: number,
): Promise<Result<T, E>> {
  const timeout = new Promise<never>((_, reject) => {
    setTimeout(() => reject(new Error(`Timed out after ${timeoutMs}ms`)), timeoutMs);
  });
  return tryCatch<T, E>(Promise.race([promise, timeout]));
}
```

**lib/env.ts**
```typescript
import { z } from 'zod';

const envSchema = z.object({
  DATABASE_URL: z.string().url(),
  // Add other required env vars
});

export const env = envSchema.parse(process.env);
```

**lib/errors.ts**
```typescript
// Standard error structure
export type AppError = {
  code: string;        // Machine-readable: 'USER_NOT_FOUND'
  message: string;     // Human-readable
  cause?: unknown;     // Original error
  meta?: Record<string, unknown>;
};

// Domain error codes (add per domain)
export const USER_ERRORS = {
  NOT_FOUND: 'USER_NOT_FOUND',
  ALREADY_EXISTS: 'USER_ALREADY_EXISTS',
  INVALID_CREDENTIALS: 'USER_INVALID_CREDENTIALS',
} as const;

// Helper to create errors
export function createError(
  code: string,
  message: string,
  meta?: Record<string, unknown>
): AppError {
  return { code, message, meta };
}
```

**lib/logger.ts**
```typescript
// pnpm add pino pino-pretty
// Class-based logger with accumulating context, pino under the hood

import pino from 'pino';
import type { Logger as PinoLogger } from 'pino';

const baseLogger: PinoLogger = pino({
  level: process.env.LOG_LEVEL ?? (process.env.NODE_ENV === 'production' ? 'info' : 'debug'),
  transport: process.env.NODE_ENV !== 'production'
    ? { target: 'pino-pretty', options: { colorize: true } }
    : undefined,
});

export class Logger {
  private context: Record<string, unknown>;
  private pino: PinoLogger;

  constructor(initialContext = {}, pinoInstance?: PinoLogger) {
    this.context = { ...initialContext };
    this.pino = pinoInstance ?? baseLogger;
  }

  addContext(context: Record<string, unknown>): this {
    this.context = { ...this.context, ...context };
    return this;
  }

  child(additionalContext = {}): Logger {
    return new Logger({ ...this.context, ...additionalContext }, this.pino);
  }

  info(message: string, context?: Record<string, unknown>): void {
    this.pino.info({ ...this.context, ...context }, message);
  }

  error(message: string, context?: Record<string, unknown>): void {
    this.pino.error({ ...this.context, ...context }, message);
  }

  // Also: warn(), debug(), trace(), fatal(), time(), timeAsync(), scope()
}

export const logger = new Logger();
export function createRequestLogger(ctx = {}) {
  return new Logger({ requestId: crypto.randomUUID(), ...ctx });
}
```

### 5. Config Files

- `tsconfig.json` with strict mode + path aliases
- `.env.example` with all required vars
- `drizzle.config.ts` (if using Drizzle)
- `.eslintrc` with import ordering
- `.prettierrc` for formatting

---

## Tips

1. **Don't rush** — 30 minutes of discovery saves 3 hours of refactoring

2. **It's OK to say "I don't know yet"** — Mark it and revisit

3. **Defaults are fine** — Not every decision needs deep thought. "Tailwind? Sure, unless you hate it."

4. **Write it down** — Decisions not documented are decisions forgotten

5. **Revisit when wrong** — Discovery isn't permanent. Update as you learn.

---

## Patterns Checklist

Before writing code, ensure these patterns are established:

### Must Have (Establish in Discovery)

**Core Principles**
- [ ] DRY principle — no duplicate logic
- [ ] `type` over `interface` — always
- [ ] `function` keyword over arrow functions — always
- [ ] useEffect only when necessary — no state derivation
- [ ] Use `tryCatch` utility — no try-catch blocks

**TypeScript Strictness**
- [ ] No non-null assertions (`!.`) — use proper null handling
- [ ] No `any` type — define proper types, use `unknown` and narrow if types can't be defined
- [ ] Check IDE for TS errors for small changes, use `typecheck` for big changes if available
- [ ] Strict mode enabled in tsconfig
- [ ] Use `import type` for type-only imports

**Code Quality**
- [ ] No comments unless logic is complex
- [ ] No emoji in logs or code
- [ ] Review code after changes
- [ ] Run code-review command after tasks

**Required Utility Files**
- [ ] `lib/try-catch.ts` — tryCatch utility
- [ ] `lib/logger.ts` — class-based Logger with pino (no console.log)
- [ ] `lib/env.ts` — validated environment variables
- [ ] `lib/errors.ts` — standard error types

**Patterns**
- [ ] Error handling (Result pattern for services)
- [ ] File naming convention
- [ ] Folder structure approach
- [ ] Import organization & path aliases
- [ ] API response format
- [ ] Database naming conventions
- [ ] Null vs undefined convention (null = intentional absence)
- [ ] Date handling (UTC storage, ISO transport, local display)
- [ ] Zod schemas as source of truth for types
- [ ] Git commit convention (conventional commits)

**Best Practices**
- [ ] Early returns over nested conditionals
- [ ] No magic numbers/strings — use constants
- [ ] Meaningful variable names
- [ ] Boolean names with is/has/can/should
- [ ] const over let
- [ ] async/await over .then()
- [ ] No nested ternaries
- [ ] Named exports over default exports
- [ ] No unused variables or imports
- [ ] Use destructuring
- [ ] Template literals over concatenation
- [ ] No console.log in production
- [ ] Keep functions small — one function = one job, compose larger from smaller
- [ ] Keep files small — refactor when over LOC limit
- [ ] Parallel async when operations are independent (Promise.all)
- [ ] Structured logging with pino (context first, message second)
- [ ] useMemo/useCallback only when needed (expensive ops, memoized children)

**File Size Limits**
- [ ] React Components: 150-200 LOC max
- [ ] Custom Hooks: 80-100 LOC max
- [ ] API Routes: 80-100 LOC max
- [ ] Services: 200-250 LOC max
- [ ] Utilities: 100-150 LOC max
- [ ] Types: 150-200 LOC max

**Database**
- [ ] Use Drizzle query builder, not raw SQL
- [ ] Never run migrations without permission
- [ ] Store dates as UTC (timestamptz)

### Should Have (Establish Early)
- [ ] Component file structure
- [ ] Hook naming & return patterns
- [ ] Logging approach (structured with context)
- [ ] Auth check patterns
- [ ] Validation strategy (where, how)
- [ ] Git commit format (conventional commits)
- [ ] API handler structure (validate → auth → business logic → response)

### Nice to Have (Can Evolve)
- [ ] Documentation standards
- [ ] Testing patterns
- [ ] Performance monitoring
- [ ] Feature flag approach

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    DISCOVERY CHECKLIST                       │
├─────────────────────────────────────────────────────────────┤
│ OVERVIEW                                                     │
│ □ What are we building? For whom?                           │
│ □ Success criteria?                                         │
│ □ Timeline? MVP deadline?                                   │
│ □ Team size?                                                │
├─────────────────────────────────────────────────────────────┤
│ TECH STACK                                                   │
│ □ Frontend framework                                        │
│ □ Backend approach                                          │
│ □ Database + ORM                                            │
│ □ Auth solution                                             │
│ □ Hosting target                                            │
├─────────────────────────────────────────────────────────────┤
│ CORE RULES (Always Follow)                                  │
│ ✓ DRY — extract duplicate logic                             │
│ ✓ type over interface                                       │
│ ✓ function keyword, not arrows                              │
│ ✓ No useEffect for state derivation                         │
│ ✓ No non-null assertions (!.)                               │
│ ✓ No any type — define types, unknown if can't              │
│ ✓ Use tryCatch utility, no try-catch blocks                 │
│ ✓ Use import type for type-only imports                     │
│ ✓ No comments unless complex                                │
│ ✓ No emoji in logs/code                                     │
│ ✓ IDE for TS errors (typecheck for big changes)             │
│ ✓ Review code after changes                                 │
│ ✓ Use Drizzle functions, not raw SQL                        │
│ ✓ Don't run db migrations without asking                    │
│ ✓ Small functions — one job each, compose larger            │
│ ✓ Keep files small — refactor when too large                │
├─────────────────────────────────────────────────────────────┤
│ FILE SIZE LIMITS (LOC)                                       │
│ Components: 150-200  │  Hooks: 80-100  │  Routes: 80-100    │
│ Services: 200-250    │  Utils: 100-150 │  Types: 150-200    │
├─────────────────────────────────────────────────────────────┤
│ CODE QUALITY                                                 │
│ ✓ Early returns over nesting                                │
│ ✓ No magic numbers — use constants                          │
│ ✓ Meaningful names (no x, temp, data)                       │
│ ✓ Boolean: isX, hasX, canX, shouldX                         │
│ ✓ const over let                                            │
│ ✓ Parallel async (Promise.all) when independent             │
│ ✓ No nested ternaries                                       │
│ ✓ Named exports over default                                │
│ ✓ No unused imports/variables                               │
│ ✓ Use destructuring                                         │
│ ✓ Template literals over concatenation                      │
│ ✓ Structured logging with pino (context, message)            │
│ ✓ useMemo/useCallback only when needed                      │
├─────────────────────────────────────────────────────────────┤
│ PATTERNS                                                     │
│ □ Error handling (Result pattern for services)              │
│ □ File naming (kebab-case)                                  │
│ □ Folder structure (feature vs layer)                       │
│ □ Import order & aliases                                    │
│ □ API response format                                       │
│ □ DB conventions (snake_case, UTC dates)                    │
│ □ null = intentional absence, undefined = optional          │
│ □ Zod schema = source of truth for types                    │
│ □ Git: conventional commits                                 │
├─────────────────────────────────────────────────────────────┤
│ REQUIRED FILES                                               │
│ □ lib/try-catch.ts — tryCatch, tryCatchSync, retry, timeout │
│ □ lib/logger.ts — class-based Logger (pino under hood)       │
│ □ lib/env.ts — validated environment vars                   │
│ □ lib/errors.ts — standard error types                      │
├─────────────────────────────────────────────────────────────┤
│ AFTER TASK COMPLETE                                          │
│ □ IDE for TS errors (typecheck for big changes if present)  │
│ □ Review code logic one more time                           │
│ □ Run /code-review command                                  │
└─────────────────────────────────────────────────────────────┘
```
