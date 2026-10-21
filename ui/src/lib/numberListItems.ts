import type { Root, RootContent } from "hast";

/** A rehype plugin: data-item on each li is its number in the document, from 1. */
export const numberListItems = () => (tree: Root) => {
  let count = 0;
  const visit = (node: Root | RootContent) => {
    if (node.type === "element" && node.tagName === "li") {
      count += 1;
      node.properties["dataItem"] = count;
    }
    if ("children" in node) node.children.forEach(visit);
  };
  visit(tree);
};
