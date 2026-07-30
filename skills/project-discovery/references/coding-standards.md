# Code Patterns

These are the project's laws. They hold in every file, in every session.

This file ships as the project's `PATTERNS.md`. Copy across only the rules the
chosen stack actually uses, and delete the rest.

## 1. TypeScript

**DRY.** If you write the same logic twice, extract it — utilities, API call
patterns, validation logic, UI components, type definitions.

**Always use `type`, never `interface`** — one syntax for every definition, and it
covers unions, intersections and mapped types. **`function` for declarations,
arrows for inline callbacks and JSX handlers.**

```typescript
type User = { id: string; name: string };
type UserCardProps = { user: User; onEdit: () => void };
type Status = 'pending' | 'active' | 'cancelled';
type UserWithPosts = User & { posts: Post[] };
type Nullable<T> = T | null;

async function getUser(id: string) { return db.users.find(id); }
function UserCard({ user }: UserCardProps) { return <div>{user.name}</div>; }

items.map(item => item.id);
<button onClick={() => setOpen(true)} />;
```

**Narrow before access: guard, early-return, or `?? fallback`.** No non-null
assertions (`!.`).

```typescript
const name = user?.name ?? 'Unknown';
if (!user) return 'Guest';
return user.name;  // TypeScript knows it's defined
```

**Type every value; reach for `unknown` and narrow when the shape is genuinely
open** — `typeof` for primitives, a type guard (`isUser(input)`) for complex
shapes, generics where the caller decides.

**Use `import type` for type-only imports** — erased at compile time, no
circular-dependency surprises. Inline form:
`import { UserService, type CreateUserInput } from './user'`.

**`null` = intentional absence, `undefined` = optional or never set.**

```typescript
type User = {
  deletedAt: Date | null;  // explicitly set to nothing
  nickname?: string;       // may not exist
};
```

**Strict tsconfig.**

```json
{ "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitReturns": true,
    "exactOptionalPropertyTypes": true } }
```

**Zod schemas are the source of truth for types** — derive with `z.infer`, reuse
with `.omit()`, `.extend()` and `.partial()`.

```typescript
const userSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  role: z.enum(['admin', 'user', 'guest']),
  createdAt: z.coerce.date(),
});
type User = z.infer<typeof userSchema>;

const createUserSchema = userSchema.omit({ id: true, createdAt: true })
  .extend({ password: z.string().min(8) });
type CreateUserInput = z.infer<typeof createUserSchema>;
```

**Where types live** — pick one: co-located with the feature
(`src/features/users/types.ts`), centralized (`src/types/user.types.ts`), or
inferred from the DB schema (`type User = typeof users.$inferSelect`).

**Run the project's type-check command and fix every error before reporting the
task complete.** Run `/done` after completing a task.

## 2. Functions & Files

**Functions are single-responsibility; compose them into operations.** 5-20 lines
ideally, 30-40 at most. If you need comments to separate sections inside a
function, or you can't name it clearly, it is doing too much.

**Split a file when it loses cohesion** — the table is the tripwire, not the rule.

| File Type | Max LOC | When to Split |
|-----------|---------|---------------|
| React Components | 150-200 | Extract sub-components, hooks, utils |
| Custom Hooks | 80-100 | Split into smaller hooks, extract helpers |
| API Routes/Handlers | 80-100 | Extract to service layer |
| Service files | 200-250 | Split by domain/entity |
| Utility files | 100-150 | Group by functionality |
| Type definition files | 150-200 | Split by domain |
| Config files | 100 | Split by concern |

**Prefer early returns over nesting; no nested ternaries** — use an object lookup
or a function with early returns.

```typescript
function processUser(user: User | null) {
  if (!user) return null;
  if (!user.isActive) return null;
  return doSomething(user);
}

const STATUS_LABELS: Record<string, string> = { active: 'Active', pending: 'Pending' };
const label = STATUS_LABELS[status] ?? 'Unknown';
```

**Smaller rules that hold everywhere:**

- Return a new object rather than mutating a parameter: `{ ...input, timestamp: Date.now() }`.
- Named exports over default exports — explicit at the import site, refactor-friendly.
- No magic numbers or strings — `const ONE_DAY_MS = 24 * 60 * 60 * 1000;`,
  `const ROLES = { ADMIN: 'admin' } as const;`.
- Meaningful names — `currentDate`, `authenticatedUser`, `activeItems`. Single
  letters only for loop indices, callbacks and generics.
- Booleans read as questions — `isLoading`, `hasData`, `canDelete`, `shouldRefresh`.
- `const` over `let`; `let` only where reassignment happens.
- Optional chaining and nullish coalescing — `user?.address?.street`,
  `user.name ?? 'Unknown'` (`||` swallows empty strings).
- Destructure instead of repeated property access; template literals over concatenation.
- No unused variables or imports.
- Comment the WHY — the constraint, the workaround, the gotcha. The code states the what.
- No emoji in logs or code.

## 3. Error Handling

Pick one pattern and hold it across the entire codebase.

**Option A: Result pattern (recommended for services).** The service never
throws; the caller cannot ignore the failure branch.

```typescript
// Defined once, used everywhere
type Result<T, E = Error> =
  | { ok: true; data: T }
  | { ok: false; error: E };

async function createUser(data: CreateUserInput): Promise<Result<User, AppError>> {
  const existing = await db.user.findByEmail(data.email);
  if (existing) {
    return { ok: false, error: { code: 'EMAIL_EXISTS', message: 'Email already registered' } };
  }
  return { ok: true, data: await db.user.create(data) };
}

const result = await createUser(input);
if (!result.ok) return res.status(400).json({ error: result.error });
return res.json(result.data);
```

**Option B: throw + catch.** An `AppError` class carrying `code` and
`statusCode`, thrown by services, caught by one global handler that maps
`instanceof AppError` to a response and everything else to a logged 500.

**Use the `tryCatch` utility instead of raw try-catch blocks.** It returns
`{ data, error }` — the error is a value you must destructure, so you cannot skip
it. It lives in `lib/try-catch.ts`.

```typescript
import { tryCatch, tryCatchSync, tryCatchRetry, tryCatchWithTimeout } from '@/lib/try-catch';

const { data: response, error: fetchError } = await tryCatch(fetch(`/api/users/${id}`));
if (fetchError) {
  logger.error({ id, error: fetchError.message }, 'Failed to fetch user');
  return null;
}

// Sync:    const { data, error } = tryCatchSync(() => JSON.parse(str));
// Retry:   await tryCatchRetry(() => fetch(url), { maxRetries: 3, backoff: true });
// Timeout: await tryCatchWithTimeout(fetch(url), 5000);
```

**Errors carry a machine-readable `code` and a human-readable `message`.** The
`AppError` shape and the per-domain code constants (`USER_ERRORS.NOT_FOUND`) live
in `lib/errors.ts`.

## 4. Naming

- Files: kebab-case (`user-service.ts`) — pick one convention and enforce it.
- Functions: camelCase, verb-first (`getUserById`, `createOrder`).
- Components: PascalCase, noun-based (`UserCard`); props are `UserCardProps`.
- Constants and env vars: SCREAMING_SNAKE (`MAX_RETRIES`, `DATABASE_URL`).
- DB tables: snake_case plural (`medical_records`); columns snake_case
  (`created_at`); foreign keys singular (`user_id`, not `users_id`).
- Routes: `/api/v1/users/:id/appointments`, kebab-case for multi-word
  (`/api/v1/medical-records`), verb suffix for actions
  (`POST /api/v1/appointments/:id/confirm`).

## 5. Imports & Folder Structure

**Path aliases, always** — `"paths": { "@/*": ["./src/*"] }` in tsconfig.

**Import order (enforce with ESLint):** node built-ins → external packages → `@/`
aliases → relative → types.

```typescript
import path from 'path';
import { z } from 'zod';
import { db } from '@/lib/db';
import { validateUser } from './validation';
import type { User } from '@/types';
```

**Import directly from the module: `@/components/ui/button`.** Barrel files slow
builds and invite circular dependencies.

**Folder structure — pick one.**

```
A: Feature-based (recommended)     B: Layer-based        C: Next.js App Router
src/features/auth/                 src/components/       app/(auth)/login/page.tsx
  {components,hooks,api}/            {ui,forms,layout}/  app/(dashboard)/patients/
  auth.service.ts                  src/services/           [id]/page.tsx
  auth.types.ts                    src/api/              app/api/users/route.ts
src/components/{ui,layout}/        src/hooks/            src/{components,lib,
src/lib/{db,auth,utils}.ts         src/{types,utils}/       services}/
src/types/index.ts
```

## 6. API Design

**REST conventions** — resources are plural nouns; actions get a verb suffix when
CRUD doesn't fit.

```
GET/POST  /api/v1/patients      GET/PATCH/PUT/DELETE  /api/v1/patients/:id
GET/POST  /api/v1/patients/:id/appointments
POST      /api/v1/appointments/:id/confirm
```

**Response format, consistent everywhere.**

```typescript
{ "data": { }, "meta": { "page": 1, "total": 100 } }
{ "error": { "code": "VALIDATION_ERROR", "message": "Invalid input",
             "details": [{ "field": "email", "message": "Invalid email format" }] } }
```

**Route handler structure — the same five steps in every route.**

```typescript
export async function POST(req: Request) {
  // 1. PARSE & VALIDATE INPUT
  const { data: body, error: parseError } = await tryCatch(req.json());
  if (parseError) {
    return Response.json({ error: { code: 'INVALID_JSON' } }, { status: 400 });
  }
  const { data: input, error: invalidInput } = tryCatchSync(() =>
    createUserSchema.parse(body));
  if (invalidInput) {
    return Response.json(
      { error: { code: 'VALIDATION_ERROR', message: invalidInput.message } },
      { status: 400 });
  }

  // 2. AUTHENTICATE
  const session = await getSession();
  if (!session) return Response.json({ error: { code: 'UNAUTHORIZED' } }, { status: 401 });

  // 3. AUTHORIZE
  if (!canCreateUser(session.user)) {
    return Response.json({ error: { code: 'FORBIDDEN' } }, { status: 403 });
  }

  // 4. BUSINESS LOGIC (delegate to service)
  const { data: user, error: serviceError } = await tryCatch(userService.create(input));
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

## 7. Database

**Use the query builder, not raw SQL.** Raw SQL only where the builder genuinely
cannot express the query. **Schema commands (`db:push`, `db:migrate`,
`db:generate`) need per-run permission — propose the command and wait.**

**Every table carries the same base columns; related writes go in a transaction;
soft-deleted rows are filtered in the service (`isNull(patients.deletedAt)`).**

```typescript
const baseColumns = {
  id: uuid('id').defaultRandom().primaryKey(),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
};

export const patients = pgTable('patients', {
  ...baseColumns,
  deletedAt: timestamp('deleted_at'),
  name: varchar('name', { length: 255 }).notNull(),
  clinicId: uuid('clinic_id').references(() => clinics.id),
});

async function createAppointmentWithNotification(data: CreateAppointmentInput) {
  return db.transaction(async (tx) => {
    const [appointment] = await tx.insert(appointments).values(data).returning();
    await tx.insert(notifications).values({ userId: data.patientId, type: 'CREATED' });
    return appointment;
  });
}
```

## 8. React Components

**`useEffect` synchronizes with an external system** — subscriptions, DOM,
analytics, non-React libraries. Derived state is computed during render; state
reset uses `key`; state initialization uses the `useState` initializer.

```typescript
function UserList({ users }: { users: User[] }) {
  const [search, setSearch] = useState('');
  const filteredUsers = users.filter(u => u.name.includes(search));   // no effect
  return <List users={filteredUsers} />;
}

<Form key={userId} userId={userId} />;                    // reset on prop change
const [content, setContent] = useState(initialContent);   // init from props
```

**Profile before memoizing.** `useMemo` for expensive computation or a stable
reference passed into a dependency array; `useCallback` only when the callback
goes into a `memo()` child.

```typescript
const sorted = useMemo(() => items.filter(i => i.isActive).sort(complexSort), [items]);
const handleSelect = useCallback((id: string) => setSelectedId(id), []);
return <MemoizedList onSelect={handleSelect} />;
```

**Component file order:** imports → types → component → subcomponents → export.
Destructure props with defaults. `forwardRef` is the one place a wrapped function
expression is idiomatic.

```typescript
type PatientCardProps = { patient: Patient; onEdit: (id: string) => void };

export function PatientCard({ patient, onEdit }: PatientCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  return <div>{/* ... */}</div>;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn(baseStyles, className)} {...props} />;
  }
);
```

**Hooks:** `use` + noun/verb, `function` keyword, return a named object — or a
tuple for simple state (`useToggle(): [boolean, () => void]`).

```typescript
function usePatients(clinicId: string) {
  const query = useQuery({ /* ... */ });
  return { patients: query.data ?? [], isLoading: query.isLoading, error: query.error };
}
```

## 9. Async

**Run independent operations in parallel; sequence only when the second call
needs the first one's result.** `async`/`await` over `.then()` chains.

```typescript
const [user, posts, notifications] = await Promise.all([
  getUser(userId), getPosts(userId), getNotifications(userId),
]);

// With per-call error handling
const [userResult, postsResult] = await Promise.all([
  tryCatch(getUser(userId)), tryCatch(getPosts(userId)),
]);
```

Server components fetch directly; the client uses TanStack Query with `queryKey`
plus `invalidateQueries` on mutation.

## 10. Security

**Validate at the boundary; everything past it is typed and trusted.** The route
handler in §6 is that boundary.

**Authorize per resource, not per route.** Authentication says who they are;
ownership and role checks say what they may touch.

```typescript
async function updatePatient(userId: string, patientId: string, data: UpdatePatientInput) {
  const patient = await db.query.patients.findFirst({ where: eq(patients.id, patientId) });
  if (patient?.userId !== userId && !(await hasRole(userId, 'admin'))) {
    return { ok: false, error: { code: 'FORBIDDEN' } };
  }
  // proceed
}
```

**Parameterized queries only** — the query builder does this; never interpolate
user input into SQL. **Validate environment variables at startup** via
`lib/env.ts`, and import `env` rather than reading `process.env` at the point of
use.

## 11. Logging

Use the class-based `Logger` from `lib/logger.ts`. Create it per request,
`addContext()` as the request progresses — the final line carries everything the
earlier ones did — and `log.time()` around slow calls.

Structured pairs, context first, message second: `logger.info({ userId }, 'User
created')`. No `console.log` in shipped code; local debugging and CLI tools only.

## 12. Dates

1. Store all dates as UTC in the database (`timestamptz`).
2. Transport as ISO strings in the API.
3. Convert to local timezone only in the UI layer.
4. Manipulate with date-fns or dayjs, not native `Date` methods.

```typescript
const formatted = format(addDays(parseISO('2024-01-15T10:30:00Z'), 7), 'yyyy-MM-dd');
const local = formatInTimeZone(appointment.startTime, userTimezone, 'MMM d, h:mm a');

const appointments = pgTable('appointments', {
  startTime: timestamp('start_time', { withTimezone: true }).notNull(),
});
```

## 13. Git & Documentation

**Conventional commits**, imperative mood, 50-char subject: `feat:`, `fix:`,
`refactor:`, `perf:`, `chore:`, `docs:`, `test:`, `style:` — with an optional
scope, `feat(auth): add OAuth2 support`.

**Document non-obvious behaviour**, and give each feature folder a README with
overview, key files, domain rules and endpoints.

```typescript
/**
 * Returns appointments for the next 7 days.
 * Excludes cancelled appointments. Results are cached for 5 minutes.
 */
async function getUpcomingAppointments(patientId: string) {}
```
