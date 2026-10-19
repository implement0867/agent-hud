import type { Point, Rect } from "~/canvas/viewport";

export type FlowOptions = { origin: Point; gap: number; rowWidth: number };

const overlaps = (a: Rect, b: Rect, gap: number) =>
  a.x < b.x + b.w + gap &&
  b.x < a.x + a.w + gap &&
  a.y < b.y + b.h + gap &&
  b.y < a.y + a.h + gap;

/**
 * Where a new card of width `w` goes: right of the most recent card while the row has room,
 * otherwise at the start of a new row below everything.
 */
export const nextPlacement = (
  placed: readonly Rect[],
  size: { w: number; h: number },
  { origin, gap, rowWidth }: FlowOptions = {
    origin: { x: 48, y: 48 },
    gap: 72,
    rowWidth: 1600,
  },
): Point => {
  const last = placed.at(-1);
  if (last === undefined) return origin;
  const beside: Rect = { x: last.x + last.w + gap, y: last.y, ...size };
  const fitsRow = beside.x + size.w <= origin.x + rowWidth;
  if (fitsRow && !placed.some((r) => overlaps(r, beside, gap / 2)))
    return { x: beside.x, y: beside.y };
  const bottom = Math.max(...placed.map((r) => r.y + r.h));
  return { x: origin.x, y: bottom + gap };
};
