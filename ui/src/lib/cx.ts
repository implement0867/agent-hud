/** Join class names, skipping falsy entries. */
export const cx = (
  ...parts: readonly (string | false | null | undefined)[]
): string =>
  parts.filter((p): p is string => typeof p === "string" && p !== "").join(" ");
