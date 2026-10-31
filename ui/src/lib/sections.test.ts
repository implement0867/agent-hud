import type { Root, RootContent } from "hast";
import { describe, expect, it } from "vitest";

import { treeOf } from "~/domain/text";
import { listSectionKeys, wrapSections } from "~/lib/sections";

/** The tree's sections as nested lists of their keys and the tags of what else they hold, without the line breaks. */
const outlineTree = (node: Root | RootContent): unknown[] => {
  if (node.type !== "element" && node.type !== "root") return [];
  return node.children.flatMap((child): unknown[] => {
    if (child.type !== "element") return [];
    if (child.tagName === "section")
      return [[child.properties["dataSection"], ...outlineTree(child)]];
    return [child.tagName];
  });
};

const outlineSections = (md: string) => {
  const tree = treeOf(md);
  wrapSections()(tree);
  return outlineTree(tree);
};

describe("wrapSections", () => {
  it("leaves a card without headings as one section, its blocks in none", () => {
    expect(outlineSections("One line.\n\n- an item")).toEqual(["p", "ul"]);
  });

  it("puts each heading and what follows it in a section, after the leading blocks", () => {
    expect(
      outlineSections("Lead.\n\n# One\n\nText.\n\n# Two\n\n- item"),
    ).toEqual(["p", ["0:One", "h1", "p"], ["0:Two", "h1", "ul"]]);
  });

  it("nests a deeper heading's section in the section above it, and ends it at a heading as high", () => {
    expect(
      outlineSections(
        "# Plan\n\n## Steps\n\nDo.\n\n### Detail\n\nMore.\n\n## Risks\n\nSome.\n\n# Next",
      ),
    ).toEqual([
      [
        "0:Plan",
        "h1",
        ["0:Steps", "h2", "p", ["0:Detail", "h3", "p"]],
        ["0:Risks", "h2", "p"],
      ],
      ["0:Next", "h1"],
    ]);
  });

  it("tells headings with the same text apart by how many came before", () => {
    expect(outlineSections("## Notes\n\nA.\n\n## Notes\n\nB.")).toEqual([
      ["0:Notes", "h2", "p"],
      ["1:Notes", "h2", "p"],
    ]);
  });

  it("marks the heading with its section's key", () => {
    const tree = treeOf("Lead.\n\n## Done *well*");
    wrapSections()(tree);
    const section = tree.children.find(
      (child) => child.type === "element" && child.tagName === "section",
    );
    const heading =
      section?.type === "element" ? section.children[0] : undefined;
    expect(
      heading?.type === "element"
        ? heading.properties["dataSectionHeading"]
        : null,
    ).toBe("0:Done well");
  });
});

describe("listSectionKeys", () => {
  it("lists the keys of the sections, nested ones after the section they are in", () => {
    expect(
      listSectionKeys("Lead.\n\n# Plan\n\n## Notes\n\n## Notes\n\n# Next"),
    ).toEqual(["0:Plan", "0:Notes", "1:Notes", "0:Next"]);
  });
});
