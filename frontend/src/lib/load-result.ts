/** Outcome of a provider fetch, applied to state by the caller (keeps setState out of effect bodies). */
export type LoadResult<T> = { data: T; error: null } | { data: null; error: string };

export function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}
