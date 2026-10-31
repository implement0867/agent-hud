import type { Element, Root } from "hast";

import { textOf, treeOf } from "~/domain/text";

/** The level of a heading's tag, h1 to h6, or null for a tag that is no heading. */
const findHeadingLevel = (tagName: string): number | null => {
  const found = /^h([1-6])$/.exec(tagName);
  return found === null ? null : Number(found[1]);
};

/**
 * A rehype plugin, before the changes, while the tree has the card's own blocks: each heading of the card's top level
 * and what follows it, up to the next heading of its level or a higher one, go in a section, which the user can fold to
 * its heading. A deeper heading's section is in the section above it; what comes before the first heading is in none.
 * The section and its heading carry the section's key: the heading's text, and how many headings before it have that
 * text, so that the key holds while the card changes elsewhere.
 */
export const wrapSections = () => (tree: Root) => {
  const counts = new Map<string, number>();
  const open: { level: number; section: Element }[] = [];
  const top: Root["children"] = [];
  for (const child of tree.children) {
    if (child.type === "doctype") {
      top.push(child);
      continue;
    }
    const level =
      child.type === "element" ? findHeadingLevel(child.tagName) : null;
    if (child.type === "element" && level !== null) {
      while ((open.at(-1)?.level ?? 0) >= level) open.pop();
      const text = textOf(child).trim();
      const occurrence = counts.get(text) ?? 0;
      counts.set(text, occurrence + 1);
      const key = `${String(occurrence)}:${text}`;
      child.properties["dataSectionHeading"] = key;
      const section: Element = {
        type: "element",
        tagName: "section",
        properties: { dataSection: key },
        children: [child],
      };
      (open.at(-1)?.section.children ?? top).push(section);
      open.push({ level, section });
    } else (open.at(-1)?.section.children ?? top).push(child);
  }
  tree.children = top;
};

/** The keys of the markdown's sections, as the plugin of the sections gives them, in the card's order. */
export const listSectionKeys = (md: string): string[] => {
  const tree = treeOf(md);
  wrapSections()(tree);
  const keys: string[] = [];
  const visit = (node: Root | Element) => {
    for (const child of node.children) {
      if (child.type !== "element" || child.tagName !== "section") continue;
      const key = child.properties["dataSection"];
      if (typeof key === "string") keys.push(key);
      visit(child);
    }
  };
  visit(tree);
  return keys;
};
