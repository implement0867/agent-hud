import type { Element } from "hast";

import { invariant } from "~/lib/invariant";

/** Whether a rehype plugin put the property on the element. */
export const hasProperty = (node: Element, name: string) =>
  node.properties[name] !== undefined;

/** The text that a rehype plugin put in the element's property. */
export const readTextProperty = (node: Element, name: string): string => {
  const value = node.properties[name];
  invariant(typeof value === "string", `the property ${name} holds text`);
  return value;
};
