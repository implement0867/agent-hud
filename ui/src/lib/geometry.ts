import type { TPoint } from "~/schemas/board";

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
 * The part of the viewport that the chat leaves free, for what the view fits, centres and tells the user about:
 * the viewport to the left of a chat at its right side, or above a chat that spans its width, with a gap.
 */
export const freeArea = (size: TSize, chat: TRect | null): TRect => {
  const whole = { x: 0, y: 0, ...size };
  if (chat === null) return whole;
  return chat.x >= size.width / 2
    ? { ...whole, width: Math.max(0, chat.x - 16) }
    : { ...whole, height: Math.max(0, chat.y - 16) };
};

const clamp = (value: number, low: number, high: number) =>
  Math.min(Math.max(value, low), Math.max(low, high));

/**
 * Where a panel of the size goes in the area, beside a part of a card, both as the viewport shows them:
 * to the right of the card at the part's top; to the left of the card when the right has no room;
 * below the part when neither side has; and in the area top to bottom, when it fits.
 */
export const placePanel = (
  card: TRect,
  part: TRect,
  panel: TSize,
  area: TRect,
): TPoint => {
  const gap = 12;
  const right = card.x + card.width + gap;
  const left = card.x - gap - panel.width;
  const x =
    right + panel.width <= area.x + area.width
      ? right
      : left >= area.x
        ? left
        : null;
  const y = x === null ? part.y + part.height + gap : part.y - 22;
  return {
    x: clamp(x ?? card.x, area.x + 8, area.x + area.width - panel.width - 8),
    y: clamp(y, area.y + 8, area.y + area.height - panel.height - 8),
  };
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

/**
 * The places that the rects below the grown rect move to, so that none of them crosses it or another moved rect:
 * each rect that crosses the grown rect's columns and starts below its top goes to the next free space, in order of
 * its top, when it would cross the rect above it. Nothing moves when nothing crosses.
 */
export const pushedBelow = (
  grown: TRect,
  rects: Record<string, TRect>,
): Record<string, TPoint> => {
  const below = Object.entries(rects)
    .filter(
      ([, rect]) =>
        rect.y > grown.y &&
        rect.x < grown.x + grown.width &&
        rect.x + rect.width > grown.x,
    )
    .sort(([, a], [, b]) => a.y - b.y);
  const moved: Record<string, TPoint> = {};
  let floor = grown.y + grown.height + gap;
  for (const [id, rect] of below) {
    if (rect.y >= floor) continue;
    moved[id] = { x: rect.x, y: floor };
    floor += rect.height + gap;
  }
  return moved;
};

/** The rect of the element in board coordinates, from its rect in the viewport. */
export const rectOnBoard = (
  element: Element,
  world: Element,
  scale: number,
): TRect => {
  const rect = element.getBoundingClientRect();
  const origin = world.getBoundingClientRect();
  return {
    x: (rect.left - origin.left) / scale,
    y: (rect.top - origin.top) / scale,
    width: rect.width / scale,
    height: rect.height / scale,
  };
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
 * A curve from the side of the source card that faces the target card, at the height of the source part,
 * to a small gap before the facing side of the target card, at the height of the target part. Cards one above the other loop out to the right.
 */
export const arrowCurve = (
  from: { card: TRect; y: number },
  to: { card: TRect; y: number },
) => {
  const fromCentre = from.card.x + from.card.width / 2;
  const toCentre = to.card.x + to.card.width / 2;
  const apart = Math.abs(toCentre - fromCentre) > from.card.width / 2;
  const rightward = toCentre > fromCentre;
  const start = {
    x: apart && !rightward ? from.card.x : from.card.x + from.card.width,
    y: from.y,
  };
  const gap = 4;
  const end = {
    x: apart && rightward ? to.card.x - gap : to.card.x + to.card.width + gap,
    y: to.y,
  };
  const reach = Math.max(48, Math.abs(end.x - start.x) / 2);
  const out = apart && !rightward ? -reach : reach;
  const back = apart ? -out : reach;
  const points: [TPoint, TPoint, TPoint, TPoint] = [
    start,
    { x: start.x + out, y: start.y },
    { x: end.x + back, y: end.y },
    end,
  ];
  const [a, b, c, d] = points;
  return {
    path: `M ${String(a.x)} ${String(a.y)} C ${String(b.x)} ${String(b.y)}, ${String(c.x)} ${String(c.y)}, ${String(d.x)} ${String(d.y)}`,
    middle: pointAt(0.5, points),
  };
};

/** The card of the ref, and the height of the middle of the ref's first line, in board coordinates. */
export const endOnBoard = (
  world: Element,
  ref: string,
  scale: number,
): { card: TRect; y: number } | null => {
  const [cardId = ""] = ref.split("/");
  const card = world.querySelector(`article[data-ref="${CSS.escape(cardId)}"]`);
  const part = world.querySelector(`[data-ref="${CSS.escape(ref)}"]`);
  if (card === null || part === null) return null;
  const rect = rectOnBoard(part, world, scale);
  return {
    card: rectOnBoard(card, world, scale),
    y: rect.y + Math.min(14, rect.height / 2),
  };
};
