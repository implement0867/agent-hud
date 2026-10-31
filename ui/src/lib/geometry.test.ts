import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { overlap, placePanel, toBoardRect } from "~/lib/geometry";
import type { TRect } from "~/lib/geometry";

const rects = (): fc.Arbitrary<TRect> =>
  fc.record({
    x: fc.integer({ min: -1000, max: 3000 }),
    y: fc.integer({ min: -1000, max: 6000 }),
    width: fc.integer({ min: 1, max: 1500 }),
    height: fc.integer({ min: 1, max: 3000 }),
  });

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

describe("toBoardRect", () => {
  it("takes the view's pan and scale off a rect of the viewport", () => {
    const view = { x: 100, y: 50, scale: 2 };
    expect(
      toBoardRect(view, { x: 300, y: 250, width: 400, height: 200 }),
    ).toEqual({ x: 100, y: 100, width: 200, height: 100 });
  });
});

describe("placePanel", () => {
  const area = { x: 0, y: 0, width: 1440, height: 900 };
  const panel = { width: 288, height: 300 };
  const card = { x: 100, y: 100, width: 384, height: 400 };
  const part = { x: 116, y: 300, width: 352, height: 24 };

  it("goes to the right of the card at the part's top when nothing is there", () => {
    expect(placePanel(card, part, panel, area)).toEqual({ x: 496, y: 278 });
  });

  it("goes below the card when a card on the right and the left edge leave no room beside", () => {
    const other = { x: 530, y: 0, width: 384, height: 600 };
    const at = placePanel(card, part, panel, area, [card, other]);
    expect(at).toEqual({ x: 100, y: 512 });
    expect(overlap({ ...at, ...panel }, other)).toBe(false);
    expect(overlap({ ...at, ...panel }, card)).toBe(false);
  });

  it("judges a candidate by its own place when the size comes with the panel's current place", () => {
    const other = { x: 530, y: 0, width: 384, height: 600 };
    const sized = { x: 496, y: 278, width: 288, height: 300 };
    const at = placePanel(card, part, sized, area, [card, other]);
    expect(at).toEqual({ x: 100, y: 512 });
  });

  it("falls back to the side when every place covers a card", () => {
    const everywhere = { x: 0, y: 0, width: 1440, height: 900 };
    expect(placePanel(card, part, panel, area, [everywhere])).toEqual({
      x: 496,
      y: 278,
    });
  });
});
