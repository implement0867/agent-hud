import type { Element, Root, RootContent } from "hast";

const isPart = (node: Element, parent: Root | Element) =>
  node.tagName === "li" ||
  (node.tagName === "tr" &&
    parent.type === "element" &&
    parent.tagName === "tbody");

/** A rehype plugin: data-part on each list item and table body row is its number in the document, from 1. */
export const numberParts = () => (tree: Root) => {
  let count = 0;
  const visit = (node: Root | RootContent, parent: Root | Element) => {
    if (node.type === "element" && isPart(node, parent)) {
      count += 1;
      node.properties["dataPart"] = count;
    }
    if ("children" in node) {
      for (const child of node.children) visit(child, node);
    }
  };
  visit(tree, tree);
};
