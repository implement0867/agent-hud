import { describe, expect, it } from "vitest";

import {
  afterChange,
  diffBoards,
  emptyLocal,
  modelOf,
} from "~/data/boardModel";
import type { TBoard, TCard } from "~/domain/board";
import type { TSnapshot } from "~/domain/events";

const card: TCard = { md: "1. parse", author: "agent", edited: false };

const board = (patch: Partial<TBoard>): TBoard => ({
  cards: {},
  threads: {},
  values: {},
  arrows: {},
  messages: [],
  positions: {},
  widths: {},
  history: {},
  ...patch,
});

const snapshot = (of: TBoard): TSnapshot => ({
  kind: "snapshot",
  board: of,
  agent: "waiting",
  pending: [],
  unsent: 0,
  waiting: 0,
});

describe("diffBoards", () => {
  it("finds the cards that arrived, left, got a version or moved", () => {
    const before = board({
      cards: { a: card, b: card, c: card },
      positions: { a: { x: 0, y: 0 }, c: { x: 0, y: 0 } },
    });
    const after = board({
      cards: { a: card, c: card, d: card },
      positions: { a: { x: 0, y: 0 }, c: { x: 5, y: 0 } },
      history: { a: [{ card, threads: {}, values: {} }] },
    });
    expect(diffBoards(before, after)).toEqual({
      arrived: ["d"],
      left: ["b"],
      revised: ["a"],
      moved: ["c"],
    });
  });

  it("finds no change from a board to itself", () => {
    const same = board({
      cards: { a: card },
      positions: { a: { x: 1, y: 2 } },
    });
    expect(diffBoards(same, same)).toEqual({
      arrived: [],
      left: [],
      revised: [],
      moved: [],
    });
  });
});

describe("afterChange", () => {
  it("makes an arrival fresh and puts it on top, and forgets a card that left", () => {
    const local = {
      ...emptyLocal,
      touched: ["b", "a"],
      fresh: ["b"],
      placed: { b: { x: 0, y: 0 } },
    };
    const after = board({ cards: { a: card, c: card } });
    const next = afterChange(
      local,
      { arrived: ["c"], left: ["b"], revised: [], moved: [] },
      after,
    );
    expect(next.touched).toEqual(["a", "c"]);
    expect(next.fresh).toEqual(["c"]);
    expect(next.placed).toEqual({});
  });

  it("ends a drop once the server has the card there", () => {
    const local = {
      ...emptyLocal,
      dropped: { a: { x: 10, y: 20 }, b: { x: 1, y: 1 } },
    };
    const after = board({
      cards: { a: card, b: card },
      positions: { a: { x: 10, y: 20 }, b: { x: 0, y: 0 } },
    });
    const next = afterChange(
      local,
      { arrived: [], left: [], revised: [], moved: [] },
      after,
    );
    expect(next.dropped).toEqual({ b: { x: 1, y: 1 } });
  });
});

describe("modelOf", () => {
  it("shows a card at its drag, else its drop, else the server's place, else the page's", () => {
    const of = board({
      cards: { a: card, b: card, c: card, d: card },
      positions: { a: { x: 1, y: 1 }, b: { x: 2, y: 2 }, c: { x: 3, y: 3 } },
    });
    const model = modelOf(snapshot(of), {
      ...emptyLocal,
      dragging: { id: "a", at: { x: 9, y: 9 } },
      dropped: { b: { x: 8, y: 8 } },
      placed: { d: { x: 7, y: 7 } },
    });
    expect(model.cards.map(({ id, at }) => [id, at])).toEqual([
      ["a", { x: 9, y: 9 }],
      ["b", { x: 8, y: 8 }],
      ["c", { x: 3, y: 3 }],
      ["d", { x: 7, y: 7 }],
    ]);
  });

  it("layers the touched cards over the others, the last touched on top", () => {
    const model = modelOf(
      snapshot(board({ cards: { a: card, b: card, c: card } })),
      {
        ...emptyLocal,
        touched: ["a", "gone"],
      },
    );
    expect(model.cards.map(({ id, layer }) => [id, layer])).toEqual([
      ["a", 3],
      ["b", 1],
      ["c", 2],
    ]);
  });
});
