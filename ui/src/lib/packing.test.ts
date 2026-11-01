import fc from "fast-check";
import { describe, expect, it } from "vitest";

import type { TPoint } from "~/domain/board";
import { columnWidth, overlap, viewMargin } from "~/lib/geometry";
import type { TRect, TSize } from "~/lib/geometry";
import { gap, packCard } from "~/lib/packing";

const area = { x: 0, y: 0, width: 1440, height: 900 };
const edge = viewMargin;
const short: TSize = { width: 256, height: 100 };

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

const pairs = <T>(items: T[]): [T, T][] =>
  items.flatMap((a, index) =>
    items.slice(index + 1).map((b): [T, T] => [a, b]),
  );

const disjoint = (all: TRect[]) => pairs(all).every(([a, b]) => !overlap(a, b));

/** The rects of cards packed one after another into the area. */
const packedInTurn = (all: TSize[]) =>
  all.reduce<TRect[]>(
    (soFar, size) => [...soFar, { ...packCard(size, soFar, area), ...size }],
    [],
  );

describe("packCard", () => {
  it("puts the first card at the edge of the view", () => {
    expect(packCard(short, [], area)).toEqual({ x: edge, y: edge });
  });

  it("puts the next card to the right of the last, a gap apart, on the same row", () => {
    const first = { x: edge, y: edge, ...short };
    expect(packCard(short, [first], area)).toEqual({
      x: edge + short.width + gap,
      y: edge,
    });
  });

  it("starts a row below the first card at the left of the view when the row is full", () => {
    const row = packedInTurn(Array<TSize>(5).fill(short));
    const last = row.at(-1);
    expect(row.slice(0, 4).map((rect) => rect.y)).toEqual([
      edge,
      edge,
      edge,
      edge,
    ]);
    expect(last).toEqual({ x: edge, y: edge + short.height + gap, ...short });
  });

  it("fills a gap the view shows before it starts a new row", () => {
    const left = { x: edge, y: edge, ...short };
    const right = { x: edge + 2 * (short.width + gap), y: edge, ...short };
    expect(packCard(short, [left, right], area)).toEqual({
      x: edge + short.width + gap,
      y: edge,
    });
  });

  it("does not use a gap that is too narrow for the card and its gaps", () => {
    const left = { x: edge, y: edge, ...short };
    const right = {
      x: edge + short.width + 2 * gap - 1,
      y: edge,
      width: 900,
      height: 100,
    };
    expect(packCard(short, [left, right], area)).toEqual({
      x: edge,
      y: edge + short.height + gap,
    });
  });

  it("goes below every card at the left of the view when nothing in the view fits it", () => {
    const tall: TSize = { width: 256, height: 2000 };
    const taken = [
      { x: edge, y: edge, ...short },
      { x: 5000, y: 3000, ...short },
    ];
    expect(packCard(tall, taken, area)).toEqual({
      x: edge,
      y: 3000 + short.height + gap,
    });
  });

  it("packs into the view the user looks at, not the board's origin", () => {
    const far = { x: 10000, y: 10000, width: 1440, height: 900 };
    expect(packCard(short, [{ x: edge, y: edge, ...short }], far)).toEqual({
      x: far.x + edge,
      y: far.y + edge,
    });
  });

  it("gives the same answer for the same board", () => {
    fc.assert(
      fc.property(
        fc.array(rects(), { maxLength: 8 }),
        sizes(),
        (taken, size) => {
          expect(packCard(size, taken, area)).toEqual(
            packCard(size, [...taken].reverse(), area),
          );
        },
      ),
    );
  });

  it("never covers a rect on the board", () => {
    fc.assert(
      fc.property(
        fc.array(rects(), { maxLength: 12 }),
        sizes(),
        (taken, size) => {
          const place = { ...packCard(size, taken, area), ...size };
          expect(taken.some((rect) => overlap(place, rect))).toBe(false);
        },
      ),
    );
  });

  it("lays out cards packed one after another with no two covering each other", () => {
    fc.assert(
      fc.property(fc.array(sizes(), { minLength: 2, maxLength: 16 }), (all) => {
        expect(disjoint(packedInTurn(all))).toBe(true);
      }),
    );
  });
});

const views = (): fc.Arbitrary<TRect> =>
  fc.record({
    x: fc.double({ min: -5000, max: 5000, noNaN: true }),
    y: fc.double({ min: -5000, max: 5000, noNaN: true }),
    width: fc.double({ min: 300, max: 6000, noNaN: true }),
    height: fc.double({ min: 300, max: 4000, noNaN: true }),
  });

const floatRects = (): fc.Arbitrary<TRect> =>
  fc.record({
    x: fc.double({ min: -6000, max: 12000, noNaN: true }),
    y: fc.double({ min: -6000, max: 12000, noNaN: true }),
    width: fc.double({ min: 0.5, max: 1500, noNaN: true }),
    height: fc.double({ min: 0.5, max: 3000, noNaN: true }),
  });

const inside = (at: TPoint, size: TSize, view: TRect) =>
  at.x >= view.x + edge &&
  at.y >= view.y + edge &&
  at.x + size.width <= view.x + view.width - edge &&
  at.y + size.height <= view.y + view.height - edge;

const clearOf = (at: TPoint, size: TSize, taken: TRect[]) =>
  !taken.some((rect) =>
    overlap(
      {
        x: at.x - gap,
        y: at.y - gap,
        width: size.width + 2 * gap,
        height: size.height + 2 * gap,
      },
      rect,
    ),
  );

const readingOrder = (a: TPoint, b: TPoint) => a.y - b.y || a.x - b.x;

describe("packCard under attack", () => {
  it("lands inside a panned and zoomed view with float and negative coordinates whenever the empty view fits the card", () => {
    fc.assert(
      fc.property(views(), sizes(), (view, size) => {
        fc.pre(
          size.width <= view.width - 2 * edge &&
            size.height <= view.height - 2 * edge,
        );
        expect(inside(packCard(size, [], view), size, view)).toBe(true);
      }),
    );
  });

  it("never covers a rect when the rects and the view have float coordinates", () => {
    fc.assert(
      fc.property(
        views(),
        fc.array(floatRects(), { maxLength: 10 }),
        sizes(),
        (view, taken, size) => {
          const place = { ...packCard(size, taken, view), ...size };
          expect(taken.some((rect) => overlap(place, rect))).toBe(false);
        },
      ),
    );
  });

  it("finds a spot in the view whenever any point of the view is clear, and no later one in reading order", () => {
    fc.assert(
      fc.property(
        fc.array(rects(), { maxLength: 8 }),
        sizes(),
        fc.record({
          x: fc.integer({ min: 0, max: 1440 }),
          y: fc.integer({ min: 0, max: 900 }),
        }),
        (taken, size, candidate) => {
          fc.pre(
            inside(candidate, size, area) && clearOf(candidate, size, taken),
          );
          const found = packCard(size, taken, area);
          expect(inside(found, size, area)).toBe(true);
          expect(readingOrder(found, candidate)).toBeLessThanOrEqual(0);
        },
      ),
    );
  });

  it("moves the spot no earlier in reading order when one more rect is on the board", () => {
    fc.assert(
      fc.property(
        fc.array(rects(), { maxLength: 8 }),
        rects(),
        sizes(),
        (taken, extra, size) => {
          const before = packCard(size, taken, area);
          const after = packCard(size, [...taken, extra], area);
          fc.pre(inside(after, size, area));
          expect(inside(before, size, area)).toBe(true);
          expect(readingOrder(before, after)).toBeLessThanOrEqual(0);
        },
      ),
    );
  });

  it("gives the same spot when two cards sit at identical coordinates as when one does", () => {
    fc.assert(
      fc.property(
        fc.array(rects(), { maxLength: 6 }),
        rects(),
        sizes(),
        (taken, twin, size) => {
          expect(packCard(size, [...taken, twin, twin], area)).toEqual(
            packCard(size, [...taken, twin], area),
          );
        },
      ),
    );
  });

  it("keeps clear of every rect of a pile the user dragged onto each other, and still fills the view beside the pile", () => {
    const pile = [
      { x: edge, y: edge, width: 300, height: 200 },
      { x: edge + 20, y: edge + 30, width: 300, height: 200 },
      { x: edge + 40, y: edge + 60, width: 300, height: 200 },
    ];
    const found = packCard(short, pile, area);
    expect(found).toEqual({ x: edge + 40 + 300 + gap, y: edge });
    expect(clearOf(found, short, pile)).toBe(true);
  });

  it("puts a card that no spot of the view fits below the lowest rect even when the rects cross each other", () => {
    fc.assert(
      fc.property(
        fc.array(rects(), { minLength: 1, maxLength: 8 }),
        (taken) => {
          const huge: TSize = { width: 1440, height: 900 };
          const found = packCard(huge, taken, area);
          const bottom = Math.max(
            ...taken.map((rect) => rect.y + rect.height + gap),
          );
          expect(found).toEqual({ x: edge, y: Math.max(edge, bottom) });
        },
      ),
    );
  });

  it("stays within the time of a frame for a board of two hundred cards", () => {
    const many = packedInTurn(Array<TSize>(200).fill(short));
    const started = performance.now();
    packCard(short, many, area);
    expect(performance.now() - started).toBeLessThan(100);
  });
});
