import type { TPoint } from "~/domain/board";

export type TView = TPoint & { scale: number };
export type TSize = { width: number; height: number };
export type TRect = TPoint & TSize;

const clampScale = (scale: number) => Math.min(3, Math.max(0.2, scale));

/** The point on the board under a point of the viewport. */
export const toBoard = (view: TView, at: TPoint): TPoint => ({
  x: (at.x - view.x) / view.scale,
  y: (at.y - view.y) / view.scale,
});

/** The view zoomed by the factor, with the board point under `at` kept in place. */
export const zoomAt = (view: TView, factor: number, at: TPoint): TView => {
  const scale = clampScale(view.scale * factor);
  const ratio = scale / view.scale;
  return {
    x: at.x - (at.x - view.x) * ratio,
    y: at.y - (at.y - view.y) * ratio,
    scale,
  };
};

const centre = (rect: TRect): TPoint => ({
  x: rect.x + rect.width / 2,
  y: rect.y + rect.height / 2,
});

/** The view at the same scale that shows the rect at the centre of the area of the viewport. */
export const centreOn = (view: TView, rect: TRect, area: TRect): TView => ({
  scale: view.scale,
  x: centre(area).x - centre(rect).x * view.scale,
  y: centre(area).y - centre(rect).y * view.scale,
});

/** The view that shows all the rects in the area of the viewport with a margin, at most at full scale. */
export const fitAll = (rects: TRect[], area: TRect): TView => {
  const left = Math.min(...rects.map((rect) => rect.x));
  const top = Math.min(...rects.map((rect) => rect.y));
  const right = Math.max(...rects.map((rect) => rect.x + rect.width));
  const bottom = Math.max(...rects.map((rect) => rect.y + rect.height));
  const margin = 64;
  const scale = clampScale(
    Math.min(
      1,
      (area.width - 2 * margin) / (right - left),
      (area.height - 2 * margin) / (bottom - top),
    ),
  );
  return {
    scale,
    x: area.x + (area.width - (right - left) * scale) / 2 - left * scale,
    y: area.y + (area.height - (bottom - top) * scale) / 2 - top * scale,
  };
};

/** The rect of the board point and size, as the view shows it in the viewport. */
export const onScreen = (view: TView, rect: TRect): TRect => ({
  x: view.x + rect.x * view.scale,
  y: view.y + rect.y * view.scale,
  width: rect.width * view.scale,
  height: rect.height * view.scale,
});

export const overlap = (a: TRect, b: TRect) =>
  a.x < b.x + b.width &&
  a.x + a.width > b.x &&
  a.y < b.y + b.height &&
  a.y + a.height > b.y;

/**
 * The part of the viewport that the chat and the history leave free, for what the view fits, centres and tells the
 * user about: the viewport to the left of a chat at its right side, or above a chat that spans its width, and to the
 * right of the history when it is open, with a gap.
 */
export const freeArea = (
  size: TSize,
  chat: TRect | null,
  history: TRect | null = null,
): TRect => {
  const whole = { x: 0, y: 0, ...size };
  const beside =
    chat === null
      ? whole
      : chat.x >= size.width / 2
        ? { ...whole, width: Math.max(0, chat.x - 16) }
        : { ...whole, height: Math.max(0, chat.y - 16) };
  if (history === null) return beside;
  const left = history.x + history.width + 16;
  return {
    ...beside,
    x: left,
    width: Math.max(0, beside.width - left),
  };
};

const clamp = (value: number, low: number, high: number) =>
  Math.min(Math.max(value, low), Math.max(low, high));

/**
 * Where a panel of the size goes in the area, beside a part of a card, both as the viewport shows them: to the right
 * of the card at the part's top, to the left of the card, below the card or above it, the first of these that fits
 * the area and covers none of the rects to avoid, which are the cards; failing all, to the right, or to the left
 * when the right has no room, or below the part, in the area top to bottom when it fits.
 */
export const placePanel = (
  card: TRect,
  part: TRect,
  panel: TSize,
  area: TRect,
  avoid: TRect[] = [],
): TPoint => {
  const gap = 12;
  const right = card.x + card.width + gap;
  const left = card.x - gap - panel.width;
  const fit = (at: TPoint): TPoint => ({
    x: clamp(at.x, area.x + 8, area.x + area.width - panel.width - 8),
    y: clamp(at.y, area.y + 8, area.y + area.height - panel.height - 8),
  });
  const wanted = [
    { x: right, y: part.y - 22 },
    { x: left, y: part.y - 22 },
    { x: card.x, y: card.y + card.height + gap },
    { x: card.x, y: card.y - gap - panel.height },
  ];
  const clear = wanted.find((at) => {
    const placed = fit(at);
    // The panel's size may come as a rect with its current place, which does not stand for the candidate's.
    const rect = { ...placed, width: panel.width, height: panel.height };
    return (
      placed.x === at.x &&
      placed.y === at.y &&
      !avoid.some((other) => overlap(rect, other))
    );
  });
  if (clear !== undefined) return clear;
  const x =
    right + panel.width <= area.x + area.width
      ? right
      : left >= area.x
        ? left
        : null;
  const y = x === null ? part.y + part.height + gap : part.y - 22;
  return fit({ x: x ?? card.x, y });
};

export type TDirection = "up" | "down" | "left" | "right";

/**
 * The point at the edge of the area nearest to a rect outside it, for a chip that points at the rect, clear of the
 * pill at the top and the toolbar at the bottom, with the direction from the area to the rect along the axis where it is farther.
 */
export const edgeTowards = (
  rect: TRect,
  area: TRect,
  inset: TSize,
): TPoint & { direction: TDirection } => {
  const to = centre(rect);
  const from = centre(area);
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const direction: TDirection =
    Math.abs(dx) * area.height > Math.abs(dy) * area.width
      ? dx > 0
        ? "right"
        : "left"
      : dy > 0
        ? "down"
        : "up";
  return {
    x: clamp(
      to.x - inset.width / 2,
      area.x + 16,
      area.x + area.width - inset.width - 16,
    ),
    y: clamp(
      to.y - inset.height / 2,
      area.y + 64,
      area.y + area.height - inset.height - 80,
    ),
    direction,
  };
};

/** The space between cards that the page places. */
export const gap = 48;

/** The width of a column of the grid that the page places cards on: the widest card, which has code. */
export const columnWidth = 640;

/** The least width of a card, which a narrow card's content takes too. */
export const leastCardWidth = 256;

/** The least height a resize gives a card. */
export const leastCardHeight = 64;

/** The width a resize gives a card: from the least width to two columns. */
export const clampCardWidth = (width: number) =>
  Math.min(2 * columnWidth, Math.max(leastCardWidth, width));

/** The top of the lowest free space in three columns of the grid, below the rects that cross each column. */
export const freePlace = (rects: TRect[]): TPoint => {
  return [0, 1, 2]
    .map((column) => {
      const x = column * (columnWidth + gap);
      const below = rects
        .filter((rect) => rect.x < x + columnWidth && rect.x + rect.width > x)
        .map((rect) => rect.y + rect.height + gap);
      return { x, y: Math.max(0, ...below) };
    })
    .reduce((best, place) => (place.y < best.y ? place : best));
};

const pointAt = (t: number, points: [TPoint, TPoint, TPoint, TPoint]) => {
  const [a, b, c, d] = points;
  const u = 1 - t;
  const blend = (key: "x" | "y") =>
    u * u * u * a[key] +
    3 * u * u * t * b[key] +
    3 * u * t * t * c[key] +
    t * t * t * d[key];
  return { x: blend("x"), y: blend("y") };
};

/**
 * A curve from a point at the end of the source words to a small gap before the side of the target card that faces it,
 * at the height of the start where the card spans it, and the middle of the curve, where the label goes.
 */
export const arrowCurve = (start: TPoint, to: TRect) => {
  const rightward = to.x + to.width / 2 >= start.x;
  const gap = 4;
  const end = {
    x: rightward ? to.x - gap : to.x + to.width + gap,
    y:
      to.height < 40
        ? to.y + to.height / 2
        : clamp(start.y, to.y + 20, to.y + to.height - 20),
  };
  const reach = Math.max(40, Math.abs(end.x - start.x) / 2);
  const out = rightward ? reach : -reach;
  const points: [TPoint, TPoint, TPoint, TPoint] = [
    start,
    { x: start.x + out, y: start.y },
    { x: end.x - out, y: end.y },
    end,
  ];
  const [a, b, c, d] = points;
  return {
    path: `M ${String(a.x)} ${String(a.y)} C ${String(b.x)} ${String(b.y)}, ${String(c.x)} ${String(c.y)}, ${String(d.x)} ${String(d.y)}`,
    middle: pointAt(0.5, points),
  };
};
