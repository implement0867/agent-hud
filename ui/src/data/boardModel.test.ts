import { describe, expect, it } from "vitest";

import {
  afterChange,
  diffBoards,
  emptyLocal,
  modelOf,
  placeArrivals,
} from "~/data/boardModel";
import type { TCardBox, TSurface } from "~/data/boardModel";
import type { TBoard, TCard, TPoint } from "~/domain/board";
import type { TSnapshot } from "~/domain/events";
import { overlap, viewMargin } from "~/lib/geometry";
import type { TSize } from "~/lib/geometry";
import { gap } from "~/lib/packing";

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

const edge = viewMargin;
const area = { x: 0, y: 0, width: 1440, height: 900 };
const short: TSize = { width: 256, height: 100 };

/** A surface that shows the area, with the given cards laid out. */
const surfaceOf = (laidOut: Record<string, TSize>): TSurface => ({
  viewport: () => area,
  sizes: () => new Map(Object.entries(laidOut)),
});

/** A measure that gives a card a line of height per line of markdown, and the width of a short card. */
const measureByLines = (box: TCardBox): TSize => ({
  width: short.width,
  height: 20 * box.md.split("\n").length,
});

describe("placeArrivals", () => {
  it("gives nothing when every card has a place, from the server, a drop, a drag or the page", () => {
    const of = board({
      cards: { a: card, b: card, c: card, d: card },
      positions: { a: { x: 1, y: 1 } },
    });
    const local = {
      ...emptyLocal,
      dropped: { b: { x: 2, y: 2 } },
      dragging: { id: "c", at: { x: 3, y: 3 } },
      placed: { d: { x: 4, y: 4 } },
    };
    expect(
      placeArrivals(null, of, local, measureByLines, surfaceOf({})),
    ).toEqual({});
  });

  it("packs a card without a place into the view, clear of the cards laid out", () => {
    const of = board({
      cards: { a: card, b: card },
      positions: { a: { x: edge, y: edge } },
    });
    const placed = placeArrivals(
      of,
      of,
      emptyLocal,
      measureByLines,
      surfaceOf({ a: { width: 400, height: 100 } }),
    );
    expect(placed).toEqual({ b: { x: edge + 400 + gap, y: edge } });
  });

  it("measures a card that the page has not laid out, both the one it places and the ones it places around", () => {
    const tall = { ...card, md: "1. a\n2. b\n3. c\n4. d\n5. e" };
    const of = board({
      cards: { a: tall, b: card, c: tall },
      positions: { a: { x: edge, y: edge } },
    });
    const placed = placeArrivals(
      null,
      of,
      emptyLocal,
      measureByLines,
      surfaceOf({}),
    );
    expect(placed).toEqual({
      b: { x: edge + short.width + gap, y: edge },
      c: { x: edge + 2 * (short.width + gap), y: edge },
    });
    const below = board({ ...of, positions: {} });
    const narrow: TSurface = {
      viewport: () => ({ ...area, width: 2 * edge + short.width }),
      sizes: () => new Map(),
    };
    expect(
      placeArrivals(null, below, emptyLocal, measureByLines, narrow),
    ).toEqual({
      a: { x: edge, y: edge },
      b: { x: edge, y: edge + 100 + gap },
      c: { x: edge, y: edge + 100 + gap + 20 + gap },
    });
  });

  it("measures a card at the width and the height set on it, with its versions", () => {
    const seen: TCardBox[] = [];
    const of = board({
      cards: { a: card },
      sizes: { a: { width: 500, height: null } },
      history: { a: [{ card, threads: {} }] },
    });
    placeArrivals(
      null,
      of,
      emptyLocal,
      (box) => {
        seen.push(box);
        return short;
      },
      surfaceOf({}),
    );
    expect(seen).toEqual([
      { md: card.md, width: 500, height: null, versions: 1 },
    ]);
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

  it("refuses a card without a place, which the store gives each card before it publishes", () => {
    expect(() =>
      modelOf(snapshot(board({ cards: { a: card } })), emptyLocal),
    ).toThrow("card a has a place");
  });

  it("layers the touched cards over the others, the last touched on top", () => {
    const at = { x: 0, y: 0 };
    const model = modelOf(
      snapshot(
        board({
          cards: { a: card, b: card, c: card },
          positions: { a: at, b: at, c: at },
        }),
      ),
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

describe("placeArrivals under attack", () => {
  it("packs around the card the user drags at its drag point, not at the server's place for it", () => {
    const of = board({
      cards: { a: card, b: card },
      positions: { a: { x: edge, y: edge } },
    });
    const dragTo = { x: edge + short.width + gap, y: edge };
    const placed = placeArrivals(
      of,
      of,
      { ...emptyLocal, dragging: { id: "a", at: dragTo } },
      measureByLines,
      surfaceOf({ a: short }),
    );
    expect(placed).toEqual({ b: { x: edge, y: edge } });
  });

  it("packs around a card where the user dropped it before the server has it there", () => {
    const of = board({
      cards: { a: card, b: card },
      positions: { a: { x: 2000, y: 2000 } },
    });
    const placed = placeArrivals(
      of,
      of,
      { ...emptyLocal, dropped: { a: { x: edge, y: edge } } },
      measureByLines,
      surfaceOf({ a: short }),
    );
    expect(placed).toEqual({ b: { x: edge + short.width + gap, y: edge } });
  });

  it("measures a card that lost its place by its markdown now, not by the size the page laid its old version out at", () => {
    const tall = {
      ...card,
      md: Array.from({ length: 25 }, () => "line").join("\n"),
    };
    const beside = {
      x: edge + short.width + gap,
      y: edge + short.height + gap,
    };
    const of = board({
      cards: { a: card, b: tall, c: card },
      positions: { a: { x: edge, y: edge }, c: beside },
    });
    const placed = placeArrivals(
      board({ ...of, cards: { a: card, b: card, c: card } }),
      of,
      emptyLocal,
      measureByLines,
      surfaceOf({ a: short, b: short, c: short }),
    );
    const rectOfB = {
      ...placeOf(placed, "b"),
      ...measureByLines(boxOfMd(tall.md)),
    };
    expect(overlap(rectOfB, { ...beside, ...short })).toBe(false);
  });

  it("packs into a view zoomed out and panned to negative float coordinates", () => {
    const of = board({ cards: { a: card } });
    const far: TSurface = {
      viewport: () => ({ x: -1234.5, y: -987.25, width: 2880, height: 1800 }),
      sizes: () => new Map(),
    };
    expect(placeArrivals(null, of, emptyLocal, measureByLines, far)).toEqual({
      a: { x: -1234.5 + edge, y: -987.25 + edge },
    });
  });

  it("places every card of a board that has none in the board's order, each clear of the ones before", () => {
    const ids = Array.from({ length: 12 }, (_, n) => `c${String(n)}`);
    const of = board({
      cards: Object.fromEntries(
        ids.map((id, n) => [
          id,
          { ...card, md: Array.from({ length: n + 1 }, () => "x").join("\n") },
        ]),
      ),
    });
    const placed = placeArrivals(
      null,
      of,
      emptyLocal,
      measureByLines,
      surfaceOf({}),
    );
    const rects = ids.map((id) => ({
      ...placeOf(placed, id),
      ...measureByLines(boxOfMd(of.cards[id]?.md ?? "")),
    }));
    const crossing = rects.flatMap((a, i) =>
      rects.slice(i + 1).filter((b) => overlap(a, b)),
    );
    expect(Object.keys(placed)).toEqual(ids);
    expect(crossing).toEqual([]);
  });
});

const boxOfMd = (md: string): TCardBox => ({
  md,
  width: null,
  height: null,
  versions: 0,
});

const placeOf = (placed: Record<string, TPoint>, id: string): TPoint => {
  const at = placed[id];
  if (at === undefined) throw new Error(`no place for ${id}`);
  return at;
};
