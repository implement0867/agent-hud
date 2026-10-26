import type { Element, ElementContent, Root, RootContent } from "hast";

import { textOf, tidy, treeOf } from "~/domain/text";

/** How a new version shows its changes: the words that changed in each block, or whole old and new lines. */
export type TDiffStyle = "word" | "line";

/** A block of a card that a diff compares: a heading, paragraph, list item, or table cell, and the element it is in. */
type TBlock = { node: Element; parent: Element | Root; text: string };

const blockTags = new Set([
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "p",
  "li",
  "td",
  "th",
]);

/** Whether a child of a list item is its own text, rather than a nested list or a paragraph that is a block itself. */
const ownChild = (child: ElementContent) =>
  !(
    child.type === "element" &&
    ["ul", "ol", "p", "pre", "blockquote", "table"].includes(child.tagName)
  );

const ownText = (node: Element) =>
  tidy(
    (node.tagName === "li" ? node.children.filter(ownChild) : node.children)
      .map((child) => textOf(child))
      .join(""),
  );

/** The blocks of the tree in document order; a list item whose text is in paragraphs is no block itself. */
const blocksOf = (tree: Root): TBlock[] => {
  const blocks: TBlock[] = [];
  const visit = (node: Root | Element) => {
    for (const child of node.children) {
      if (child.type !== "element") continue;
      if (child.tagName === "pre") continue;
      if (blockTags.has(child.tagName)) {
        const text = ownText(child);
        if (child.tagName !== "li" || text !== "")
          blocks.push({ node: child, parent: node, text });
      }
      visit(child);
    }
  };
  visit(tree);
  return blocks;
};

/** The longest common subsequence of two lists, as the pairs of indices of the items it keeps, in order. */
const common = <T>(a: T[], b: T[]): [number, number][] => {
  const rows = a.length + 1;
  const columns = b.length + 1;
  const table = new Uint16Array(rows * columns);
  for (let i = a.length - 1; i >= 0; i -= 1)
    for (let j = b.length - 1; j >= 0; j -= 1)
      table[i * columns + j] =
        a[i] === b[j]
          ? (table[(i + 1) * columns + j + 1] ?? 0) + 1
          : Math.max(
              table[(i + 1) * columns + j] ?? 0,
              table[i * columns + j + 1] ?? 0,
            );
  const pairs: [number, number][] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      pairs.push([i, j]);
      i += 1;
      j += 1;
    } else if (
      (table[(i + 1) * columns + j] ?? 0) >= (table[i * columns + j + 1] ?? 0)
    )
      i += 1;
    else j += 1;
  }
  return pairs;
};

const text = (value: string): ElementContent => ({ type: "text", value });

/** The words a change removed, which are no part of the card's text, and the words it added. */
const removed = (value: string): Element => ({
  type: "element",
  tagName: "del",
  properties: { className: ["diff-del"], dataChrome: "" },
  children: [text(value)],
});

const added = (children: ElementContent[]): Element => ({
  type: "element",
  tagName: "ins",
  properties: { className: ["diff-ins"] },
  children,
});

/** A run of words: the same in both texts, or the words that went and the words that came in their place. */
type TRun = { same: string } | { gone: string; come: string };

/** The runs of the old text and the new, word by word. */
const runsOf = (before: string, after: string): TRun[] => {
  const old = before.split(/(\s+)/);
  const now = after.split(/(\s+)/);
  if (old.length * now.length > 160_000) return [{ gone: before, come: after }];
  const runs: TRun[] = [];
  const pairs: [number, number][] = [
    ...common(old, now),
    [old.length, now.length],
  ];
  let i = 0;
  let j = 0;
  for (const [keepOld, keepNew] of pairs) {
    const gone = old.slice(i, keepOld).join("");
    const come = now.slice(j, keepNew).join("");
    const last = runs.at(-1);
    const space = runs.at(-2);
    // A space alone between two rewordings joins them, so that a reworded phrase reads as one change.
    if (
      gone !== "" &&
      come !== "" &&
      last !== undefined &&
      "same" in last &&
      last.same.trim() === "" &&
      space !== undefined &&
      "gone" in space &&
      space.gone !== "" &&
      space.come !== ""
    ) {
      runs.pop();
      runs[runs.length - 1] = {
        gone: space.gone + last.same + gone,
        come: space.come + last.same + come,
      };
    } else if (gone !== "" || come !== "") runs.push({ gone, come });
    if (keepOld < old.length) runs.push({ same: old[keepOld] ?? "" });
    i = keepOld + 1;
    j = keepNew + 1;
  }
  return runs;
};

/** The words of the old text and the new, with the words that the new one removed and added marked. */
const wordDiff = (before: string, after: string): ElementContent[] =>
  runsOf(before, after).flatMap((run) =>
    "same" in run
      ? [text(run.same)]
      : [
          ...(run.gone.trim() === "" ? [] : [removed(run.gone)]),
          ...(run.come === ""
            ? []
            : run.come.trim() === ""
              ? [text(run.come)]
              : [added([text(run.come)])]),
        ],
  );

/** The block's own children replaced, before its nested lists. */
const replaceOwn = (node: Element, children: ElementContent[]) => {
  node.children =
    node.tagName === "li"
      ? [...children, ...node.children.filter((child) => !ownChild(child))]
      : children;
};

const addClass = (node: Element, name: string) => {
  const current = node.properties.className;
  node.properties.className = [
    ...(Array.isArray(current) ? current.map(String) : []),
    name,
  ];
};

/** A copy of an old block, with its words as removed, to show where it was. */
const gone = (block: TBlock, style: TDiffStyle): Element => ({
  type: "element",
  tagName: block.node.tagName,
  properties:
    style === "line"
      ? { className: ["dl", "dl-del"], dataChrome: "" }
      : { dataChrome: "" },
  children: [removed(block.text)],
});

/** Puts the node right after the anchor in its parent, or before the next block when there is no anchor, or last. */
const insert = (
  node: Element,
  after: TBlock | null,
  next: TBlock | undefined,
  tree: Root,
) => {
  if (after !== null) {
    (after.parent.children as RootContent[]).splice(
      after.parent.children.indexOf(after.node) + 1,
      0,
      node,
    );
  } else if (next !== undefined) {
    (next.parent.children as RootContent[]).splice(
      next.parent.children.indexOf(next.node),
      0,
      node,
    );
  } else tree.children.push(node);
};

const isCell = (block: TBlock) =>
  block.node.tagName === "td" || block.node.tagName === "th";

/**
 * A rehype plugin, before the colouring: the blocks of the card that changed since the old markdown show the change.
 * In the word style, a reworded block shows the words that went struck through and the new words tinted, a new block
 * is tinted whole, and a block that went shows struck through where it was. In the line style, the old block shows
 * whole as a removed line before the new one. A table cell that went shows nowhere, and code blocks show as they are.
 */
export const showChanges =
  ({ before, style }: { before: string; style: TDiffStyle }) =>
  (tree: Root) => {
    const old = blocksOf(treeOf(before));
    const now = blocksOf(tree);
    const pairs: [number, number][] = [
      ...common(
        old.map((b) => b.text),
        now.map((b) => b.text),
      ),
      [old.length, now.length],
    ];
    let i = 0;
    let j = 0;
    let last: TBlock | null = null;
    for (const [keepOld, keepNew] of pairs) {
      const olds = old.slice(i, keepOld);
      const news = now.slice(j, keepNew);
      for (const [n, block] of news.entries()) {
        const was = olds[n];
        if (style === "line") {
          if (was !== undefined && !isCell(was))
            insert(gone(was, style), null, block, tree);
          addClass(block.node, "dl");
          addClass(block.node, "dl-ins");
        } else if (was === undefined)
          replaceOwn(block.node, [
            added(
              block.node.tagName === "li"
                ? block.node.children.filter(ownChild)
                : block.node.children,
            ),
          ]);
        else replaceOwn(block.node, wordDiff(was.text, block.text));
        last = block;
      }
      for (const was of olds.slice(news.length).toReversed()) {
        if (!isCell(was)) insert(gone(was, style), last, now[keepNew], tree);
      }
      if (keepNew < now.length) last = now[keepNew] ?? null;
      i = keepOld + 1;
      j = keepNew + 1;
    }
  };
