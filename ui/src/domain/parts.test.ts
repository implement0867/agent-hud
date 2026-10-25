import { describe, expect, it } from "vitest";

import { changesBetween, partTexts } from "~/domain/parts";

describe("partTexts", () => {
  it("numbers headings, paragraphs, list items, table rows and code lines as the server does", () => {
    const md = [
      "# Plan",
      "",
      "A note.",
      "",
      "1. parse",
      "2. render",
      "",
      "| Task | Done {check} |",
      "|---|---|",
      "| ship | |",
      "",
      "```py",
      "x = 1",
      "y = 2",
      "```",
    ].join("\n");
    expect(partTexts(md)).toEqual([
      "Plan",
      "A note.",
      "parse",
      "render",
      "ship",
      "x = 1",
      "y = 2",
    ]);
  });
});

describe("changesBetween", () => {
  it("finds the parts the new version added or reworded, and the texts that went", () => {
    const { parts, removed } = changesBetween(
      "1. parse\n2. render\n3. test",
      "1. parse\n2. render fast\n3. ship",
    );
    expect(parts).toEqual([2, 3]);
    expect(removed).toEqual(["render", "test"]);
  });

  it("finds nothing when the text is the same", () => {
    expect(changesBetween("a\n\nb", "a\n\nb")).toEqual({
      parts: [],
      removed: [],
    });
  });
});
