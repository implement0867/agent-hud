import type { Element, Root } from "hast";

import { textOf } from "~/domain/text";

const headingLevels: Record<string, number> = {
  h1: 1,
  h2: 2,
  h3: 3,
  h4: 4,
  h5: 5,
  h6: 6,
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
      child.type === "element" ? headingLevels[child.tagName] : undefined;
    if (child.type === "element" && level !== undefined) {
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
