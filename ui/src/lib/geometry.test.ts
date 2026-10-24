import fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  columnWidth,
  freePlace,
  gap,
  overlap,
  settleCards,
} from "~/lib/geometry";
import type { TRect, TSize } from "~/lib/geometry";

const sizes = (): fc.Arbitrary<TSize> =>
  fc.record({
    width: fc.integer({ min: 1, max: columnWidth }),
    height: fc.integer({ min: 1, max: 3000 }),
  });

const rects = (): fc.Arbitrary<TRect> =>
  fc.record({
    x: fc.integer({ min: -1000, max: 3000 }),
    y: fc.integer({ min: -1000, max: 6000 }),
    width: fc.integer({ min: 1, max: 1500 }),
    height: fc.integer({ min: 1, max: 3000 }),
  });

const boards = (): fc.Arbitrary<Record<string, TRect>> =>
  fc
    .uniqueArray(fc.tuple(fc.stringMatching(/^[a-z]{1,3}$/), rects()), {
      selector: ([id]) => id,
      maxLength: 12,
    })
    .map((entries) => Object.fromEntries(entries));

const pairs = <T>(items: T[]): [T, T][] =>
  items.flatMap((a, index) =>
    items.slice(index + 1).map((b): [T, T] => [a, b]),
  );

const disjoint = (all: TRect[]) => pairs(all).every(([a, b]) => !overlap(a, b));

/** The rects of cards placed one after another, each at the free place below the ones before it. */
const placedInTurn = (all: TSize[]) =>
  all.reduce<TRect[]>(
    (soFar, size) => [...soFar, { ...freePlace(soFar), ...size }],
    [],
  );

describe("overlap", () => {
  it("is symmetric", () => {
    fc.assert(
      fc.property(rects(), rects(), (a, b) => {
        expect(overlap(a, b)).toBe(overlap(b, a));
      }),
    );
  });

  it("does not count rects that touch at an edge", () => {
    fc.assert(
      fc.property(rects(), (a) => {
        expect(overlap(a, { ...a, x: a.x + a.width })).toBe(false);
        expect(overlap(a, { ...a, y: a.y + a.height })).toBe(false);
      }),
    );
  });
});

describe("freePlace", () => {
  it("puts a card of at most a column's width clear of every rect on the board", () => {
    fc.assert(
      fc.property(
        fc.array(rects(), { maxLength: 12 }),
        sizes(),
        (taken, size) => {
          const place = { ...freePlace(taken), ...size };
          expect(place.y).toBeGreaterThanOrEqual(0);
          expect(place.x % (columnWidth + gap)).toBe(0);
          expect(taken.some((rect) => overlap(place, rect))).toBe(false);
        },
      ),
    );
  });

  it("lays out cards placed one after another with no two covering each other", () => {
    fc.assert(
      fc.property(fc.array(sizes(), { minLength: 2, maxLength: 16 }), (all) => {
        expect(disjoint(placedInTurn(all))).toBe(true);
      }),
    );
  });
});

describe("settleCards", () => {
  it("leaves no card covering another, moves cards only down, and keeps the fixed card where it is", () => {
    fc.assert(
      fc.property(
        boards(),
        fc.option(fc.integer({ min: 0, max: 11 }), { nil: null }),
        (board, pick) => {
          const ids = Object.keys(board);
          const fixed =
            pick === null || ids.length === 0
              ? null
              : (ids[pick % ids.length] ?? null);
          const moved = settleCards(board, fixed);
          const after = Object.entries(board).map(([id, rect]) => ({
            ...rect,
            ...moved[id],
          }));
          expect(disjoint(after)).toBe(true);
          for (const [id, to] of Object.entries(moved)) {
            const from = board[id];
            expect(from).toBeDefined();
            expect(to.x).toBe(from?.x);
            expect(to.y).toBeGreaterThan(from?.y ?? Infinity);
          }
          if (fixed !== null) expect(moved).not.toHaveProperty(fixed);
        },
      ),
    );
  });

  it("moves nothing on a board where no card covers another", () => {
    fc.assert(
      fc.property(fc.array(sizes(), { maxLength: 12 }), (all) => {
        const board = Object.fromEntries(
          placedInTurn(all).map((rect, index) => [String(index), rect]),
        );
        expect(settleCards(board)).toEqual({});
      }),
    );
  });
});
