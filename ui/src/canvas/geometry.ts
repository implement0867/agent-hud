import { intersects } from "~/canvas/viewport";
import type { Point, Rect } from "~/canvas/viewport";

/** Path data, plus where its text goes and how the text aligns there. */
export type Arrow = { d: string; label: Point & { align: "middle" | "start" } };

const center = (r: Rect): Point => ({ x: r.x + r.w / 2, y: r.y + r.h / 2 });

/** One decimal is plenty on screen and keeps path strings stable between frames. */
const n = (v: number) => String(Math.round(v * 10) / 10);

const path = (p0: Point, p1: Point, p2: Point, p3: Point) =>
  `M ${n(p0.x)} ${n(p0.y)} C ${n(p1.x)} ${n(p1.y)}, ${n(p2.x)} ${n(p2.y)}, ${n(p3.x)} ${n(p3.y)}`;

/** Point at t = 0.5 on a cubic Bézier. */
const midpoint = (p0: Point, p1: Point, p2: Point, p3: Point): Point => ({
  x: (p0.x + 3 * p1.x + 3 * p2.x + p3.x) / 8,
  y: (p0.y + 3 * p1.y + 3 * p2.y + p3.y) / 8,
});

/**
 * Curved arrow between two anchor boxes. Boxes side by side connect facing edges;
 * boxes in one column (such as two items of one list) loop out on the right.
 */
export const arrowBetween = (a: Rect, b: Rect, gap = 16): Arrow => {
  const ca = center(a);
  const cb = center(b);
  if (b.x > a.x + a.w + gap || a.x > b.x + b.w + gap) {
    const forward = b.x > a.x;
    const start = { x: forward ? a.x + a.w : a.x, y: ca.y };
    const end = { x: forward ? b.x : b.x + b.w, y: cb.y };
    const bend =
      Math.max(40, Math.abs(end.x - start.x) / 2) * (forward ? 1 : -1);
    const c1 = { x: start.x + bend, y: start.y };
    const c2 = { x: end.x - bend, y: end.y };
    const mid = midpoint(start, c1, c2, end);
    return {
      d: path(start, c1, c2, end),
      label: { x: mid.x, y: mid.y - 6, align: "middle" },
    };
  }
  // Longer loops bulge further out, so nested loops and their texts stay apart.
  const start = { x: a.x + a.w, y: ca.y };
  const end = { x: b.x + b.w, y: cb.y };
  const out =
    Math.max(start.x, end.x) +
    24 +
    Math.min(Math.abs(end.y - start.y) * 0.3, 72);
  const c1 = { x: out, y: start.y };
  const c2 = { x: out, y: end.y };
  const mid = midpoint(start, c1, c2, end);
  return {
    d: path(start, c1, c2, end),
    label: { x: mid.x + 6, y: mid.y + 4, align: "start" },
  };
};

/** Box of an arrow text of width `w`, from its anchor point and alignment. */
export const labelBox = (label: Arrow["label"], w: number, h = 14): Rect => ({
  x: label.align === "middle" ? label.x - w / 2 : label.x,
  y: label.y - h + 3,
  w,
  h,
});

/** Move boxes down, in order, until none overlaps one placed before it. */
export const separate = (boxes: readonly Rect[], step = 14): Rect[] =>
  boxes.reduce<Rect[]>((placed, box) => {
    let moved = box;
    while (placed.some((p) => intersects(p, moved))) {
      moved = { ...moved, y: moved.y + step };
    }
    return [...placed, moved];
  }, []);
