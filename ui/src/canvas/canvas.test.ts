import { describe, expect, it } from "vitest";

import { arrowBetween, separate } from "./geometry";
import { nextPlacement } from "./placement";
import { fit, reveal, toWorld, zoomAt } from "./viewport";

describe("viewport", () => {
  it.each([
    [
      { x: 0, y: 0, zoom: 1 },
      { x: 100, y: 50 },
      { x: 100, y: 50 },
    ],
    [
      { x: 20, y: 10, zoom: 2 },
      { x: 120, y: 50 },
      { x: 50, y: 20 },
    ],
  ])("maps screen to world", (v, screen, world) => {
    expect(toWorld(v, screen)).toEqual(world);
  });

  it("zooms around the cursor", () => {
    const v = { x: 30, y: 40, zoom: 1 };
    const cursor = { x: 200, y: 100 };
    const before = toWorld(v, cursor);
    const after = toWorld(zoomAt(v, cursor, 1.5), cursor);
    expect(after.x).toBeCloseTo(before.x);
    expect(after.y).toBeCloseTo(before.y);
  });

  it.each([0.01, 100])("clamps zoom factor %d", (factor) => {
    const { zoom } = zoomAt({ x: 0, y: 0, zoom: 1 }, { x: 0, y: 0 }, factor);
    expect(zoom).toBeGreaterThanOrEqual(0.2);
    expect(zoom).toBeLessThanOrEqual(3);
  });

  it("fits bounds without zooming in past 100%", () => {
    expect(fit({ x: 0, y: 0, w: 100, h: 100 }, { w: 1000, h: 800 }).zoom).toBe(
      1,
    );
    expect(
      fit({ x: 0, y: 0, w: 4000, h: 1000 }, { w: 1000, h: 800 }).zoom,
    ).toBeLessThan(1);
  });

  it("reveals an off-screen card and leaves a visible one alone", () => {
    const v = { x: 0, y: 0, zoom: 1 };
    const size = { w: 1000, h: 800 };
    expect(reveal(v, { x: 100, y: 100, w: 200, h: 100 }, size)).toBeNull();
    expect(reveal(v, { x: 1500, y: 100, w: 200, h: 100 }, size)?.x).toBe(-748);
  });
});

describe("placement", () => {
  const size = { w: 300, h: 200 };

  it("starts at the origin", () => {
    expect(nextPlacement([], size)).toEqual({ x: 48, y: 48 });
  });

  it("flows right, then wraps below the tallest card", () => {
    const row = [
      { x: 48, y: 48, w: 600, h: 500 },
      { x: 720, y: 48, w: 800, h: 200 },
    ];
    expect(nextPlacement(row.slice(0, 1), size)).toEqual({ x: 720, y: 48 });
    expect(nextPlacement(row, size)).toEqual({ x: 48, y: 620 });
  });
});

describe("arrows", () => {
  it("connects facing edges of side-by-side boxes", () => {
    const { d } = arrowBetween(
      { x: 0, y: 0, w: 100, h: 20 },
      { x: 300, y: 0, w: 100, h: 20 },
    );
    expect(d.startsWith("M 100 10")).toBe(true);
    expect(d.endsWith("300 10")).toBe(true);
  });

  it("loops out to the right between rows of one column", () => {
    const { d, label } = arrowBetween(
      { x: 0, y: 100, w: 200, h: 20 },
      { x: 0, y: 0, w: 200, h: 20 },
    );
    expect(d.startsWith("M 200 110")).toBe(true);
    expect(label.x).toBeGreaterThan(200);
    expect(label.align).toBe("start");
  });

  it("bulges longer loops further so their texts stay apart", () => {
    const box = { x: 0, w: 200, h: 20 };
    const short = arrowBetween({ ...box, y: 100 }, { ...box, y: 70 });
    const long = arrowBetween({ ...box, y: 200 }, { ...box, y: 0 });
    expect(long.label.x - short.label.x).toBeGreaterThan(30);
  });
});

describe("arrow texts", () => {
  it("moves overlapping boxes down and leaves clear ones alone", () => {
    const items = separate([
      { box: { x: 0, y: 0, w: 40, h: 14 } },
      { box: { x: 20, y: 4, w: 40, h: 14 } },
      { box: { x: 200, y: 0, w: 40, h: 14 } },
    ]);
    expect(items.map((i) => i.box.y)).toEqual([0, 18, 0]);
  });
});
