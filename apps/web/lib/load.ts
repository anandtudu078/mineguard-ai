/**
 * Load values without writing JSX inside a `try` block.
 *
 * A page that does `try { return <Thing/> } catch { return <Fallback/> }` is
 * flagged by React's error-boundary lint rule: constructing elements inside a
 * `try` means a render-time error in the success path is swallowed by the catch
 * that was only meant for the fetch. Turning the outcome into a value and
 * branching once makes that impossible.
 *
 * Usage:
 *   const result = await load(() => getThing(id));
 *   if (!result.ok) return <ApiErrorState detail={result.error} status={result.status} />;
 *   const thing = result.data;
 */

import { ApiError } from "./api";

export type Loaded<T> =
  | { ok: true; data: T }
  | { ok: false; error: string | undefined; status: number | undefined };

export async function load<T>(loader: () => Promise<T>): Promise<Loaded<T>> {
  try {
    return { ok: true, data: await loader() };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof ApiError ? error.message : undefined,
      status: error instanceof ApiError ? error.status : undefined,
    };
  }
}
