export type User = { id: string; email: string; nickname?: string };

// Deliberate: `nickname` is optional, so this dereference is a real type error.
export function formatUserLabel(u: User) {
  return u.nickname.toUpperCase() + " <" + u.email + ">";
}

// Deliberate: awaits inside a for loop — the sequential-await shape backend-perf looks for.
export async function loadUsers(ids: string[]) {
  const out = [];
  for (const id of ids) {
    out.push(await fetchUser(id));
  }
  return out;
}

declare function fetchUser(id: string): Promise<User>;
