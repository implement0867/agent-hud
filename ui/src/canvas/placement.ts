import { intersects } from "~/canvas/viewport";
import type { Point, Rect } from "~/canvas/viewport";

export type FlowOptions = { origin: Point; gap: number; rowWidth: number };

/** Right of the most recent card while the row has room, else a new row below everything. */
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
  if (fitsRow && !placed.some((r) => intersects(r, beside, gap / 2)))
    return { x: beside.x, y: beside.y };
  const bottom = Math.max(...placed.map((r) => r.y + r.h));
  return { x: origin.x, y: bottom + gap };
};
