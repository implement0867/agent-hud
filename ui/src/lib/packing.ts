import type { TPoint } from "~/domain/board";
import { overlap, viewMargin } from "~/lib/geometry";
import type { TRect, TSize } from "~/lib/geometry";

/** The space between cards that the page places. */
export const gap = 48;

const edge = viewMargin;

const byReadingOrder = (a: TPoint, b: TPoint) => a.y - b.y || a.x - b.x;

/**
 * Where a card of the size goes among the rects on the board, in the part of the board that the view shows: the first
 * spot in reading order, on the grid of the view's margin and the rects' edges, where the card fits inside the view's
 * margin with the gap from every rect; or, when no spot in the view fits it, below every rect at the left of the view.
 */
export const packCard = (size: TSize, taken: TRect[], area: TRect): TPoint => {
  const inside = (at: TPoint) =>
    at.x >= area.x + edge &&
    at.y >= area.y + edge &&
    at.x + size.width <= area.x + area.width - edge &&
    at.y + size.height <= area.y + area.height - edge;
  const clear = (at: TPoint) => {
    const grown = {
      x: at.x - gap,
      y: at.y - gap,
      width: size.width + 2 * gap,
      height: size.height + 2 * gap,
    };
    return !taken.some((rect) => overlap(grown, rect));
  };
  const xs = [
    area.x + edge,
    ...taken.flatMap((rect) => [rect.x, rect.x + rect.width + gap]),
  ];
  const ys = [
    area.y + edge,
    ...taken.flatMap((rect) => [rect.y, rect.y + rect.height + gap]),
  ];
  const spots = ys
    .flatMap((y) => xs.map((x) => ({ x, y })))
    .filter((at) => inside(at) && clear(at))
    .sort(byReadingOrder);
  return (
    spots[0] ?? {
      x: area.x + edge,
      y: Math.max(
        area.y + edge,
        ...taken.map((rect) => rect.y + rect.height + gap),
      ),
    }
  );
};
