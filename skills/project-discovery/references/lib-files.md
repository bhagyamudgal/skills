# lib/ Files

Copy all four into the project's `lib/` verbatim. Every rule in
`coding-standards.md` assumes these exact signatures.

**lib/try-catch.ts**
```typescript
type Success<T> = { data: T; error: null };
type Failure<E> = { data: null; error: E };

// Distinct from the service-level `Result` in coding-standards.md: this one is
// destructured as { data, error }, never branched on `.ok`.
type TryCatchResult<T, E = Error> = Success<T> | Failure<E>;

// Async operations
export async function tryCatch<T, E = Error>(
  promise: Promise<T>,
): Promise<TryCatchResult<T, E>> {
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
): TryCatchResult<T, E> {
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
): (...args: TArgs) => Promise<TryCatchResult<TReturn, E>> {
  return async (...args: TArgs) => tryCatch<TReturn, E>(fn(...args));
}

// Retry with exponential backoff
export async function tryCatchRetry<T, E = Error>(
  promise: () => Promise<T>,
  options: { maxRetries?: number; delayMs?: number; backoff?: boolean } = {},
): Promise<TryCatchResult<T, E>> {
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
): Promise<TryCatchResult<T, E>> {
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
