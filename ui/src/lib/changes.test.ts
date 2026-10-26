import type { Element, Root, RootContent } from "hast";
import { describe, expect, it } from "vitest";

import { treeOf } from "~/domain/text";
import { showChanges } from "~/lib/changes";

/** The tree as text, with the removed words in [-…-] and the added ones in {+…+}. */
const marked = (node: Root | RootContent): string => {
  if (node.type === "text") return node.value;
  if (node.type !== "element" && node.type !== "root") return "";
  const inner = node.children.map(marked).join("");
  const element = node as Element;
  if (node.type === "element" && element.tagName === "del")
    return `[-${inner}-]`;
  if (node.type === "element" && element.tagName === "ins")
    return `{+${inner}+}`;
  return ["li", "p", "h1"].includes(element.tagName) ? ` ${inner} ` : inner;
};

const diff = (
  before: string,
  after: string,
  style: "word" | "line" = "word",
) => {
  const tree = treeOf(after);
  showChanges({ before, style })(tree);
  return marked(tree).replace(/\s+/g, " ").trim();
};

describe("showChanges", () => {
  it("marks the words a block lost and gained, and leaves the others", () => {
    expect(
      diff("Ship it on a fresh board.", "Ship it from a clean install."),
    ).toBe("Ship it [-on-]{+from+} a [-fresh board.-]{+clean install.+}");
  });

  it("tints a new list item whole and shows a removed one where it was", () => {
    expect(diff("- one\n- two\n- three", "- one\n- three\n- four")).toBe(
      "one [-two-] three {+four+}",
    );
  });

  it("shows nothing for the same text", () => {
    expect(diff("# A\n\nb", "# A\n\nb")).toBe("A b");
  });

  it("puts the old block before the new one in the line style", () => {
    expect(diff("old words", "new words", "line")).toBe(
      "[-old words-] new words",
    );
  });
});
