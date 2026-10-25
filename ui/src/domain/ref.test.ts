import fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  cardOf,
  cellRef,
  isCardRef,
  partRef,
  rowOf,
  splitRefs,
} from "~/domain/ref";

const cardIds = () => fc.stringMatching(/^[A-Za-z][A-Za-z0-9_-]{0,31}$/);
const numbers = () => fc.integer({ min: 1, max: 999 });

describe("refs", () => {
  it("name the card they are on", () => {
    fc.assert(
      fc.property(cardIds(), numbers(), numbers(), (card, row, column) => {
        expect(cardOf(card)).toBe(card);
        expect(cardOf(partRef(card, row))).toBe(card);
        expect(cardOf(cellRef(card, row, column))).toBe(card);
      }),
    );
  });

  it("tell a card from its parts", () => {
    fc.assert(
      fc.property(cardIds(), numbers(), (card, part) => {
        expect(isCardRef(card)).toBe(true);
        expect(isCardRef(partRef(card, part))).toBe(false);
      }),
    );
  });

  it("give a cell's row", () => {
    fc.assert(
      fc.property(cardIds(), numbers(), numbers(), (card, row, column) => {
        expect(rowOf(cellRef(card, row, column))).toBe(partRef(card, row));
      }),
    );
  });
});

describe("splitRefs", () => {
  const onBoard = (card: string) => ["plan", "tasks"].includes(card);

  it("links the parts of cards on the board and the rows of their cells", () => {
    expect(splitRefs("see plan/2 and tasks/3/4, not gone/1", onBoard)).toEqual([
      { text: "see ", ref: null, at: 0 },
      { text: "plan/2", ref: "plan/2", at: 4 },
      { text: " and ", ref: null, at: 10 },
      { text: "tasks/3/4", ref: "tasks/3", at: 15 },
      { text: ", not ", ref: null, at: 24 },
      { text: "gone/1", ref: null, at: 30 },
    ]);
  });

  it("leaves a card id alone and a part number from 0", () => {
    expect(splitRefs("plan and plan/0", onBoard)).toEqual([
      { text: "plan and plan/0", ref: null, at: 0 },
    ]);
  });

  it("gives back the text it splits", () => {
    fc.assert(
      fc.property(fc.string(), (text) => {
        const pieces = splitRefs(text, onBoard);
        expect(pieces.map((piece) => piece.text).join("")).toBe(text);
        for (const piece of pieces)
          expect(text.slice(piece.at, piece.at + piece.text.length)).toBe(
            piece.text,
          );
      }),
    );
  });
});
