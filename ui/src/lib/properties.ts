import type { Element } from "hast";

import { invariant } from "~/lib/invariant";

/** The text that a rehype plugin put in the element's property, or undefined where it put none. */
export const readTextProperty = (
  node: Element,
  name: string,
): string | undefined => {
  const value = node.properties[name];
  if (value === undefined) return undefined;
  invariant(typeof value === "string", `the property ${name} holds text`);
  return value;
};
