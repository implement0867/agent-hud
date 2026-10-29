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
  arrows: {},
  messages: [],
  positions: {},
  sizes: {},
  history: {},
  ...patch,
});

const snapshot = (of: TBoard): TSnapshot => ({
  kind: "snapshot",
  board: of,
  agent: "waiting",
  pending: [],
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
      history: { a: [{ card, threads: {} }] },
    });
    expect(diffBoards(before, after)).toEqual({
      arrived: ["d"],
      left: ["b"],
      revised: ["a"],
      moved: ["c"],
      lost: [],
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
      lost: [],
    });
  });

  it("finds the arrows that went, with what they were", () => {
    const arrow = {
      card: "a",
      quote: "parse",
      occurrence: 0,
      dst: "b",
      text: "",
      author: "user" as const,
    };
    const before = board({ arrows: { ab: arrow, kept: arrow } });
    const after = board({ arrows: { kept: arrow } });
    expect(diffBoards(before, after).lost).toEqual([{ id: "ab", arrow }]);
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
      { arrived: ["c"], left: ["b"], revised: [], moved: [], lost: [] },
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
      { arrived: [], left: [], revised: [], moved: [], lost: [] },
      after,
    );
    expect(next.dropped).toEqual({ b: { x: 1, y: 1 } });
  });

  it("shows a new version's changes against the version before, unless the user put it from this page, and drops those of a card that left", () => {
    const old = { ...card, md: "1. parse\n2. render" };
    const after = board({
      cards: {
        a: { ...card, md: "1. parse\n2. render fast" },
        b: { ...card, md: "1. parse\n2. ship" },
      },
      history: {
        a: [{ card: old, threads: {} }],
        b: [{ card: old, threads: {} }],
      },
    });
    const next = afterChange(
      {
        ...emptyLocal,
        expected: ["b"],
        changed: { gone: "1. was" },
      },
      { arrived: [], left: ["gone"], revised: ["a", "b"], moved: [], lost: [] },
      after,
    );
    expect(next.changed).toEqual({ a: "1. parse\n2. render" });
    expect(next.expected).toEqual([]);
  });

  it("keeps the user's arrows that went without the user's unlink, and not the agent's or the expected", () => {
    const mine = {
      card: "a",
      quote: "",
      occurrence: 0,
      dst: "b",
      text: "",
      author: "user" as const,
    };
    const theirs = { ...mine, author: "agent" as const };
    const next = afterChange(
      { ...emptyLocal, expected: ["own"] },
      {
        arrived: [],
        left: [],
        revised: [],
        moved: [],
        lost: [
          { id: "own", arrow: mine },
          { id: "taken", arrow: mine },
          { id: "theirs", arrow: theirs },
        ],
      },
      board({}),
    );
    expect(next.lostArrows).toEqual([{ id: "taken", arrow: mine }]);
    expect(next.expected).toEqual([]);
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

describe("afterChange of changes", () => {
  it("keeps the version the user last saw when the agent puts again before the user looks", () => {
    const v1 = { ...card, md: "1. one" };
    const v2 = { ...card, md: "1. two" };
    const after = board({
      cards: { a: { ...card, md: "1. three" } },
      history: {
        a: [
          { card: v1, threads: {} },
          { card: v2, threads: {} },
        ],
      },
    });
    const next = afterChange(
      { ...emptyLocal, changed: { a: "1. one" } },
      { arrived: [], left: [], revised: ["a"], moved: [], lost: [] },
      after,
    );
    expect(next.changed).toEqual({ a: "1. one" });
  });
});
