import type { Element, Root } from "hast";

import { isBoxCell } from "~/domain/text";
import { invariant } from "~/lib/invariant";

/** Where a box's markdown runs, which a click on the box flips. */
export type TBoxRange = { start: number; end: number };

/** Calls the visitor on each element of the tree, outermost first. */
const visitElements = (
  node: Root | Element,
  visit: (element: Element) => void,
) => {
  for (const child of node.children)
    if (child.type === "element") {
      visit(child);
      visitElements(child, visit);
    }
};

/** A rehype plugin: a table cell of a box alone is marked as a box, which shows as a checkbox. */
export const markBoxCells = () => (tree: Root) => {
  visitElements(tree, (element) => {
    if (isBoxCell(element)) element.properties["dataBox"] = "";
  });
};

/**
 * A rehype plugin, after the box cells are marked and before the colouring, while the elements have their places in
 * the markdown: a task item's box and a box cell get the range of their markdown, for a click to flip the box.
 */
export const markBoxRanges = () => (tree: Root) => {
  visitElements(tree, (element) => {
    const place = element.position;
    if (place?.start.offset === undefined || place.end.offset === undefined)
      return;
    const range = { dataStart: place.start.offset, dataEnd: place.end.offset };
    if (element.properties["dataBox"] !== undefined)
      Object.assign(element.properties, range);
    if (element.tagName === "li")
      for (const box of [
        ...element.children,
        ...element.children.flatMap((child) =>
          child.type === "element" && child.tagName === "p"
            ? child.children
            : [],
        ),
      ])
        if (box.type === "element" && box.tagName === "input")
          Object.assign(box.properties, range);
  });
};

/** The range that markBoxRanges put on the box, or null on a box that does not flip, such as an earlier version's. */
export const readBoxRange = (box: Element): TBoxRange | null => {
  const start = box.properties["dataStart"];
  const end = box.properties["dataEnd"];
  if (start === undefined && end === undefined) return null;
  invariant(
    typeof start === "number" && typeof end === "number",
    "a box's range runs between two offsets",
  );
  return { start, end };
};
