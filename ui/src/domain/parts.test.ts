import { describe, expect, it } from "vitest";

import type { TBoard } from "~/domain/board";
import { changesBetween, nameOf, partTexts } from "~/domain/parts";

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
      "ship | ",
      "x = 1",
      "y = 2",
    ]);
  });
});

describe("partTexts", () => {
  it("joins a table row's cells with a bar, as the server does", () => {
    expect(
      partTexts("| Task | Size {S, M, L} |\n|---|---|\n| parse | M |"),
    ).toEqual(["parse | M"]);
    expect(partTexts("| Task | Done {check} |\n|---|---|\n| ship | |")).toEqual(
      ["ship | "],
    );
  });
});

describe("nameOf", () => {
  const board: TBoard = {
    cards: {
      plan: {
        md: "# The plan\n\n1. parse\n2. render",
        author: "agent",
        edited: false,
      },
      tasks: {
        md: "| Task | Hours {number} |\n|---|---|\n| parse the input | |",
        author: "agent",
        edited: false,
      },
    },
    threads: {},
    values: {},
    arrows: {},
    messages: [],
    positions: {},
    widths: {},
    history: {},
  };

  it("names a card by its title, a part by its text, a row by its first cell and a cell by its row and column", () => {
    expect(nameOf(board, "plan")).toBe("The plan");
    expect(nameOf(board, "plan/3")).toBe("render");
    expect(nameOf(board, "tasks")).toBe("Task");
    expect(nameOf(board, "tasks/1")).toBe("parse the input");
    expect(nameOf(board, "tasks/1/2")).toBe("parse the input: Hours");
  });

  it("keeps the ref when the card is not on the board or the part is not in it", () => {
    expect(nameOf(board, "gone/1")).toBe("gone/1");
    expect(nameOf(board, "plan/9")).toBe("plan/9");
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
