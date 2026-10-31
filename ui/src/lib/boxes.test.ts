import type { Element, Root } from "hast";
import { describe, expect, it } from "vitest";

import { treeOf } from "~/domain/text";
import { markBoxCells, markBoxRanges, readBoxRange } from "~/lib/boxes";

/** The elements of the tree with the tag, in the tree's order. */
const listElements = (node: Root | Element, tag: string): Element[] =>
  node.children.flatMap((child) =>
    child.type === "element"
      ? [...(child.tagName === tag ? [child] : []), ...listElements(child, tag)]
      : [],
  );

const markTree = (md: string, ranges: boolean) => {
  const tree = treeOf(md);
  markBoxCells()(tree);
  if (ranges) markBoxRanges()(tree);
  return tree;
};

describe("markBoxRanges", () => {
  it("gives a task item's box the range of its item's markdown", () => {
    const md = "- [ ] Do it\n- [x] Done";
    const boxes = listElements(markTree(md, true), "input");
    expect(boxes.map(readBoxRange)).toEqual([
      { start: 0, end: 11 },
      { start: 12, end: 22 },
    ]);
  });

  it("gives a cell of a box alone the range of its markdown", () => {
    const md = "| Done | Step |\n| --- | --- |\n| [x] | Ship |";
    const cells = listElements(markTree(md, true), "td");
    expect(cells.map((cell) => cell.properties["dataBox"])).toEqual([
      "",
      undefined,
    ]);
    expect(cells.map(readBoxRange)).toEqual([{ start: 30, end: 36 }, null]);
  });

  it("leaves the boxes of a tree it did not run on without a range", () => {
    const boxes = listElements(markTree("- [ ] Do it", false), "input");
    expect(boxes.map(readBoxRange)).toEqual([null]);
  });
});
