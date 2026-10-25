import type { Root, RootContent } from "hast";
import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import remarkRehype from "remark-rehype";
import { unified } from "unified";

import { numberParts } from "~/lib/numberParts";

const textOf = (node: Root | RootContent): string =>
  node.type === "text"
    ? node.value
    : "children" in node
      ? node.children.map(textOf).join("")
      : "";

const parser = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkRehype)
  .use(numberParts);

/** The text of each part of the markdown, in order, as numberParts numbers them from 1, and as the page shows them. */
export const partTexts = (md: string): string[] => {
  const tree = parser.runSync(parser.parse(md));
  const texts: string[] = [];
  const visit = (node: Root | RootContent) => {
    if (
      node.type === "element" &&
      typeof node.properties["dataPart"] === "number"
    )
      texts[node.properties["dataPart"] - 1] = textOf(node).trim();
    if ("children" in node) for (const child of node.children) visit(child);
  };
  visit(tree);
  return texts;
};

/** What a new version of a card changed, for the page to mark: the numbers of the parts whose text is new, and the texts that went. */
export type TChanges = { parts: number[]; removed: string[] };

/** The parts of the new version that the old one did not have, by number, and the old version's texts that the new one does not have. */
export const changesBetween = (before: string, after: string): TChanges => {
  const was = partTexts(before);
  const is = partTexts(after);
  return {
    parts: is.flatMap((text, index) => (was.includes(text) ? [] : [index + 1])),
    removed: was.filter((text) => !is.includes(text)),
  };
};
