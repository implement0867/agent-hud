import type { z } from "zod";

/**
 * What the browser keeps for the viewer, which the server never sees. A browser that keeps nothing, or keeps a value
 * that the page cannot read, reads as one that keeps nothing.
 */

/** The value the browser keeps under the key, or null when it keeps none that the schema takes. */
export const readKept = <T>(key: string, schema: z.ZodType<T>): T | null => {
  try {
    const kept = schema.safeParse(
      JSON.parse(localStorage.getItem(key) ?? "null"),
    );
    return kept.success ? kept.data : null;
  } catch {
    return null;
  }
};

/** Keeps the value in the browser under the key, or forgets the key on null. */
export const writeKept = (key: string, value: unknown) => {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // A browser that keeps nothing holds the value until the page reloads.
  }
};
