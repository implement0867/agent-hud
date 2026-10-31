import fc from "fast-check";
import { describe, expect, it } from "vitest";

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
